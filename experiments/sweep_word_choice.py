"""Evaluate alternative 5-word sentences for style transfer quality.

Tests whether different word choices (maximizing stroke diversity)
improve style transfer fidelity over the default "Quick Brown Foxes Jump High".

The alternative sentences are designed to cover missing strokes:
- 't' (most common letter, distinctive cross-stroke)
- 'a', 'd' (common round+vertical combos)
- 'l' (pure vertical)

Usage:
    python experiments/sweep_word_choice.py --style styles/hw-sample.png
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

# Current default: ascenders (k,h), descenders (p,g), round (o,e), diagonal (x,w,k)
# Missing: t, a, d, l
SENTENCES = {
    "default": ["Quick", "Brown", "Foxes", "Jump", "High"],
    # Covers: t, y, w, z, d, l, k, g, f, u, n, b, r, s
    "alt1": ["Typed", "Waltz", "Funky", "Brisk", "Dodge"],
    # Covers: p, l, a, d, s, w, t, c, h, b, g, r, f
    "alt2": ["Plaid", "Swept", "Chunk", "Bogey", "Draft"],
    # Covers: l, g, h, t, d, z, n, q, f, s, w, p, b, r
    "alt3": ["Light", "Dozen", "Quaff", "Swept", "Brawl"],
}

DEMO_TEXT_WORDS = ["The", "morning", "sun", "cast", "long"]
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "output", "word_choice_sweep.json")


def main():
    parser = argparse.ArgumentParser(description="Sweep word choice for style transfer")
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

    # Load shared models
    unet_ckpt = download_unet_weights()
    unet = load_unet(unet_ckpt, device=device)
    vae = load_vae(device=device)
    tokenizer = load_tokenizer()

    uncond_context = tokenizer(" ", return_tensors="pt", padding="max_length", max_length=16)

    # Load style image and segment (for all sentences, re-segment the same image)
    style_img = cv2.imread(args.style, cv2.IMREAD_GRAYSCALE)
    if style_img is None:
        raise FileNotFoundError(f"Cannot read: {args.style}")

    results = []
    for name, style_words in SENTENCES.items():
        print(f"\n--- Sentence: {name} ({' '.join(style_words)}) ---")

        # For the default sentence, use normal segmentation
        # For alternatives, we'd need photos of those words in the user's handwriting
        # Since we only have hw-sample.png with "Quick Brown Foxes Jump High",
        # we can only test the default. The alternatives require new photos.
        if name != "default":
            print(f"  Skipping (requires new handwriting photo of: {' '.join(style_words)})")
            results.append({
                "name": name,
                "words": style_words,
                "status": "skipped",
                "reason": "requires new handwriting photo",
            })
            continue

        words_raw = segment_sentence_image(style_img)
        if len(words_raw) != 5:
            print(f"  ERROR: got {len(words_raw)} words, expected 5")
            continue
        style_tensors = preprocess_words(words_raw)

        style_ckpt = download_style_encoder_weights()
        encoder = StyleEncoder(checkpoint_path=style_ckpt).to(device)
        style_features = encoder.encode(style_tensors)

        torch.manual_seed(SEED)
        np.random.seed(SEED)

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
            "name": name,
            "words": style_words,
            "status": "completed",
            "wall_clock_s": round(gen_time, 2),
            "metrics": {k: round(v, 4) if isinstance(v, float) else v for k, v in scores.items()},
        }
        results.append(entry)

        overall = scores.get("overall", 0)
        fidelity = scores.get("style_fidelity", "n/a")
        print(f"  overall={overall:.3f}  style_fidelity={fidelity}  time={gen_time:.1f}s")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump({"sweep": "word_choice", "results": results}, f, indent=2)
    print(f"\nResults saved to {OUTPUT_PATH}")
    print("\nNote: alternative sentences require new handwriting photos to test.")
    print("Design candidates for future testing:")
    for name, words in SENTENCES.items():
        if name != "default":
            print(f"  {name}: {' '.join(words)}")


if __name__ == "__main__":
    main()
