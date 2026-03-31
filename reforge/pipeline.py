"""Orchestration pipeline: validate -> preprocess -> encode -> generate -> harmonize -> compose."""

import numpy as np
import torch
from PIL import Image

# Enable tensor core acceleration on Ada GPUs
torch.set_float32_matmul_precision("high")
if torch.backends.cudnn.is_available():
    torch.backends.cudnn.benchmark = True

from reforge.config import (
    DEFAULT_DDIM_STEPS,
    DEFAULT_GUIDANCE_SCALE,
    DEFAULT_NUM_CANDIDATES,
    NUM_STYLE_WORDS,
)
from reforge.validation import split_paragraphs, validate_charset


def run(
    style_path: str | None = None,
    style_image_paths: list[str] | None = None,
    text: str = "",
    output_path: str = "result.png",
    num_steps: int = DEFAULT_DDIM_STEPS,
    guidance_scale: float = DEFAULT_GUIDANCE_SCALE,
    num_candidates: int = DEFAULT_NUM_CANDIDATES,
    device: str = "cuda",
) -> dict:
    """Run the full generation pipeline.

    Args:
        style_path: Path to a sentence image (will be segmented into 5 words).
        style_image_paths: Alternatively, paths to exactly 5 pre-segmented word images.
        text: Text to generate (supports newlines for paragraphs).
        output_path: Where to save the output PNG.
        num_steps: DDIM sampling steps.
        guidance_scale: CFG guidance scale.
        num_candidates: Best-of-N candidate count.
        device: Torch device.

    Returns:
        Dict with output_path, quality_scores, and word_positions.
    """
    import cv2
    import torch

    # --- Validate ---
    validate_charset(text)
    paragraphs = split_paragraphs(text)
    if not paragraphs:
        raise ValueError("No text provided")

    # --- Preprocess style images ---
    from reforge.preprocess.normalize import preprocess_words
    from reforge.preprocess.segment import segment_sentence_image

    if style_image_paths is not None:
        if len(style_image_paths) != NUM_STYLE_WORDS:
            raise ValueError(f"Expected {NUM_STYLE_WORDS} style images, got {len(style_image_paths)}")
        word_imgs_raw = [cv2.imread(p, cv2.IMREAD_GRAYSCALE) for p in style_image_paths]
        for i, img in enumerate(word_imgs_raw):
            if img is None:
                raise FileNotFoundError(f"Could not read style image: {style_image_paths[i]}")
    elif style_path is not None:
        style_img = cv2.imread(style_path, cv2.IMREAD_GRAYSCALE)
        if style_img is None:
            raise FileNotFoundError(f"Could not read style image: {style_path}")
        word_imgs_raw = segment_sentence_image(style_img)
        if len(word_imgs_raw) != NUM_STYLE_WORDS:
            raise ValueError(
                f"Expected {NUM_STYLE_WORDS} words in style image, got {len(word_imgs_raw)}. "
                "Style image must contain exactly 5 words."
            )
    else:
        raise ValueError("Must provide either style_path or style_image_paths")

    style_tensors = preprocess_words(word_imgs_raw)

    # --- Encode style ---
    from reforge.model.encoder import StyleEncoder
    from reforge.model.weights import (
        download_style_encoder_weights,
        download_unet_weights,
        load_tokenizer,
        load_unet,
        load_vae,
    )

    style_ckpt = download_style_encoder_weights()
    encoder = StyleEncoder(checkpoint_path=style_ckpt)
    encoder = encoder.to(device)
    style_features = encoder.encode(style_tensors)

    # --- Load generation models ---
    unet_ckpt = download_unet_weights()
    unet = load_unet(unet_ckpt, device=device)
    vae = load_vae(device=device)
    tokenizer = load_tokenizer()

    # --- Generate words ---
    from reforge.model.generator import generate_word

    # Pre-build unconditional context for CFG (reused across all words)
    uncond_context = None
    if guidance_scale != 1.0:
        uncond_context = tokenizer(" ", return_tensors="pt", padding="max_length", max_length=16)

    # Build flat word list with None sentinels for paragraph breaks
    flat_words = []
    flat_images = []
    for i, para in enumerate(paragraphs):
        if i > 0:
            flat_words.append(None)
            flat_images.append(None)
        for word in para:
            flat_words.append(word)

    generated_images = []
    for word in flat_words:
        if word is None:
            generated_images.append(None)
            continue
        img = generate_word(
            word, unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=num_steps,
            guidance_scale=guidance_scale,
            num_candidates=num_candidates,
            device=device,
        )
        generated_images.append(img)

    # --- Font normalization ---
    from reforge.quality.font_scale import normalize_font_size

    for i, (img, word) in enumerate(zip(generated_images, flat_words)):
        if img is not None and word is not None:
            generated_images[i] = normalize_font_size(img, word)

    # --- Harmonize ---
    from reforge.quality.harmonize import harmonize_words

    real_images = [img for img in generated_images if img is not None]
    harmonized = harmonize_words(real_images)
    real_idx = 0
    for i in range(len(generated_images)):
        if generated_images[i] is not None:
            generated_images[i] = harmonized[real_idx]
            real_idx += 1

    # --- Compose ---
    from reforge.compose.render import compose_words

    output_img = compose_words(generated_images, flat_words)
    output_img.save(output_path)

    # --- Evaluate ---
    from reforge.compose.layout import compute_word_positions
    from reforge.evaluate.visual import overall_quality_score

    output_array = np.array(output_img)
    word_positions = compute_word_positions(generated_images, flat_words)
    real_word_imgs = [img for img in generated_images if img is not None]
    quality = overall_quality_score(output_array, real_word_imgs, word_positions)

    return {
        "output_path": output_path,
        "quality_scores": quality,
        "word_positions": word_positions,
    }
