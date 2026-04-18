"""Real-font glyph rasterizer for trailing punctuation.

Plan soft-shimmying-parnas Turn 2d (case 1 only). Replaces the Bezier
make_synthetic_mark path for trailing punctuation (comma, period,
semicolon, exclamation, question) with an OFL handwriting-font render.
Does NOT touch contraction right-sides — the mid-word two-hand mismatch
was rejected by the user (case 3).

Design:
- Caveat (OFL) is the default font; configurable via config.py.
- Glyphs are rasterized at a point size derived from the surrounding
  word's body_height, matching how compose/render.py scales the DP word.
- Baseline is computed explicitly from font.getmetrics() so the mark
  aligns cleanly when attached via _attach_mark_to_word (which aligns
  on the bottom-of-ink).
- Returns a grayscale uint8 image shaped so the baseline row is at a
  known y-coordinate; callers that need to co-align with a DP word's
  baseline can read that metadata (or use _attach_mark_to_word, which
  infers from ink bottom).
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _font_for_body_height(font_path: str, body_height: int) -> tuple[ImageFont.FreeTypeFont, int]:
    """Select a point size whose cap-height roughly equals body_height.

    Caveat's cap-to-em ratio (measured empirically from font.getmetrics())
    lands near 0.55. We size so the rendered cap-height matches body_height,
    matching the visual scale of a DP word at the same body_height.
    """
    # Caveat cap-height factor = 0.55 (empirical); 1/0.55 ≈ 1.82.
    # Clamp to a minimum so very small body_heights still render visibly.
    point_size = max(18, int(round(body_height / 0.55)))
    font = ImageFont.truetype(font_path, point_size)
    return font, point_size


def render_trailing_mark(
    mark: str,
    body_height: int,
    ink_intensity: int,
    font_path: str,
    *,
    horizontal_padding_px: int = 2,
) -> np.ndarray:
    """Rasterize a trailing punctuation mark from ``font_path``.

    The returned image has the glyph's visual baseline at row
    ``body_height`` (pre-padding), so that mark images with and without
    descenders (",", ";" vs "." "!" "?") can be vertically stacked and
    co-aligned by that row. Height exceeds body_height when the mark has
    a descender (", ;"), otherwise equals body_height.

    Args:
        mark: single-character punctuation (e.g. ",", ".", ";", "!", "?").
        body_height: target cap-height / x-height in pixels, matched to
            the surrounding DP word's body.
        ink_intensity: target darkest ink value 0-255 (lower = darker).
            Font is rasterized at this intensity directly.
        font_path: path to a TTF file (Caveat or similar).
        horizontal_padding_px: whitespace columns on each side of the
            rasterized glyph (1-2 px is plenty; the attach-step adds
            gap_px on top of this).

    Returns:
        Grayscale uint8 image. White background; mark rendered at
        ``ink_intensity`` over it.
    """
    if len(mark) != 1:
        raise ValueError(f"render_trailing_mark expects single char, got {mark!r}")
    body_height = max(4, int(body_height))
    ink_intensity = max(0, min(255, int(ink_intensity)))

    font, point_size = _font_for_body_height(font_path, body_height)
    ascent, descent = font.getmetrics()

    # PIL's draw.text uses the glyph's logical top as the anchor when
    # given (x, y). Bounding box tells us the visible extent.
    bbox = font.getbbox(mark)
    # bbox is (x0, y0, x1, y1) in draw-coordinate space.
    visible_w = max(1, bbox[2] - bbox[0])
    visible_h = max(1, bbox[3] - bbox[1])

    # Canvas: width covers visible glyph + padding. Height is the full
    # ascent + descent so baseline alignment is explicit.
    canvas_w = visible_w + horizontal_padding_px * 2
    canvas_h = ascent + descent

    img = Image.new("L", (canvas_w, canvas_h), 255)
    draw = ImageDraw.Draw(img)
    # Anchor: draw so that the glyph's visible left edge lands at
    # horizontal_padding_px. bbox[0] is the x-offset of visible left
    # from the logical draw x; subtract it to zero-align.
    draw.text(
        (horizontal_padding_px - bbox[0], 0),
        mark,
        fill=ink_intensity,
        font=font,
    )
    arr = np.array(img, dtype=np.uint8)

    # Tight-crop horizontally to visible ink, keeping the padding.
    col_ink = np.any(arr < 200, axis=0)
    if col_ink.any():
        x0 = max(0, int(np.argmax(col_ink)) - horizontal_padding_px)
        x1 = min(arr.shape[1], len(col_ink) - int(np.argmax(col_ink[::-1])) + horizontal_padding_px)
        arr = arr[:, x0:x1]

    # Trim trailing rows below any descender-less glyph's lowest ink so
    # that a period / exclamation / question comes back body_height-tall.
    # Comma / semicolon retain their below-baseline rows.
    row_ink = np.any(arr < 200, axis=1)
    if row_ink.any():
        ink_bottom = len(row_ink) - 1 - int(np.argmax(row_ink[::-1]))
        # Keep at most (ink_bottom + 1) rows + 1 padding; clips unused ascent
        arr = arr[: min(arr.shape[0], ink_bottom + 2)]

    return arr
