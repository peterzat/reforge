"""Evaluate preprocessing variations on style input quality.

Tests whether changes to preprocessing before style encoding improve
output quality: crop padding, CLAHE strength, binarization.

Usage:
    python experiments/sweep_preprocess.py --style styles/hw-sample.png
"""

import argparse
import json
import os
import sys
import time

import cv2
import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SEED = 42
DEMO_TEXT_WORDS = ["The", "morning", "sun", "cast", "long"]
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "output", "preprocess_sweep.json")


def main():
    parser = argparse.ArgumentParser(description="Sweep preprocessing variations")
    parser.add_argument("--style", type=str, default="styles/hw-sample.png")
    parser.add_argument("--device", type=str, default="cuda")
    args = parser.parse_args()

    from reforge.config import PRESET_QUALITY
    from reforge.compose.render import compose_words
    from reforge.evaluate.visual import overall_quality_score
    from reforge.model.encoder import StyleEncoder
    from reforge.model.generator import generate_word
    from reforge.model.weights import (
        download_style_encoder_weights,
        download_unet_weights,
        load_tokenizer,
        load_unet,
        load_vae,
    )
    from reforge.preprocess.normalize import (
        deskew_word,
        normalize_contrast,
        word_to_tensor,
    )
    from reforge.preprocess.segment import segment_sentence_image
    from reforge.quality.font_scale import normalize_font_size
    from reforge.quality.harmonize import harmonize_words

    device = args.device
    steps = PRESET_QUALITY["steps"]
    guidance = PRESET_QUALITY["guidance_scale"]

    # Load models
    unet_ckpt = download_unet_weights()
    unet = load_unet(unet_ckpt, device=device)
    vae = load_vae(device=device)
    tokenizer = load_tokenizer()
    uncond_context = tokenizer(" ", return_tensors="pt", padding="max_length", max_length=16)

    style_ckpt = download_style_encoder_weights()

    # Segment style image
    style_img = cv2.imread(args.style, cv2.IMREAD_GRAYSCALE)
    if style_img is None:
        raise FileNotFoundError(f"Cannot read: {args.style}")
    words_raw = segment_sentence_image(style_img)
    if len(words_raw) != 5:
        raise ValueError(f"Expected 5 words, got {len(words_raw)}")

    # Define preprocessing variants
    variants = {
        "default": {
            "description": "Standard: deskew + CLAHE(2.0) + grayscale tensor",
            "fn": lambda w: word_to_tensor(normalize_contrast(deskew_word(w))),
        },
        "clahe_1.0": {
            "description": "Weaker CLAHE (clipLimit=1.0)",
            "fn": lambda w: word_to_tensor(
                cv2.createCLAHE(clipLimit=1.0, tileGridSize=(4, 4)).apply(deskew_word(w))
            ),
        },
        "clahe_4.0": {
            "description": "Stronger CLAHE (clipLimit=4.0)",
            "fn": lambda w: word_to_tensor(
                cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4)).apply(deskew_word(w))
            ),
        },
        "binarized": {
            "description": "Otsu binarization (pure black/white)",
            "fn": lambda w: word_to_tensor(
                cv2.threshold(deskew_word(w), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            ),
        },
    }

    results = []
    for vname, variant in variants.items():
        print(f"\n--- {vname}: {variant['description']} ---")
        torch.manual_seed(SEED)
        np.random.seed(SEED)

        # Preprocess style words with this variant
        style_tensors = [variant["fn"](w) for w in words_raw]

        encoder = StyleEncoder(checkpoint_path=style_ckpt).to(device)
        style_features = encoder.encode(style_tensors)

        t0 = time.monotonic()
        imgs = []
        for w in DEMO_TEXT_WORDS:
            img = generate_word(
                w, unet, vae, tokenizer, style_features,
                uncond_context=uncond_context,
                num_steps=steps, guidance_scale=guidance,
                num_candidates=1, device=device,
                style_reference_imgs=words_raw,
            )
            imgs.append(normalize_font_size(img, w))
        gen_time = time.monotonic() - t0

        imgs = harmonize_words(imgs)
        composed = compose_words(imgs, DEMO_TEXT_WORDS, upscale_factor=1)
        composed_arr = np.array(composed)

        from reforge.compose.layout import compute_word_positions
        positions = compute_word_positions(imgs, DEMO_TEXT_WORDS)

        scores = overall_quality_score(
            composed_arr, word_imgs=imgs, word_positions=positions,
            words=DEMO_TEXT_WORDS, style_reference_imgs=words_raw,
        )

        entry = {
            "variant": vname,
            "description": variant["description"],
            "wall_clock_s": round(gen_time, 2),
            "metrics": {k: round(v, 4) if isinstance(v, float) else v for k, v in scores.items()},
        }
        results.append(entry)

        overall = scores.get("overall", 0)
        fidelity = scores.get("style_fidelity", "n/a")
        print(f"  overall={overall:.3f}  style_fidelity={fidelity}  time={gen_time:.1f}s")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump({"sweep": "preprocess", "results": results}, f, indent=2)
    print(f"\nResults saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
