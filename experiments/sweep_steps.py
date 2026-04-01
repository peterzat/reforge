"""Sweep DDIM step counts to find the quality/time knee.

Generates 5 fixed words at each step count with guidance_scale=3.0,
candidates=1, seed=42. Records quality, OCR, stroke weight, and
wall-clock time per step count.

Usage:
    python experiments/sweep_steps.py --style styles/hw-sample.png
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
STEP_VALUES = [10, 15, 20, 30, 40, 50]
GUIDANCE_SCALE = 3.0
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "output", "steps_sweep.json")


def main():
    parser = argparse.ArgumentParser(description="Sweep DDIM step counts")
    parser.add_argument("--style", type=str, default="styles/hw-sample.png")
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

    uncond_context = tokenizer(" ", return_tensors="pt", padding="max_length", max_length=16)

    results = []
    for steps in STEP_VALUES:
        print(f"\n--- Steps={steps} ---")
        torch.manual_seed(SEED)
        np.random.seed(SEED)

        t0 = time.monotonic()
        imgs = []
        for w in TEST_WORDS:
            img = generate_word(
                w, unet, vae, tokenizer, style_features,
                uncond_context=uncond_context,
                num_steps=steps, guidance_scale=GUIDANCE_SCALE,
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
            "steps": steps,
            "guidance_scale": GUIDANCE_SCALE,
            "candidates": 1,
            "wall_clock_s": round(gen_time, 2),
            "per_word_s": round(gen_time / len(TEST_WORDS), 2),
            "metrics": {k: round(v, 4) if isinstance(v, float) else v for k, v in scores.items()},
        }
        results.append(entry)

        overall = scores.get("overall", 0)
        ocr = scores.get("ocr_accuracy", "n/a")
        swc = scores.get("stroke_weight_consistency", "n/a")
        print(f"  overall={overall:.3f}  ocr={ocr}  stroke_weight={swc}  time={gen_time:.1f}s")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump({"sweep": "steps", "results": results}, f, indent=2)
    print(f"\nResults saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
