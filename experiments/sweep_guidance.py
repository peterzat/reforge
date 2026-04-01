"""Sweep guidance scale values at a fixed step count.

Usage:
    python experiments/sweep_guidance.py --style styles/hw-sample.png --steps 30
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
TEST_WORDS = ["Quick", "brown", "foxes", "jump", "high"]
GUIDANCE_VALUES = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "output", "guidance_sweep.json")


def main():
    parser = argparse.ArgumentParser(description="Sweep guidance scale values")
    parser.add_argument("--style", type=str, default="styles/hw-sample.png")
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--device", type=str, default="cuda")
    args = parser.parse_args()

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
    from reforge.preprocess.normalize import preprocess_words
    from reforge.preprocess.segment import segment_sentence_image
    from reforge.quality.font_scale import normalize_font_size
    from reforge.quality.harmonize import harmonize_words

    device = args.device
    num_steps = args.steps

    # Load models once
    style_img = cv2.imread(args.style, cv2.IMREAD_GRAYSCALE)
    if style_img is None:
        raise FileNotFoundError(f"Cannot read: {args.style}")
    words_raw = segment_sentence_image(style_img)
    style_tensors = preprocess_words(words_raw)

    style_ckpt = download_style_encoder_weights()
    encoder = StyleEncoder(checkpoint_path=style_ckpt).to(device)
    style_features = encoder.encode(style_tensors)

    unet_ckpt = download_unet_weights()
    unet = load_unet(unet_ckpt, device=device)
    vae = load_vae(device=device)
    tokenizer = load_tokenizer()

    results = []
    for guidance in GUIDANCE_VALUES:
        print(f"\n--- Guidance={guidance} ---")
        torch.manual_seed(SEED)
        np.random.seed(SEED)

        uncond_context = None
        if guidance != 1.0:
            uncond_context = tokenizer(" ", return_tensors="pt", padding="max_length", max_length=16)

        t0 = time.monotonic()
        imgs = []
        for w in TEST_WORDS:
            img = generate_word(
                w, unet, vae, tokenizer, style_features,
                uncond_context=uncond_context,
                num_steps=num_steps, guidance_scale=guidance,
                num_candidates=1, device=device,
            )
            imgs.append(normalize_font_size(img, w))
        gen_time = time.monotonic() - t0

        imgs = harmonize_words(imgs)
        composed = compose_words(imgs, TEST_WORDS, upscale_factor=1)
        composed_arr = np.array(composed)

        from reforge.compose.layout import compute_word_positions
        positions = compute_word_positions(imgs, TEST_WORDS)

        scores = overall_quality_score(
            composed_arr, word_imgs=imgs, word_positions=positions, words=TEST_WORDS,
        )

        entry = {
            "steps": num_steps,
            "guidance_scale": guidance,
            "candidates": 1,
            "wall_clock_s": round(gen_time, 2),
            "per_word_s": round(gen_time / len(TEST_WORDS), 2),
            "metrics": {k: round(v, 4) if isinstance(v, float) else v for k, v in scores.items()},
        }
        results.append(entry)

        overall = scores.get("overall", 0)
        ocr = scores.get("ocr_accuracy", "n/a")
        print(f"  overall={overall:.3f}  ocr={ocr}  time={gen_time:.1f}s")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump({"sweep": "guidance", "steps": num_steps, "results": results}, f, indent=2)
    print(f"\nResults saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
