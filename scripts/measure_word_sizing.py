"""Diagnostic: per-word ink-height and x-height on the demo.sh sentence.

Generates the demo.sh two-paragraph sentence at a deterministic seed, runs the
pipeline up through the stage that feeds composition (normalize_font_size +
equalize_body_zones), and prints per-word (idx, word, ink_h, x_h) plus the
x_height_spread statistic used by spec 2026-04-19 (body-zone sizing).

x_height_spread = max(x_heights) / min(x_heights) across word tokens that are
alphabetic and >= 2 chars. Contractions (words containing an apostrophe) and
single-char tokens are excluded: contractions are stitched from two DP passes
and are not a stable x-height signal; single-char tokens ("I", "a") are
handled by an independent short-word code path.

No file writes. Paste the stdout into docs/sizing_diagnostic.md.

Usage:
    .venv/bin/python scripts/measure_word_sizing.py [--seed 42]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEMO_TEXT = (
    "I can't remember exactly, but it was a Thursday; the bakery on Birchwood "
    "had croissants so perfect they'd disappear by noon.\n"
    "We grabbed two, maybe three? Katherine laughed and said something "
    "wonderful about mornings being too beautiful for ordinary breakfast."
)
STYLE_PATH = ROOT / "styles" / "hw-sample.png"


def _eligible_for_spread(word: str) -> bool:
    """Alphabetic word of length >= 2 (excludes single-char tokens and contractions)."""
    return word.isalpha() and len(word) >= 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--preset", type=str, default="quality",
        choices=["draft", "fast", "quality"],
    )
    args = parser.parse_args()

    from reforge.config import NUM_STYLE_WORDS, PRESETS
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
    from reforge.quality.font_scale import equalize_body_zones, normalize_font_size
    from reforge.quality.ink_metrics import compute_ink_height, compute_x_height
    from reforge.validation import split_paragraphs, validate_charset

    device = "cuda" if torch.cuda.is_available() else "cpu"
    preset = PRESETS[args.preset]

    validate_charset(DEMO_TEXT)
    paragraphs = split_paragraphs(DEMO_TEXT)

    style_img = cv2.imread(str(STYLE_PATH), cv2.IMREAD_GRAYSCALE)
    if style_img is None:
        raise FileNotFoundError(f"Could not read style image: {STYLE_PATH}")
    word_imgs_raw = segment_sentence_image(style_img)
    if len(word_imgs_raw) != NUM_STYLE_WORDS:
        raise RuntimeError(
            f"Expected {NUM_STYLE_WORDS} style words, got {len(word_imgs_raw)}"
        )
    style_tensors = preprocess_words(word_imgs_raw)

    style_ckpt = download_style_encoder_weights()
    encoder = StyleEncoder(checkpoint_path=style_ckpt).to(device)
    style_features = encoder.encode(style_tensors)

    unet_ckpt = download_unet_weights()
    unet = load_unet(unet_ckpt, device=device)
    vae = load_vae(device=device)
    tokenizer = load_tokenizer()

    uncond_context = None
    if preset["guidance_scale"] != 1.0:
        uncond_context = tokenizer(
            " ", return_tensors="pt", padding="max_length", max_length=16
        )

    from reforge.quality.harmonize import compute_mean_stroke_width

    def _resize_to_canvas_height(img: np.ndarray, target_h: int = 64) -> np.ndarray:
        h, w = img.shape[:2]
        if h <= 0 or w <= 0:
            return img
        scale = target_h / h
        new_h = max(1, int(h * scale))
        new_w = max(1, int(w * scale))
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    style_widths = [
        compute_mean_stroke_width(_resize_to_canvas_height(w)) for w in word_imgs_raw
    ]
    valid_style_widths = [w for w in style_widths if w > 0]
    reference_stroke_width = (
        float(np.median(valid_style_widths)) if valid_style_widths else 0.0
    )

    flat_words: list[str | None] = []
    for i, para in enumerate(paragraphs):
        if i > 0:
            flat_words.append(None)
        for w in para:
            flat_words.append(w)

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    generated: list[np.ndarray | None] = []
    for word in flat_words:
        if word is None:
            generated.append(None)
            continue
        img = generate_word(
            word, unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=preset["steps"],
            guidance_scale=preset["guidance_scale"],
            num_candidates=preset["candidates"],
            device=device,
            style_reference_imgs=word_imgs_raw,
            reference_stroke_width=reference_stroke_width,
        )
        generated.append(img)

    for i, (img, word) in enumerate(zip(generated, flat_words)):
        if img is not None and word is not None:
            generated[i] = normalize_font_size(img, word)

    real_for_xh = [img for img in generated if img is not None]
    equalized = equalize_body_zones(real_for_xh)
    eq_idx = 0
    for i in range(len(generated)):
        if generated[i] is not None:
            generated[i] = equalized[eq_idx]
            eq_idx += 1

    real_words = [w for w in flat_words if w is not None]
    real_images = [img for img in generated if img is not None]

    # --- Print report ---
    print(f"Seed: {args.seed}")
    print(
        f"Preset: {args.preset} "
        f"(steps={preset['steps']}, guidance={preset['guidance_scale']}, "
        f"candidates={preset['candidates']})"
    )
    print(f"Style: {STYLE_PATH.relative_to(ROOT)}")
    print(f"Stage: post normalize_font_size + post equalize_body_zones")
    print()
    print(f"{'idx':>3}  {'word':<20} {'ink_h':>6} {'x_h':>5}")
    rows: list[tuple[int, str, int, int]] = []
    for idx, (word, img) in enumerate(zip(real_words, real_images), start=1):
        ink_h = compute_ink_height(img)
        x_h = compute_x_height(img)
        rows.append((idx, word, ink_h, x_h))
        print(f"{idx:>3}  {word:<20} {ink_h:>6} {x_h:>5}")

    print()
    eligible_rows = [r for r in rows if _eligible_for_spread(r[1])]
    excluded_rows = [r for r in rows if not _eligible_for_spread(r[1])]
    print(
        "Excluded from x_height_spread "
        "(single-char or contains apostrophe):"
    )
    if excluded_rows:
        print("  " + ", ".join(f"{r[1]} (x_h={r[3]})" for r in excluded_rows))
    else:
        print("  (none)")
    print()

    if len(eligible_rows) < 2:
        print("x_height_spread: N/A (need at least 2 eligible words)")
        return 0

    x_heights = [r[3] for r in eligible_rows]
    min_xh = min(x_heights)
    max_xh = max(x_heights)
    spread = max_xh / max(1, min_xh)
    min_word = next(r[1] for r in eligible_rows if r[3] == min_xh)
    max_word = next(r[1] for r in eligible_rows if r[3] == max_xh)

    print(f"x_heights ({len(x_heights)} eligible): {x_heights}")
    print(f"min x_h = {min_xh} ({min_word})")
    print(f"max x_h = {max_xh} ({max_word})")
    print(f"x_height_spread (max/min) = {spread:.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
