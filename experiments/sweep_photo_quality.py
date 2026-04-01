"""Evaluate photo quality sensitivity for style input.

Tests whether output quality varies significantly with input photo
conditions: resolution, contrast, etc.

Simulates different conditions by degrading the reference photo:
- Original (baseline)
- Downscaled 2x then upscaled back (simulates lower-res camera)
- Reduced contrast (simulates poor lighting)
- Added Gaussian noise (simulates noisy sensor)

Usage:
    python experiments/sweep_photo_quality.py --style styles/hw-sample.png
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
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "output", "photo_quality_sweep.json")


def _degrade_downscale(img):
    """Downscale 2x then upscale back to simulate lower resolution."""
    h, w = img.shape[:2]
    small = cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)


def _degrade_contrast(img):
    """Reduce contrast to simulate poor lighting."""
    return cv2.convertScaleAbs(img, alpha=0.5, beta=128)


def _degrade_noise(img):
    """Add Gaussian noise to simulate noisy sensor."""
    noise = np.random.normal(0, 25, img.shape).astype(np.float32)
    noisy = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    return noisy


def main():
    parser = argparse.ArgumentParser(description="Sweep photo quality sensitivity")
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
    from reforge.preprocess.normalize import preprocess_words
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

    # Load original style image
    original = cv2.imread(args.style, cv2.IMREAD_GRAYSCALE)
    if original is None:
        raise FileNotFoundError(f"Cannot read: {args.style}")

    variants = {
        "original": ("Original photo", original),
        "downscaled": ("Downscaled 2x + upscaled (lower res)", _degrade_downscale(original)),
        "low_contrast": ("Reduced contrast (poor lighting)", _degrade_contrast(original)),
        "noisy": ("Gaussian noise (noisy sensor)", _degrade_noise(original)),
    }

    results = []
    for vname, (desc, style_img) in variants.items():
        print(f"\n--- {vname}: {desc} ---")
        torch.manual_seed(SEED)
        np.random.seed(SEED)

        try:
            words_raw = segment_sentence_image(style_img)
            if len(words_raw) != 5:
                print(f"  WARNING: got {len(words_raw)} words, expected 5. Skipping.")
                results.append({
                    "variant": vname,
                    "description": desc,
                    "status": "failed",
                    "reason": f"segmented {len(words_raw)} words",
                })
                continue
        except Exception as e:
            print(f"  WARNING: segmentation failed: {e}. Skipping.")
            results.append({
                "variant": vname,
                "description": desc,
                "status": "failed",
                "reason": str(e),
            })
            continue

        style_tensors = preprocess_words(words_raw)
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
            "description": desc,
            "status": "completed",
            "wall_clock_s": round(gen_time, 2),
            "metrics": {k: round(v, 4) if isinstance(v, float) else v for k, v in scores.items()},
        }
        results.append(entry)

        overall = scores.get("overall", 0)
        fidelity = scores.get("style_fidelity", "n/a")
        print(f"  overall={overall:.3f}  style_fidelity={fidelity}  time={gen_time:.1f}s")

    # Analyze sensitivity
    completed = [r for r in results if r.get("status") == "completed"]
    if len(completed) >= 2:
        overalls = [r["metrics"]["overall"] for r in completed]
        delta = max(overalls) - min(overalls)
        print(f"\nOverall score range: {min(overalls):.3f} - {max(overalls):.3f} (delta={delta:.3f})")
        if delta > 0.1:
            print("SIGNIFICANT sensitivity to photo quality detected.")
        else:
            print("Output is relatively robust to photo quality variation.")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump({"sweep": "photo_quality", "results": results}, f, indent=2)
    print(f"\nResults saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
