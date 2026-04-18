"""Smoke test for Turn 2d: render Caveat punctuation marks at body_height=32
and composite each next to a DP-generated word. Decides whether the font
glyphs blend ("handwritten") or read ("printed") against real DP ink —
informs whether the rasterizer needs a morphological-dilate pass before
we commit the implementation.

Throwaway. Output at experiments/output/caveat_smoke/sheet.png.
"""

import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(REPO, "fonts", "Caveat-VariableFont_wght.ttf")
DP_WORD = os.path.join(REPO, "experiments", "output", "cantt_diagnosis", "can_t_1_left.png")
OUT = os.path.join(REPO, "experiments", "output", "caveat_smoke")

MARKS = [",", ".", ";", "!", "?", "'"]
# Reference letters rendered alongside marks so the mark-to-letter ratio
# is visible (otherwise a tiny comma could look right in isolation but
# wrong next to handwritten ink).
REFERENCE_LETTERS = ["t", "a"]


def render_caveat_glyph(char: str, point_size: int, ink_intensity: int = 50) -> np.ndarray:
    """Rasterize a single glyph using Caveat at an explicit point size.
    Output is trimmed to the glyph's tight bounds with small padding.
    """
    font = ImageFont.truetype(FONT, point_size)

    bbox = font.getbbox(char)
    w = max(1, bbox[2] - bbox[0] + 4)
    h = max(1, bbox[3] - bbox[1] + 4)

    img = Image.new("L", (w + 20, h + 20), 255)
    draw = ImageDraw.Draw(img)
    draw.text((10 - bbox[0], 10 - bbox[1]), char, fill=ink_intensity, font=font)

    arr = np.array(img)
    col_ink = np.any(arr < 180, axis=0)
    row_ink = np.any(arr < 180, axis=1)
    if not col_ink.any() or not row_ink.any():
        return arr
    x0 = max(0, int(np.argmax(col_ink)) - 1)
    x1 = min(arr.shape[1], len(col_ink) - int(np.argmax(col_ink[::-1])) + 1)
    y0 = max(0, int(np.argmax(row_ink)) - 1)
    y1 = min(arr.shape[0], len(row_ink) - int(np.argmax(row_ink[::-1])) + 1)
    return arr[y0:y1, x0:x1]


def main():
    os.makedirs(OUT, exist_ok=True)

    dp_word = cv2.imread(DP_WORD, cv2.IMREAD_GRAYSCALE)
    if dp_word is None:
        print(f"DP sample missing: {DP_WORD}. Run diagnose_contraction.py first.", file=sys.stderr)
        sys.exit(1)

    # Tight-crop the DP word for composition
    col_has_ink = np.any(dp_word < 180, axis=0)
    x_first = int(np.argmax(col_has_ink))
    x_last = int(len(col_has_ink) - int(np.argmax(col_has_ink[::-1])))
    dp_crop = dp_word[:, max(0, x_first - 2):min(dp_word.shape[1], x_last + 2)]

    # Measure DP ink stats for our rasterizer
    ink_pixels = dp_crop[dp_crop < 180]
    dp_ink_median = int(np.median(ink_pixels)) if len(ink_pixels) > 0 else 50

    # Match Caveat's cap-height to the DP word's ink height. Caveat's
    # cap-height is roughly 55% of the point size in pixels. So for a
    # target letter height of ~dp_height, point_size ≈ dp_height / 0.55.
    dp_h = dp_crop.shape[0]
    point_size = max(30, int(dp_h / 0.55))

    rows = []
    # Reference row: Caveat letter(s) alone, so marks can be compared to
    # Caveat's own letter-mark ratio, not just raw letters-vs-marks.
    ref_glyphs = [render_caveat_glyph(c, point_size, ink_intensity=dp_ink_median) for c in REFERENCE_LETTERS]
    h_max = max(g.shape[0] for g in ref_glyphs)
    def _pad_to(img, h):
        if img.shape[0] >= h:
            return img
        pad = h - img.shape[0]
        return cv2.copyMakeBorder(img, pad, 0, 0, 0, cv2.BORDER_CONSTANT, value=255)
    gap = 255 * np.ones((h_max, 10), dtype=np.uint8)
    ref_padded = [_pad_to(g, h_max) for g in ref_glyphs]
    ref_row_content = np.concatenate([r for pair in zip(ref_padded, [gap] * len(ref_padded)) for r in pair][:-1], axis=1)
    label_h = 18
    label = 255 * np.ones((label_h, ref_row_content.shape[1]), dtype=np.uint8)
    cv2.putText(label, f"Caveat ref letters (pt {point_size})", (4, 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, 80, 1, cv2.LINE_AA)
    rows.append(np.concatenate([label, ref_row_content], axis=0))

    for mark in MARKS:
        glyph = render_caveat_glyph(mark, point_size, ink_intensity=dp_ink_median)

        # Pad vertically so DP word and glyph share a canvas height.
        # Pad at top — glyphs hang from the baseline which aligns to the
        # DP word's visual bottom.
        row_h = max(dp_crop.shape[0], glyph.shape[0])
        dp_padded = _pad_to(dp_crop.copy(), row_h)
        glyph_padded = _pad_to(glyph, row_h)
        row_gap = 255 * np.ones((row_h, 8), dtype=np.uint8)
        row = np.concatenate([dp_padded, row_gap, glyph_padded], axis=1)

        # Label the row with the mark
        row_label_h = 18
        row_label = 255 * np.ones((row_label_h, row.shape[1]), dtype=np.uint8)
        cv2.putText(
            row_label, f"mark: {mark}", (4, 14),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, 80, 1, cv2.LINE_AA,
        )
        rows.append(np.concatenate([row_label, row], axis=0))

    max_w = max(r.shape[1] for r in rows)
    padded_rows = [
        cv2.copyMakeBorder(r, 0, 0, 0, max_w - r.shape[1], cv2.BORDER_CONSTANT, value=255)
        for r in rows
    ]
    gap = 255 * np.ones((12, max_w), dtype=np.uint8)
    stacked = []
    for p in padded_rows:
        stacked.append(p)
        stacked.append(gap)
    sheet = np.concatenate(stacked[:-1], axis=0)

    sheet_path = os.path.join(OUT, "sheet.png")
    cv2.imwrite(sheet_path, sheet)
    print(f"Sheet: {sheet_path}")
    print(f"DP word height: {dp_h}px  (ink intensity median {dp_ink_median})")
    print(f"Caveat glyphs rasterized at point size {point_size}")


if __name__ == "__main__":
    main()
