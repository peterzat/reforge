"""Orchestration pipeline: validate -> preprocess -> encode -> generate -> harmonize -> compose."""

import os
import sys
import time

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


def _fmt_time(seconds: float) -> str:
    """Format seconds as a human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def _log(msg: str, verbose: bool, end: str = "\n") -> None:
    """Print a status line if verbose."""
    if verbose:
        sys.stderr.write(msg + end)
        sys.stderr.flush()


def run(
    style_path: str | None = None,
    style_image_paths: list[str] | None = None,
    text: str = "",
    output_path: str = "result.png",
    num_steps: int = DEFAULT_DDIM_STEPS,
    guidance_scale: float = DEFAULT_GUIDANCE_SCALE,
    num_candidates: int = DEFAULT_NUM_CANDIDATES,
    device: str | None = None,
    verbose: bool = True,
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
        verbose: Print progress to stderr.

    Returns:
        Dict with output_path, quality_scores, and word_positions.
    """
    import cv2

    # --- Validate device ---
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA requested but not available. "
            "Use --device cpu for CPU inference (slow) or install CUDA drivers."
        )

    if verbose:
        if device == "cuda":
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            _log(f"Device: {name} ({vram:.0f} GB)", verbose)
        else:
            _log(f"Device: {device}", verbose)

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

    # --- Load models ---
    t0 = time.monotonic()
    _log("Loading models...", verbose, end="")

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

    unet_ckpt = download_unet_weights()
    unet = load_unet(unet_ckpt, device=device)
    vae = load_vae(device=device)
    tokenizer = load_tokenizer()

    _log(f" done ({_fmt_time(time.monotonic() - t0)})", verbose)

    # --- Generate words ---
    from reforge.model.generator import generate_word

    # Pre-build unconditional context for CFG (reused across all words)
    uncond_context = None
    if guidance_scale != 1.0:
        uncond_context = tokenizer(" ", return_tensors="pt", padding="max_length", max_length=16)

    # Build flat word list with None sentinels for paragraph breaks
    flat_words = []
    for i, para in enumerate(paragraphs):
        if i > 0:
            flat_words.append(None)
        for word in para:
            flat_words.append(word)

    real_words = [w for w in flat_words if w is not None]
    n_words = len(real_words)
    _log(f"Generating {n_words} words ({num_steps} steps, {num_candidates} candidates)", verbose)

    generated_images = []
    word_idx = 0
    t_gen = time.monotonic()
    for word in flat_words:
        if word is None:
            generated_images.append(None)
            continue
        word_idx += 1
        if verbose:
            elapsed = time.monotonic() - t_gen
            if word_idx > 1:
                eta = elapsed / (word_idx - 1) * (n_words - word_idx + 1)
                msg = f"  [{word_idx}/{n_words}] {word} (ETA {_fmt_time(eta)})"
            else:
                msg = f"  [{word_idx}/{n_words}] {word}"
            _log(f"\r{msg:<60}", verbose, end="")
        img = generate_word(
            word, unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=num_steps,
            guidance_scale=guidance_scale,
            num_candidates=num_candidates,
            device=device,
        )
        generated_images.append(img)

    gen_time = time.monotonic() - t_gen
    _log(f"\r  [{n_words}/{n_words}] done ({_fmt_time(gen_time)})" + " " * 20, verbose)

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

    output_img, word_positions = compose_words(
        generated_images, flat_words, return_positions=True,
    )
    output_img.save(output_path)

    # --- Evaluate ---
    from reforge.evaluate.visual import overall_quality_score

    output_array = np.array(output_img)
    real_word_imgs = [img for img in generated_images if img is not None]
    quality = overall_quality_score(
        output_array, real_word_imgs, word_positions, words=real_words,
    )

    # --- Summary ---
    file_size = os.path.getsize(output_path)
    size_str = f"{file_size / 1024:.0f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024*1024):.1f} MB"
    _log(f"Output: {output_path} ({output_img.width}x{output_img.height}, {size_str})", verbose)

    if verbose:
        parts = [f"{k}={v:.2f}" for k, v in quality.items() if k != "overall"]
        _log(f"Quality: {quality['overall']:.2f} ({' '.join(parts)})", verbose)

    return {
        "output_path": output_path,
        "quality_scores": quality,
        "word_positions": word_positions,
    }
