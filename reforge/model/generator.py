"""Word generation: DDIM sampling with CFG, best-of-N, chunking, stitching, postprocessing.

Implements all five gray-box defense layers in postprocessing.
"""

import warnings

import numpy as np
import torch

warnings.filterwarnings("ignore", message=".*model-agnostic default.*max_length.*")
import torch.nn.functional as F

from reforge.config import (
    BACKGROUND_PERCENTILE,
    BODY_ZONE_BOTTOM,
    BODY_ZONE_INK_THRESHOLD,
    BODY_ZONE_TOP,
    CC_BOUNDARY_BONUS,
    CLUSTER_GAP_PX,
    COMPOSITOR_INK_THRESHOLD,
    CONSONANT_PENALTY,
    CV_BOUNDARY_BONUS,
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
    DEFAULT_DDIM_STEPS,
    DEFAULT_GUIDANCE_SCALE,
    DEFAULT_NUM_CANDIDATES,
    HALO_DILATE_RADIUS,
    HALO_GRAY_THRESHOLD,
    INK_THRESHOLD_RATIO,
    MAX_CANVAS_WIDTH,
    MAX_WORD_LENGTH,
    MIN_CHUNK_CHARS,
    OCR_SELECTION_WEIGHT,
    STITCH_OVERLAP_PX,
    VAE_SCALE_FACTOR,
    WIDTH_MULTIPLE,
)

VOWELS = set("aeiouAEIOU")
CONSONANTS = set("bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ")


# --- Contraction splitting ---

def is_contraction(word: str) -> bool:
    """Check if a word is a contraction containing an apostrophe.

    Returns True for words like "can't", "don't", "it's", "they'd",
    "Katherine's". The apostrophe must be internal (not at start/end)
    and both sides must contain at least one letter.
    """
    if "'" not in word:
        return False
    idx = word.index("'")
    left = word[:idx]
    right = word[idx + 1:]
    return len(left) >= 1 and len(right) >= 1 and left[-1].isalpha() and right[0].isalpha()


def split_contraction(word: str) -> tuple[str, str]:
    """Split a contraction at the first apostrophe, keeping the mark on the right.

    Returns (left, right) where word == left + right and right starts with "'".
    E.g. "can't" -> ("can", "'t"), "Katherine's" -> ("Katherine", "'s").
    """
    idx = word.index("'")
    return word[:idx], word[idx:]


def _bezier_point(t: float, p0, p1, p2, p3):
    """Evaluate a cubic Bezier curve at parameter t in [0, 1]."""
    u = 1 - t
    return (
        u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
        u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1],
    )


def _rasterize_bezier_stroke(
    img: np.ndarray,
    p0, p1, p2, p3,
    ink_intensity: int,
    width_start: float,
    width_end: float,
    n_samples: int = 40,
):
    """Rasterize a cubic Bezier curve as a tapered stroke onto img.

    The stroke width interpolates linearly from width_start to width_end
    along the curve. Each sample point fills a circular region.
    """
    import cv2

    for i in range(n_samples + 1):
        t = i / n_samples
        x, y = _bezier_point(t, p0, p1, p2, p3)
        ix, iy = int(round(x)), int(round(y))
        radius = width_start + (width_end - width_start) * t
        # Intensity fades toward stroke ends for a natural feel
        fade = 1.0 - 0.3 * abs(t - 0.5) * 2  # lightest at tips
        intensity = int(ink_intensity + (200 - ink_intensity) * (1.0 - fade) * 0.4)
        intensity = min(190, max(ink_intensity, intensity))
        r = max(0.5, radius)
        ri = int(round(r))
        for dy in range(-ri, ri + 1):
            for dx in range(-ri, ri + 1):
                if dx * dx + dy * dy <= r * r:
                    px, py = ix + dx, iy + dy
                    if 0 <= py < img.shape[0] and 0 <= px < img.shape[1]:
                        img[py, px] = min(img[py, px], intensity)


def _rasterize_dot(
    img: np.ndarray,
    cx: float,
    cy: float,
    radius: float,
    ink_intensity: int,
):
    """Rasterize a filled dot (period, part of !, ?, ;) onto img."""
    ri = int(round(radius))
    ix, iy = int(round(cx)), int(round(cy))
    for dy in range(-ri - 1, ri + 2):
        for dx in range(-ri - 1, ri + 2):
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= radius:
                px, py = ix + dx, iy + dy
                if 0 <= py < img.shape[0] and 0 <= px < img.shape[1]:
                    # Slight antialiasing at edge
                    if dist > radius - 0.8:
                        edge_blend = (radius - dist) / 0.8
                        val = int(ink_intensity + (255 - ink_intensity) * (1.0 - edge_blend))
                    else:
                        val = ink_intensity
                    img[py, px] = min(img[py, px], val)


# Trailing punctuation marks that can be synthesized
SYNTHETIC_MARKS = {",", ".", "?", "!", ";"}
# All marks handled by the synthetic system (including apostrophe from contraction path)
ALL_SYNTHETIC_MARKS = SYNTHETIC_MARKS | {"'"}


def make_synthetic_mark(mark: str, ink_intensity: int, body_height: int) -> np.ndarray:
    """Render a synthetic punctuation mark using Bezier curves.

    Supports: comma, period, question mark, exclamation mark, semicolon.
    Each mark is built from 1-3 Bezier curves and/or dots, parameterized
    by ink_intensity and body_height. The returned image is body_height
    tall with the mark positioned at the correct baseline-relative offset.

    Args:
        mark: One of ',', '.', '?', '!', ';'
        ink_intensity: Median ink pixel value (0=black, 255=white).
        body_height: Approximate x-height of surrounding text in pixels.

    Returns:
        Grayscale uint8 image on white background. The image height equals
        body_height (plus descender space for comma/semicolon). The mark is
        positioned relative to the baseline (bottom of body zone).
    """
    if mark not in SYNTHETIC_MARKS:
        raise ValueError(f"Unsupported mark: {mark!r}. Supported: {SYNTHETIC_MARKS}")

    body_height = max(8, body_height)
    ink_intensity = max(10, min(200, ink_intensity))

    # Stroke width and dot radius proportional to body height.
    # These must be large enough to survive 2x upscale in composition.
    # At body_h=21 (typical), stroke_w=2.5, dot_radius=3.4.
    stroke_w = max(1.5, body_height * 0.12)
    dot_radius = max(2.0, body_height * 0.16)

    if mark == ".":
        return _make_period(ink_intensity, body_height, dot_radius)
    elif mark == ",":
        return _make_comma(ink_intensity, body_height, stroke_w, dot_radius)
    elif mark == "!":
        return _make_exclamation(ink_intensity, body_height, stroke_w, dot_radius)
    elif mark == "?":
        return _make_question(ink_intensity, body_height, stroke_w, dot_radius)
    elif mark == ";":
        return _make_semicolon(ink_intensity, body_height, stroke_w, dot_radius)
    else:
        raise ValueError(f"Unsupported mark: {mark!r}")


def _make_period(ink_intensity: int, body_height: int, dot_radius: float) -> np.ndarray:
    """Period: single dot at baseline."""
    img_w = max(6, int(dot_radius * 2 + 6))
    img_h = body_height
    img = np.full((img_h, img_w), 255, dtype=np.uint8)
    cx = img_w / 2
    # Baseline is at the bottom of the body zone
    cy = body_height - dot_radius - 1
    _rasterize_dot(img, cx, cy, dot_radius, ink_intensity)
    return img


def _make_comma(ink_intensity: int, body_height: int, stroke_w: float, dot_radius: float) -> np.ndarray:
    """Comma: dot at baseline + tapered curve descending below."""
    descender = max(4, int(body_height * 0.35))
    img_w = max(7, int(dot_radius * 2 + 8))
    img_h = body_height + descender
    img = np.full((img_h, img_w), 255, dtype=np.uint8)

    cx = img_w / 2
    baseline_y = body_height - 1

    # Dot at baseline
    _rasterize_dot(img, cx, baseline_y - dot_radius, dot_radius * 0.8, ink_intensity)

    # Tapered curve from dot downward-left
    p0 = (cx, baseline_y)
    p1 = (cx + dot_radius * 0.3, baseline_y + descender * 0.4)
    p2 = (cx - dot_radius * 0.5, baseline_y + descender * 0.7)
    p3 = (cx - dot_radius * 0.8, baseline_y + descender * 0.9)
    _rasterize_bezier_stroke(img, p0, p1, p2, p3, ink_intensity, stroke_w, stroke_w * 0.3)
    return img


def _make_exclamation(ink_intensity: int, body_height: int, stroke_w: float, dot_radius: float) -> np.ndarray:
    """Exclamation: tapered vertical stroke from top to near-baseline + dot at baseline."""
    img_w = max(7, int(dot_radius * 2 + 8))
    img_h = body_height
    img = np.full((img_h, img_w), 255, dtype=np.uint8)

    cx = img_w / 2
    baseline_y = body_height - 1

    # Vertical stroke from top down to 70% of body height
    top_y = max(1, int(body_height * 0.05))
    stroke_end_y = int(body_height * 0.70)

    p0 = (cx, top_y)
    p1 = (cx + 0.3, top_y + (stroke_end_y - top_y) * 0.33)
    p2 = (cx - 0.2, top_y + (stroke_end_y - top_y) * 0.66)
    p3 = (cx, stroke_end_y)
    _rasterize_bezier_stroke(img, p0, p1, p2, p3, ink_intensity, stroke_w * 1.2, stroke_w * 0.5)

    # Dot near baseline
    dot_y = baseline_y - dot_radius - 0.5
    _rasterize_dot(img, cx, dot_y, dot_radius, ink_intensity)
    return img


def _make_question(ink_intensity: int, body_height: int, stroke_w: float, dot_radius: float) -> np.ndarray:
    """Question mark: open curve at top + short vertical stroke + dot at baseline."""
    img_w = max(9, int(body_height * 0.5 + 6))
    img_h = body_height
    img = np.full((img_h, img_w), 255, dtype=np.uint8)

    cx = img_w / 2
    baseline_y = body_height - 1

    # Open curve (the hook): from upper-left, arcing right and down
    hook_top = max(1, int(body_height * 0.05))
    hook_bottom = int(body_height * 0.55)
    hook_w = img_w * 0.35

    p0 = (cx - hook_w * 0.5, hook_top + (hook_bottom - hook_top) * 0.2)
    p1 = (cx + hook_w * 0.3, hook_top - body_height * 0.05)
    p2 = (cx + hook_w * 0.8, hook_top + (hook_bottom - hook_top) * 0.5)
    p3 = (cx, hook_bottom)
    _rasterize_bezier_stroke(img, p0, p1, p2, p3, ink_intensity, stroke_w * 0.8, stroke_w * 1.0)

    # Short vertical segment from hook bottom toward baseline
    vert_end = int(body_height * 0.72)
    p0v = (cx, hook_bottom)
    p1v = (cx + 0.2, hook_bottom + (vert_end - hook_bottom) * 0.5)
    p2v = (cx - 0.1, vert_end - 1)
    p3v = (cx, vert_end)
    _rasterize_bezier_stroke(img, p0v, p1v, p2v, p3v, ink_intensity, stroke_w * 0.9, stroke_w * 0.4)

    # Dot near baseline
    dot_y = baseline_y - dot_radius - 0.5
    _rasterize_dot(img, cx, dot_y, dot_radius, ink_intensity)
    return img


def _make_semicolon(ink_intensity: int, body_height: int, stroke_w: float, dot_radius: float) -> np.ndarray:
    """Semicolon: dot above mid-body + comma below baseline."""
    descender = max(4, int(body_height * 0.30))
    img_w = max(7, int(dot_radius * 2 + 8))
    img_h = body_height + descender
    img = np.full((img_h, img_w), 255, dtype=np.uint8)

    cx = img_w / 2
    baseline_y = body_height - 1

    # Upper dot at ~40% of body height
    upper_dot_y = int(body_height * 0.40)
    _rasterize_dot(img, cx, upper_dot_y, dot_radius, ink_intensity)

    # Lower part: dot at baseline + comma tail
    _rasterize_dot(img, cx, baseline_y - dot_radius, dot_radius * 0.8, ink_intensity)

    # Comma tail from baseline downward
    p0 = (cx, baseline_y)
    p1 = (cx + dot_radius * 0.2, baseline_y + descender * 0.35)
    p2 = (cx - dot_radius * 0.4, baseline_y + descender * 0.65)
    p3 = (cx - dot_radius * 0.7, baseline_y + descender * 0.85)
    _rasterize_bezier_stroke(img, p0, p1, p2, p3, ink_intensity, stroke_w, stroke_w * 0.3)
    return img


def _render_trailing_mark_or_fallback(
    mark: str,
    ink_intensity: int,
    body_height: int,
) -> np.ndarray:
    """Render a trailing punctuation mark via the OFL font when configured,
    falling back to the synthetic Bezier renderer when unconfigured or on
    rasterization error.

    Plan Turn 2d: uses ``PUNCTUATION_GLYPH_FALLBACK_FONT`` from config.py.
    None disables. Missing font file logs a warning and falls back to
    Bezier so the pipeline never hard-fails on a missing asset.
    """
    import logging
    import os

    from reforge.config import PUNCTUATION_GLYPH_FALLBACK_FONT

    log = logging.getLogger("reforge.generator")

    if PUNCTUATION_GLYPH_FALLBACK_FONT is None:
        return make_synthetic_mark(mark, ink_intensity, body_height)

    font_path = PUNCTUATION_GLYPH_FALLBACK_FONT
    if not os.path.isabs(font_path):
        repo_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        font_path = os.path.join(repo_root, font_path)
    if not os.path.exists(font_path):
        log.warning(
            "PUNCTUATION_GLYPH_FALLBACK_FONT=%r not found; falling back to Bezier mark",
            PUNCTUATION_GLYPH_FALLBACK_FONT,
        )
        return make_synthetic_mark(mark, ink_intensity, body_height)

    try:
        from reforge.model.font_glyph import render_trailing_mark
        return render_trailing_mark(mark, body_height, ink_intensity, font_path)
    except (OSError, ValueError) as e:
        log.warning(
            "font glyph rasterization failed for %r: %s; falling back to Bezier mark",
            mark, e,
        )
        return make_synthetic_mark(mark, ink_intensity, body_height)


# --- Contraction chunk matching ---

# Spec 2026-04-19: contraction right-side sizing. After the W split, the
# 2-char right chunk ("'t", "'s", "'d") is below IAM's MIN_WORD_CHARS=4
# training filter and DP renders it with noticeably lighter stroke and
# smaller ink height than the left chunk. `_match_chunk_to_reference`
# rescales and dilates the shorter/thinner chunk so the two halves stitch
# together without a visible sizing discontinuity.
CHUNK_MIN_HEIGHT_RATIO = 0.85  # right ink height must be >= this * left's
CHUNK_MIN_STROKE_RATIO = 0.85  # right stroke width must be >= this * left's
CHUNK_MAX_UPSCALE = 1.8  # never blow the shorter chunk up more than this
CHUNK_MAX_DILATE_ITER = 6  # cap on grayscale-erode iterations


def _match_chunk_to_reference(
    adjust_img: np.ndarray,
    reference_img: np.ndarray,
) -> np.ndarray:
    """Scale + dilate ``adjust_img`` so its ink height and stroke width
    come within CHUNK_MIN_*_RATIO of ``reference_img``.

    Bounded: scale is clamped to CHUNK_MAX_UPSCALE and dilation to
    CHUNK_MAX_DILATE_ITER iterations. Reference image is left unchanged.
    Returns ``adjust_img`` unchanged when either side has too little ink
    for a reliable measurement.
    """
    INK_THRESH = 180

    def _ink_height(img: np.ndarray) -> int:
        rows = np.any(img < INK_THRESH, axis=1)
        if not rows.any():
            return 0
        first = int(np.argmax(rows))
        last = len(rows) - 1 - int(np.argmax(rows[::-1]))
        return last - first + 1

    def _stroke(img: np.ndarray) -> float:
        import cv2
        mask = (img < INK_THRESH).astype(np.uint8)
        if int(mask.sum()) < 10:
            return 0.0
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
        ink_dists = dist[mask > 0]
        if ink_dists.size == 0:
            return 0.0
        return 2.0 * float(np.mean(ink_dists))

    import cv2

    ref_h = _ink_height(reference_img)
    adj_h = _ink_height(adjust_img)
    if ref_h == 0 or adj_h == 0:
        return adjust_img

    out = adjust_img
    # Step 1: height match via isotropic upscale.
    height_ratio = adj_h / ref_h
    if height_ratio < CHUNK_MIN_HEIGHT_RATIO:
        target_scale = min(ref_h / adj_h, CHUNK_MAX_UPSCALE)
        new_h = max(1, int(round(out.shape[0] * target_scale)))
        new_w = max(1, int(round(out.shape[1] * target_scale)))
        out = cv2.resize(out, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    def _shift_ink_toward(img, target_ink_median):
        ink_pixels = img[img < INK_THRESH]
        if ink_pixels.size == 0:
            return img
        cur_median = float(np.median(ink_pixels))
        if abs(target_ink_median - cur_median) < 5.0:
            return img
        shift = target_ink_median - cur_median
        mask = img < INK_THRESH
        shifted = img.astype(np.float32)
        shifted[mask] += shift
        return np.clip(shifted, 0, 255).astype(np.uint8)

    ref_ink_pixels = reference_img[reference_img < INK_THRESH]
    ref_ink = float(np.median(ref_ink_pixels)) if ref_ink_pixels.size > 0 else None

    # Step 2: ink intensity pre-shift. Moving ink pixels toward the
    # reference median before dilation lets the erode step operate on
    # already-matched intensities; otherwise the min-filter behavior of
    # erode on the original (wrong-intensity) pixels leaks back into the
    # dilated output.
    if ref_ink is not None:
        out = _shift_ink_toward(out, ref_ink)

    # Step 3: stroke match via bounded grayscale erosion.
    ref_stroke = _stroke(reference_img)
    cur_stroke = _stroke(out)
    if ref_stroke > 0 and cur_stroke > 0:
        ratio = cur_stroke / ref_stroke
        if ratio < CHUNK_MIN_STROKE_RATIO:
            target = ref_stroke * CHUNK_MIN_STROKE_RATIO
            kernel_3 = np.ones((3, 3), dtype=np.uint8)
            kernel_5 = np.ones((5, 5), dtype=np.uint8)
            for _ in range(CHUNK_MAX_DILATE_ITER):
                out = cv2.erode(out, kernel_3, iterations=1)
                if _stroke(out) >= target:
                    break
            else:
                for _ in range(2):
                    out = cv2.erode(out, kernel_5, iterations=1)
                    if _stroke(out) >= target:
                        break

    # Step 4: ink intensity post-shift. Erode's min-filter pulls in the
    # darkest pixel in each kernel window, so the post-dilate median
    # drifts darker even after the pre-shift. Re-match to pull the
    # post-dilate median back to the reference.
    if ref_ink is not None:
        out = _shift_ink_toward(out, ref_ink)

    return out


def stitch_contraction(
    left_img: np.ndarray,
    right_img: np.ndarray,
) -> np.ndarray:
    """Stitch a contraction as [left] [right], aligned by ink bottom (baseline).

    The right part is expected to already contain the apostrophe as part of
    its rendered image (spec 2026-04-18 Option W); no synthetic mark is
    inserted between the parts.
    """
    INK_THRESH = 180

    def _ink_bottom(img):
        ink_rows = np.any(img < INK_THRESH, axis=1)
        if not np.any(ink_rows):
            return 0
        return img.shape[0] - 1 - int(np.argmax(ink_rows[::-1]))

    def _tight_crop_h(img, pad_px=1):
        """Tight horizontal crop to ink bounds with configurable padding."""
        col_has_ink = np.any(img < INK_THRESH, axis=0)
        if not np.any(col_has_ink):
            return img
        left = max(0, int(np.argmax(col_has_ink)) - pad_px)
        right = min(img.shape[1] - 1, len(col_has_ink) - 1 - int(np.argmax(col_has_ink[::-1])) + pad_px)
        return img[:, left:right + 1]

    left_img = _tight_crop_h(left_img)
    right_img = _tight_crop_h(right_img)

    parts = [left_img, right_img]
    bottoms = [_ink_bottom(p) for p in parts]

    max_bottom = max(bottoms)
    max_h = max(
        p.shape[0] + (max_bottom - b) for p, b in zip(parts, bottoms)
    )

    aligned = []
    for p, b in zip(parts, bottoms):
        bottom_pad = max_bottom - b
        if bottom_pad > 0:
            pad = np.full((bottom_pad, p.shape[1]), 255, dtype=np.uint8)
            p = np.vstack([p, pad])
        if p.shape[0] < max_h:
            top_pad = np.full((max_h - p.shape[0], p.shape[1]), 255, dtype=np.uint8)
            p = np.vstack([top_pad, p])
        aligned.append(p)

    gap = np.full((max_h, 1), 255, dtype=np.uint8)
    return np.hstack([aligned[0], gap, aligned[1]])


# --- Syllable splitting ---

def score_split(word: str, pos: int) -> float:
    """Score a split position in a word.

    Considers:
    - Balance: prefer equal-length chunks
    - Consonant penalty: -3 if >= 3 trailing consonants in left chunk
    - Boundary bonus: +2 for CC boundary, +1 for CV boundary
    """
    left, right = word[:pos], word[pos:]
    if len(left) < MIN_CHUNK_CHARS or len(right) < MIN_CHUNK_CHARS:
        return -999

    # Balance score: prefer equal halves
    balance = 1.0 - abs(len(left) - len(right)) / len(word)

    # Consonant cluster penalty
    trailing_consonants = 0
    for c in reversed(left):
        if c in CONSONANTS:
            trailing_consonants += 1
        else:
            break
    consonant_score = CONSONANT_PENALTY if trailing_consonants >= 3 else 0

    # Boundary bonus
    boundary_score = 0
    if pos > 0 and pos < len(word):
        left_char = word[pos - 1]
        right_char = word[pos]
        if left_char in CONSONANTS and right_char in CONSONANTS:
            boundary_score = CC_BOUNDARY_BONUS
        elif left_char in CONSONANTS and right_char in VOWELS:
            boundary_score = CV_BOUNDARY_BONUS

    return balance * 10 + consonant_score + boundary_score


def split_long_word(word: str) -> list[str]:
    """Split a long word into chunks using score-based syllable splitting.

    Each chunk is guaranteed to be >= MIN_CHUNK_CHARS characters.
    """
    if len(word) <= MAX_WORD_LENGTH:
        return [word]

    # Find best split point
    best_pos = None
    best_score = -999
    for pos in range(MIN_CHUNK_CHARS, len(word) - MIN_CHUNK_CHARS + 1):
        s = score_split(word, pos)
        if s > best_score:
            best_score = s
            best_pos = pos

    if best_pos is None:
        # Cannot split while maintaining minimum chunk size
        return [word]

    left = word[:best_pos]
    right = word[best_pos:]

    # Recursively split if chunks are still too long
    chunks = []
    if len(left) > MAX_WORD_LENGTH:
        chunks.extend(split_long_word(left))
    else:
        chunks.append(left)

    if len(right) > MAX_WORD_LENGTH:
        chunks.extend(split_long_word(right))
    else:
        chunks.append(right)

    return chunks


# --- Adaptive canvas width ---

def compute_canvas_width(word_len: int) -> int:
    """Compute canvas width based on word length, up to MAX_CANVAS_WIDTH."""
    if word_len <= 8:
        width = DEFAULT_CANVAS_WIDTH
    else:
        # Scale linearly from 256 to 320 for 8-10 char words
        ratio = min((word_len - 8) / 2, 1.0)
        width = int(DEFAULT_CANVAS_WIDTH + ratio * (MAX_CANVAS_WIDTH - DEFAULT_CANVAS_WIDTH))
    # Round up to multiple of WIDTH_MULTIPLE
    width = ((width + WIDTH_MULTIPLE - 1) // WIDTH_MULTIPLE) * WIDTH_MULTIPLE
    return min(width, MAX_CANVAS_WIDTH)


# --- Postprocessing: 5 gray-box defense layers ---

def adaptive_background_estimate(img: np.ndarray) -> float:
    """Layer 1: 90th-percentile pixel value as background estimate."""
    return float(np.percentile(img, BACKGROUND_PERCENTILE))


def apply_ink_threshold(img: np.ndarray, bg_estimate: float) -> np.ndarray:
    """Create ink mask using adaptive threshold at 70% of background estimate."""
    threshold = bg_estimate * INK_THRESHOLD_RATIO
    ink_mask = img < threshold
    return ink_mask


def body_zone_noise_removal(img: np.ndarray, ink_mask: np.ndarray) -> np.ndarray:
    """Layer 2: Blank columns without sufficient body-zone ink.

    Uses connected-component analysis on strong ink (< 128) to preserve
    columns that are part of the same character as body-zone-valid columns,
    even if those specific columns lack body-zone ink (e.g. crossbar of "T",
    ascenders of "t", "l"). Uses strong ink for connectivity to avoid
    chaining through diffusion noise.
    """
    import cv2

    h, w = img.shape[:2]
    body_top = int(h * BODY_ZONE_TOP)
    body_bottom = int(h * BODY_ZONE_BOTTOM)
    body_zone = ink_mask[body_top:body_bottom, :]

    col_ink_ratio = np.mean(body_zone, axis=0)
    valid_cols = col_ink_ratio >= BODY_ZONE_INK_THRESHOLD

    # Use strong ink (< 128) for connected-component analysis to avoid
    # gray noise chaining into large components
    strong_ink = (img < 128).astype(np.uint8) * 255
    num_labels, labels = cv2.connectedComponents(strong_ink)

    # Find which components touch body-zone-valid columns
    preserved_labels = set()
    for c in range(w):
        if valid_cols[c]:
            col_labels = labels[:, c]
            preserved_labels.update(col_labels[col_labels > 0])

    # Build mask of columns to preserve: body-zone valid OR part of a
    # preserved component
    preserved_cols = valid_cols.copy()
    if preserved_labels:
        labels_arr = np.array(list(preserved_labels))
        for c in range(w):
            if not preserved_cols[c]:
                col_labels = labels[:, c]
                if np.any(np.isin(col_labels, labels_arr)):
                    preserved_cols[c] = True

    result = img.copy()
    for c in range(w):
        if not preserved_cols[c]:
            result[:, c] = 255
    return result


def isolated_cluster_filter(img: np.ndarray, ink_mask: np.ndarray = None) -> np.ndarray:
    """Layer 3: Discard ink clusters separated by large gaps from main cluster.

    Uses a lenient threshold (< 230) for column presence so faint
    inter-letter strokes bridge gaps that the stricter ink_mask misses.
    Clusters are merged transitively: if A is near B and B is near C,
    all three form one group, even if A is far from C. Only truly
    isolated groups (no neighbor within CLUSTER_GAP_PX) are removed.
    """
    h, w = img.shape[:2]

    # Lenient column presence: any pixel below 230 counts, not just
    # the adaptive ink threshold. DiffusionPen generates faint gray
    # (160-200) between letters that should bridge gaps.
    col_has_ink = np.any(img < 230, axis=0)

    # Find connected runs of ink columns
    clusters = []
    start = None
    for c in range(w):
        if col_has_ink[c] and start is None:
            start = c
        elif not col_has_ink[c] and start is not None:
            clusters.append((start, c))
            start = None
    if start is not None:
        clusters.append((start, w))

    if len(clusters) <= 1:
        return img

    # Transitive merge: group clusters where neighbors are within gap threshold
    groups = []  # list of lists of cluster indices
    current_group = [0]
    for i in range(1, len(clusters)):
        prev_end = clusters[i - 1][1]
        curr_start = clusters[i][0]
        gap = curr_start - prev_end
        if gap < CLUSTER_GAP_PX:
            current_group.append(i)
        else:
            groups.append(current_group)
            current_group = [i]
    groups.append(current_group)

    if len(groups) <= 1:
        return img

    # Find the main group (most total ink columns) and preserve any group
    # with significant ink.  Punctuated words ("can't", "it's") produce a
    # gap at the apostrophe; the fragment after it is real content, not noise.
    def group_ink_width(group):
        return sum(clusters[i][1] - clusters[i][0] for i in group)

    total_ink_cols = sum(group_ink_width(g) for g in groups)
    main_group_idx = max(range(len(groups)), key=lambda g: group_ink_width(groups[g]))

    # Minimum fraction of total ink a group must contain to be preserved
    MIN_GROUP_INK_FRACTION = 0.15

    result = img.copy()
    for g_idx, group in enumerate(groups):
        if g_idx == main_group_idx:
            continue
        # Preserve groups with significant ink (not isolated noise)
        if total_ink_cols > 0 and group_ink_width(group) / total_ink_cols >= MIN_GROUP_INK_FRACTION:
            continue
        for ci in group:
            cs, ce = clusters[ci]
            result[:, cs:ce] = 255

    return result


def _word_gray_cleanup(img: np.ndarray) -> np.ndarray:
    """Remove gray fringe pixels not adjacent to strong ink at word level.

    Similar to halo_cleanup but operates on the raw 64x256 word image
    before composition, using a smaller dilation radius suited to the
    smaller pixel scale.
    """
    import cv2

    strong_ink = img < 128
    if not np.any(strong_ink):
        return img

    strong_ink_uint8 = strong_ink.astype(np.uint8) * 255
    # Smaller dilation for word-level (2px vs 4px for halo_cleanup)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    dilated = cv2.dilate(strong_ink_uint8, kernel)
    near_ink = dilated > 0

    result = img.copy()
    # Only clean mid-to-light gray (160-220), preserving darker gray near ink
    # boundaries that metrics count as ink (< 180)
    gray_pixels = (img >= 160) & (img < 220)
    cleanup_mask = gray_pixels & ~near_ink
    result[cleanup_mask] = 255
    return result


def postprocess_word(img: np.ndarray) -> np.ndarray:
    """Apply all 5 gray-box defense layers to a generated word image.

    Args:
        img: Grayscale uint8 word image from VAE decode.

    Returns:
        Cleaned grayscale uint8 image.
    """
    # Layer 1: Adaptive background estimation
    bg_estimate = adaptive_background_estimate(img)
    ink_mask = apply_ink_threshold(img, bg_estimate)

    # Layer 2: Body-zone noise removal
    img = body_zone_noise_removal(img, ink_mask)

    # Recompute ink mask after layer 2
    ink_mask = apply_ink_threshold(img, bg_estimate)

    # Layer 3: Isolated cluster filtering
    img = isolated_cluster_filter(img, ink_mask)

    # Layer 3b: Word-level gray fringe cleanup
    # Remove gray pixels (128-220) not adjacent to strong ink (< 128)
    img = _word_gray_cleanup(img)

    # Layer 4 (compositor ink-only) is applied during composition in render.py

    # Layer 5 (post-upscale halo cleanup) is applied after upscaling in render.py

    return img


def pad_clipped_descender(img: np.ndarray) -> np.ndarray:
    """Add bottom padding when descender ink is clipped by the canvas edge.

    The 64px generation canvas clips deep descenders (g, j, p, q, y).
    When ink reaches within 2px of the canvas bottom, add white padding
    proportional to the descender depth so the composition stage can
    place the word correctly.
    """
    h = img.shape[0]
    ink_mask = img < 180
    if not np.any(ink_mask):
        return img

    ink_rows = np.any(ink_mask, axis=1)
    last_ink_row = len(ink_rows) - 1 - int(np.argmax(ink_rows[::-1]))
    first_ink_row = int(np.argmax(ink_rows))
    ink_height = last_ink_row - first_ink_row + 1

    # Only pad if ink reaches within 2px of canvas bottom
    if last_ink_row < h - 3:
        return img

    # Padding proportional to ink height: descenders are typically 20-35%
    # of body height. Add 25% of ink height, minimum 6px.
    pad_amount = max(6, int(ink_height * 0.25))
    padding = np.full((pad_amount, img.shape[1]), 255, dtype=np.uint8)
    return np.vstack([img, padding])


def halo_cleanup(img: np.ndarray) -> np.ndarray:
    """Layer 5: Post-upscale halo cleanup.

    Dilate strong-ink mask, blank gray pixels not near dilated ink.
    """
    import cv2

    # Find strong ink pixels
    strong_ink = img < 128
    strong_ink_uint8 = strong_ink.astype(np.uint8) * 255

    # Dilate to create neighborhood mask
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (HALO_DILATE_RADIUS * 2 + 1, HALO_DILATE_RADIUS * 2 + 1)
    )
    dilated = cv2.dilate(strong_ink_uint8, kernel)
    near_ink = dilated > 0

    # Blank gray pixels not near ink
    result = img.copy()
    gray_pixels = (img > 128) & (img < HALO_GRAY_THRESHOLD)
    cleanup_mask = gray_pixels & ~near_ink
    result[cleanup_mask] = 255

    return result


# --- DDIM Sampling ---

def ddim_sample(
    unet,
    vae,
    text_context: dict,
    style_features: torch.Tensor,
    uncond_context: dict | None = None,
    canvas_width: int = DEFAULT_CANVAS_WIDTH,
    num_steps: int = DEFAULT_DDIM_STEPS,
    guidance_scale: float = DEFAULT_GUIDANCE_SCALE,
    device: str = "cuda",
) -> np.ndarray:
    """Run DDIM sampling to generate a single word image.

    Args:
        unet: DiffusionPen UNet model.
        vae: SD 1.5 VAE decoder.
        text_context: Canine-C tokenizer output dict.
        style_features: (5, 1280) raw style features.
        uncond_context: Pre-tokenized unconditional context for CFG.
            If None and guidance_scale != 1.0, CFG is skipped.
        canvas_width: Width of generation canvas.
        num_steps: Number of DDIM steps.
        guidance_scale: CFG guidance scale (1.0 disables CFG).
        device: Torch device.

    Returns:
        Grayscale uint8 numpy array.
    """
    from diffusers import DDIMScheduler

    scheduler = DDIMScheduler(
        beta_start=0.00085,
        beta_end=0.012,
        beta_schedule="scaled_linear",
        clip_sample=False,
    )
    scheduler.set_timesteps(num_steps, device=device)

    latent_h = DEFAULT_CANVAS_HEIGHT // 8
    latent_w = canvas_width // 8

    # Move inputs to device once
    text_ctx = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in text_context.items()}
    style_feat = style_features.to(device)

    # CFG setup
    use_cfg = guidance_scale != 1.0 and uncond_context is not None
    if use_cfg:
        uncond_ctx = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in uncond_context.items()}
        zero_style = torch.zeros_like(style_feat)

    with torch.no_grad():
        # Start from noise
        latents = torch.randn(1, 4, latent_h, latent_w, device=device)

        for t in scheduler.timesteps:
            t_batch = t.unsqueeze(0) if t.dim() == 0 else t

            # Conditional prediction
            noise_pred_cond = unet(
                latents, t_batch, context=text_ctx, y=style_feat,
                style_extractor=style_feat,
            )

            if use_cfg:
                # Unconditional prediction
                noise_pred_uncond = unet(
                    latents, t_batch, context=uncond_ctx, y=zero_style,
                    style_extractor=zero_style,
                )
                noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_cond - noise_pred_uncond)
            else:
                noise_pred = noise_pred_cond

            latents = scheduler.step(noise_pred, t, latents).prev_sample

        # VAE decode
        decoded = vae.decode(latents / VAE_SCALE_FACTOR).sample
        decoded = (decoded / 2 + 0.5).clamp(0, 1)
        img = decoded[0].mean(dim=0).cpu().numpy()

    img = (img * 255).astype(np.uint8)
    return img


def generate_word(
    word: str,
    unet,
    vae,
    tokenizer,
    style_features: torch.Tensor,
    uncond_context: dict | None = None,
    num_steps: int = DEFAULT_DDIM_STEPS,
    guidance_scale: float = DEFAULT_GUIDANCE_SCALE,
    num_candidates: int = DEFAULT_NUM_CANDIDATES,
    device: str = "cuda",
    style_reference_imgs: list[np.ndarray] | None = None,
    reference_stroke_width: float = 0.0,
) -> np.ndarray:
    """Generate a single word image with best-of-N candidate selection.

    Long words (>10 chars) are split, generated as chunks, and stitched.

    Candidates with OCR accuracy below 0.4 are rejected; up to 2 extra
    retries are attempted to find a readable result.

    Args:
        uncond_context: Pre-tokenized unconditional context for CFG.
            Build once with tokenizer(" ", ...) and reuse across all words.
        style_reference_imgs: Raw grayscale style word images for tiebreaking.
            When two candidates have quality scores within 0.05, the one
            with higher style similarity wins.
        reference_stroke_width: Target stroke width from style images.
            When > 0, candidate scoring penalizes stroke width deviation.
    """
    import logging

    from reforge.quality.score import quality_score

    log = logging.getLogger("reforge.generator")

    # Contraction path (spec 2026-04-18 Option W): split at the apostrophe,
    # keeping the mark on the right (e.g. "can't" -> "can" + "'t"). Both parts
    # render through the normal word path; no synthetic apostrophe injection.
    if is_contraction(word):
        left_text, right_text = split_contraction(word)
        log.debug("contraction split: %s -> %s + %s", word, left_text, right_text)
        return _generate_contraction(
            left_text, right_text, word,
            unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=num_steps,
            guidance_scale=guidance_scale,
            num_candidates=num_candidates,
            device=device,
            style_reference_imgs=style_reference_imgs,
            reference_stroke_width=reference_stroke_width,
        )

    # Trailing punctuation path: strip the mark, generate the base word,
    # then attach a synthetic Bezier-rendered mark. DiffusionPen renders
    # trailing punctuation as invisible (IAM dataset bias).
    base_word, trailing_mark = strip_trailing_punctuation(word)
    if trailing_mark is not None:
        log.debug("trailing punctuation: %s -> %s + '%s'", word, base_word, trailing_mark)
        return _generate_punctuated_word(
            word, trailing_mark, base_word,
            unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=num_steps,
            guidance_scale=guidance_scale,
            num_candidates=num_candidates,
            device=device,
            style_reference_imgs=style_reference_imgs,
            reference_stroke_width=reference_stroke_width,
        )

    chunks = split_long_word(word)

    # OCR function: needed for candidate scoring (num_candidates > 1)
    # and post-selection rejection loop.
    ocr_fn = _get_ocr_fn() if num_candidates > 1 else None
    log_candidates = _candidate_logging_enabled()

    def _generate_chunk(chunk_text: str) -> tuple[np.ndarray, float]:
        """Generate a word chunk with best-of-N selection.

        Returns (image, ocr_accuracy). ocr_accuracy is -1.0 when OCR
        scoring was not performed (num_candidates == 1).
        """
        from reforge.quality.score import quality_score_breakdown

        canvas_width = compute_canvas_width(len(chunk_text))
        text_ctx = tokenizer(chunk_text, return_tensors="pt", padding="max_length", max_length=16)

        candidates = []
        candidate_log_rows = []
        for cand_idx in range(num_candidates):
            img = ddim_sample(
                unet, vae, text_ctx, style_features,
                uncond_context=uncond_context,
                canvas_width=canvas_width,
                num_steps=num_steps,
                guidance_scale=guidance_scale,
                device=device,
            )
            img = postprocess_word(img)
            img = pad_clipped_descender(img)
            img_score, sub_scores = quality_score_breakdown(
                img,
                reference_stroke_width=reference_stroke_width,
                word_len=len(chunk_text) if num_candidates > 1 else 0,
            )

            # A1: OCR-aware scoring when multiple candidates
            if ocr_fn is not None:
                ocr_acc = ocr_fn(img, chunk_text)
                combined = (1 - OCR_SELECTION_WEIGHT) * img_score + OCR_SELECTION_WEIGHT * ocr_acc
                candidates.append((img, img_score, ocr_acc, combined))
                log.debug(
                    "candidate %s: quality=%.3f ocr=%.3f combined=%.3f",
                    chunk_text, img_score, ocr_acc, combined,
                )
            else:
                ocr_acc = -1.0
                combined = img_score
                candidates.append((img, img_score, ocr_acc, combined))

            if log_candidates:
                row_sub = {k: round(float(v), 4) for k, v in sub_scores.items()}
                row_sub["ocr_accuracy"] = round(float(ocr_acc), 4)
                row_sub["combined"] = round(float(combined), 4)
                candidate_log_rows.append({
                    "index": cand_idx,
                    "sub_scores": row_sub,
                    "total": round(float(img_score), 4),
                })

        # Select best candidate by combined score
        best_combined = max(c[3] for c in candidates)

        # Style similarity tiebreaker: among candidates within 0.05
        # of the best combined score, prefer higher style similarity
        if style_reference_imgs is not None and len(candidates) > 1:
            from reforge.evaluate.visual import compute_style_similarity
            tied = [c for c in candidates if c[3] >= best_combined - 0.05]
            if len(tied) > 1:
                winner = max(
                    tied,
                    key=lambda c: compute_style_similarity(c[0], style_reference_imgs),
                )
                log.debug(
                    "selected %s: quality=%.3f ocr=%.3f combined=%.3f (style tiebreak)",
                    chunk_text, winner[1], winner[2], winner[3],
                )
                if log_candidates and candidate_log_rows:
                    sel_idx = candidates.index(winner)
                    _log_candidate_scores(chunk_text, candidate_log_rows, sel_idx)
                return winner[0], winner[2]

        winner = max(candidates, key=lambda c: c[3])
        log.debug(
            "selected %s: quality=%.3f ocr=%.3f combined=%.3f",
            chunk_text, winner[1], winner[2], winner[3],
        )
        if log_candidates and candidate_log_rows:
            sel_idx = candidates.index(winner)
            _log_candidate_scores(chunk_text, candidate_log_rows, sel_idx)
        return winner[0], winner[2]

    if len(chunks) == 1:
        best, known_ocr_acc = _generate_chunk(word)

        # OCR-based rejection: retry if accuracy is too low.
        # Threshold 0.4 catches borderline cases (e.g. "an" at 0.33) that
        # 0.3 missed. Retries trigger on ~10% of words; cost is acceptable.
        # A3: reuse known OCR accuracy from candidate scoring to avoid
        # redundant TrOCR call on the selected candidate.
        rejection_ocr_fn = _get_ocr_fn()
        if rejection_ocr_fn is not None:
            ocr_threshold = 0.4
            max_retries = 2
            # If OCR-aware scoring already computed accuracy, reuse it
            best_acc = known_ocr_acc if known_ocr_acc >= 0 else 0.0
            first_check_done = known_ocr_acc >= 0

            for attempt in range(max_retries):
                if not first_check_done or attempt > 0:
                    acc = rejection_ocr_fn(best, word)
                    best_acc = max(best_acc, acc)
                else:
                    acc = known_ocr_acc
                    best_acc = max(best_acc, acc)

                if acc >= ocr_threshold:
                    break

                # Retry with fresh generation
                retry, retry_known_acc = _generate_chunk(word)
                if retry_known_acc >= 0:
                    retry_acc = retry_known_acc
                else:
                    retry_acc = rejection_ocr_fn(retry, word)
                best_acc = max(best_acc, retry_acc)
                if retry_acc > acc:
                    best = retry
                    if retry_acc >= ocr_threshold:
                        break
            else:
                # Exhausted retries without reaching threshold
                _record_hard_word_candidate(word, best_acc)

        return best

    # Multi-chunk: generate each, normalize heights, baseline-align, stitch
    chunk_images = [_generate_chunk(chunk)[0] for chunk in chunks]
    return stitch_chunks(chunk_images)


def _get_ocr_fn():
    """Return ocr_accuracy function if available, else None."""
    try:
        from reforge.evaluate.ocr import ocr_accuracy
        return ocr_accuracy
    except ImportError:
        return None


def _candidate_logging_enabled() -> bool:
    """True when REFORGE_LOG_CANDIDATES=1 is set in the environment."""
    import os
    return os.environ.get("REFORGE_LOG_CANDIDATES", "") == "1"


def _log_candidate_scores(
    word: str,
    candidate_rows: list[dict],
    selected_index: int,
    timestamp: str | None = None,
) -> None:
    """Append one JSONL row per best-of-N selection to the candidate log.

    ``candidate_rows`` is a list of {"index", "sub_scores", "total"} dicts
    describing every candidate evaluated. ``timestamp`` may be supplied by
    callers that want the log to share a timestamp with another record
    (e.g., the human-review JSON join key); defaults to ``now``. Writes are
    gated on ``REFORGE_LOG_CANDIDATES=1``; callers must check
    ``_candidate_logging_enabled()`` first.
    """
    import datetime
    import json
    import os

    log_path = os.path.join("experiments", "output", "candidate_scores.jsonl")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    try:
        seed = int(torch.initial_seed())
    except Exception:
        seed = -1
    record = {
        "word": word,
        "seed": seed,
        "timestamp": timestamp or datetime.datetime.now().isoformat(timespec="seconds"),
        "candidates": candidate_rows,
        "selected_index": selected_index,
    }
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass  # Non-critical; logging never blocks generation


def _record_hard_word_candidate(word: str, best_acc: float) -> None:
    """Record a word that exhausted OCR retries as a hard word candidate."""
    try:
        from reforge.data.words import add_candidate
        add_candidate(word, source="ocr_rejection", ocr_accuracy=best_acc)
    except Exception:
        pass  # Non-critical; do not interrupt generation


def _generate_contraction(
    left_text: str,
    right_text: str,
    full_word: str,
    unet,
    vae,
    tokenizer,
    style_features,
    uncond_context=None,
    num_steps=DEFAULT_DDIM_STEPS,
    guidance_scale=DEFAULT_GUIDANCE_SCALE,
    num_candidates=DEFAULT_NUM_CANDIDATES,
    device="cuda",
    style_reference_imgs=None,
    reference_stroke_width=0.0,
) -> np.ndarray:
    """Generate a contraction by producing the two parts separately and stitching.

    Spec 2026-04-18 Option W: split_contraction keeps the apostrophe on the
    right part (e.g. "can't" -> "can" + "'t"), so both parts generate through
    the normal word path with no synthetic apostrophe injection between them.
    """
    import logging

    from reforge.quality.score import quality_score

    log = logging.getLogger("reforge.generator")

    ocr_fn = _get_ocr_fn() if num_candidates > 1 else None

    def _gen_part(text):
        canvas_width = compute_canvas_width(len(text))
        text_ctx = tokenizer(text, return_tensors="pt", padding="max_length", max_length=16)
        best_img = None
        best_score = -999
        for _ in range(num_candidates):
            img = ddim_sample(
                unet, vae, text_ctx, style_features,
                uncond_context=uncond_context,
                canvas_width=canvas_width,
                num_steps=num_steps,
                guidance_scale=guidance_scale,
                device=device,
            )
            img = postprocess_word(img)
            img = pad_clipped_descender(img)
            score = quality_score(
                img,
                reference_stroke_width=reference_stroke_width,
                word_len=len(text) if num_candidates > 1 else 0,
            )
            if ocr_fn is not None:
                from reforge.config import OCR_SELECTION_WEIGHT
                ocr_acc = ocr_fn(img, text)
                combined = (1 - OCR_SELECTION_WEIGHT) * score + OCR_SELECTION_WEIGHT * ocr_acc
            else:
                combined = score
            if combined > best_score:
                best_score = combined
                best_img = img
        return best_img

    left_img = _gen_part(left_text)
    right_img = _gen_part(right_text)

    right_img = _match_chunk_to_reference(right_img, left_img)

    result = stitch_contraction(left_img, right_img)
    log.debug(
        "contraction stitched: %s (%dx%d) + %s (%dx%d) -> %dx%d",
        left_text, left_img.shape[1], left_img.shape[0],
        right_text, right_img.shape[1], right_img.shape[0],
        result.shape[1], result.shape[0],
    )
    return result


def strip_trailing_punctuation(word: str) -> tuple[str, str | None]:
    """Strip a trailing punctuation mark that can be synthesized.

    Returns (base_word, mark) where mark is the single trailing character
    if it is in SYNTHETIC_MARKS, or None if no strippable punctuation.
    Only strips one trailing mark. Does not strip apostrophes (handled
    by the contraction path).
    """
    if len(word) >= 2 and word[-1] in SYNTHETIC_MARKS:
        return word[:-1], word[-1]
    return word, None


def _attach_mark_to_word(
    word_img: np.ndarray,
    mark_img: np.ndarray,
    gap_px: int = 1,
    *,
    word: str | None = None,
    mark: str | None = None,
) -> np.ndarray:
    """Attach a synthetic punctuation mark to the right side of a word image.

    When ``word`` is given, the word's baseline (non-descender letter bottom)
    is used instead of its full ink bottom, so trailing marks don't track
    the descender of letters like ``j g p q y``. When ``mark`` is a descender
    glyph (``,``, ``;``), the mark's own body baseline is used so the
    descender extends below rather than pulling the alignment point down.
    """
    INK_THRESH = 180

    def _ink_bottom(img):
        ink_rows = np.any(img < INK_THRESH, axis=1)
        if not np.any(ink_rows):
            return 0
        return img.shape[0] - 1 - int(np.argmax(ink_rows[::-1]))

    def _tight_crop_h(img, pad_px=1):
        col_has_ink = np.any(img < INK_THRESH, axis=0)
        if not np.any(col_has_ink):
            return img
        left = max(0, int(np.argmax(col_has_ink)) - pad_px)
        right = min(img.shape[1] - 1, len(col_has_ink) - 1 - int(np.argmax(col_has_ink[::-1])) + pad_px)
        return img[:, left:right + 1]

    def _word_reference_row(img):
        if word is None:
            return _ink_bottom(img)
        from reforge.compose.layout import detect_baseline
        return int(detect_baseline(img, word))

    def _mark_reference_row(img):
        if mark not in {",", ";"}:
            return _ink_bottom(img)
        # Descender mark: find the bottom of the body (dot) portion, above
        # the thin tail. The body rows have high ink density relative to
        # the tail.
        row_density = np.mean(img < INK_THRESH, axis=1)
        if not np.any(row_density > 0):
            return _ink_bottom(img)
        max_density = float(row_density.max())
        body_threshold = max(0.05, max_density * 0.5)
        body_rows = np.where(row_density >= body_threshold)[0]
        if body_rows.size == 0:
            return _ink_bottom(img)
        return int(body_rows.max())

    word_img = _tight_crop_h(word_img)

    word_ref = _word_reference_row(word_img)
    mark_ref = _mark_reference_row(mark_img)

    parts = [word_img, mark_img]
    refs = [word_ref, mark_ref]

    # Canvas: enough rows above every part's ref, and enough below every
    # part's content. Each part gets top-padded so ref lands at top_canvas,
    # and bottom-padded to match canvas height.
    top_canvas = max(refs)
    bot_canvas = max(p.shape[0] - ref - 1 for p, ref in zip(parts, refs))
    max_h = top_canvas + 1 + bot_canvas

    aligned = []
    for p, ref in zip(parts, refs):
        top_pad_n = top_canvas - ref
        bot_pad_n = bot_canvas - (p.shape[0] - ref - 1)
        if top_pad_n > 0:
            p = np.vstack([np.full((top_pad_n, p.shape[1]), 255, dtype=np.uint8), p])
        if bot_pad_n > 0:
            p = np.vstack([p, np.full((bot_pad_n, p.shape[1]), 255, dtype=np.uint8)])
        aligned.append(p)

    gap = np.full((max_h, gap_px), 255, dtype=np.uint8)
    return np.hstack([aligned[0], gap, aligned[1]])


def strip_and_reattach_punctuation(
    word: str,
    word_img: np.ndarray,
    generate_fn=None,
    unet=None, vae=None, tokenizer=None, style_features=None,
    **gen_kwargs,
) -> np.ndarray:
    """Pipeline helper: detect trailing punctuation, generate base word, reattach mark.

    If the word ends with a synthesizable mark (. , ! ? ;), strips it,
    generates the base word (or uses word_img if generate_fn is None),
    and appends the synthetic mark at the correct baseline position.

    For apostrophes, delegates to the contraction path (handled separately
    in generate_word).

    Args:
        word: The full word including trailing punctuation.
        word_img: Pre-generated image of the base word (used when generate_fn
            is None, e.g. in testing).
        generate_fn: Optional callable(base_word) -> np.ndarray that generates
            the base word image. Used in the live pipeline.

    Returns:
        Word image with synthetic punctuation attached, or word_img unchanged
        if no trailing punctuation is detected.
    """
    from reforge.quality.ink_metrics import compute_x_height

    base_word, mark = strip_trailing_punctuation(word)
    if mark is None:
        return word_img

    # Generate the base word if a generate function is provided
    if generate_fn is not None:
        word_img = generate_fn(base_word)

    # Derive mark properties from the generated word
    ink_pixels = word_img[word_img < 180]
    ink_intensity = int(np.median(ink_pixels)) if len(ink_pixels) > 0 else 60
    body_h = compute_x_height(word_img)

    mark_img = make_synthetic_mark(mark, ink_intensity, body_h)
    return _attach_mark_to_word(word_img, mark_img, word=base_word, mark=mark)


def _generate_punctuated_word(
    word: str,
    mark: str,
    base_word: str,
    unet,
    vae,
    tokenizer,
    style_features,
    uncond_context=None,
    num_steps=DEFAULT_DDIM_STEPS,
    guidance_scale=DEFAULT_GUIDANCE_SCALE,
    num_candidates=DEFAULT_NUM_CANDIDATES,
    device="cuda",
    style_reference_imgs=None,
    reference_stroke_width=0.0,
) -> np.ndarray:
    """Generate a word with trailing punctuation by producing the base word
    and attaching a synthetic mark.

    This mirrors _generate_contraction but for trailing punctuation marks.
    """
    import logging

    from reforge.quality.ink_metrics import compute_x_height
    from reforge.quality.score import quality_score

    log = logging.getLogger("reforge.generator")

    ocr_fn = _get_ocr_fn() if num_candidates > 1 else None

    # Generate base word (without trailing punctuation)
    canvas_width = compute_canvas_width(len(base_word))
    text_ctx = tokenizer(base_word, return_tensors="pt", padding="max_length", max_length=16)

    best_img = None
    best_score = -999
    for _ in range(num_candidates):
        img = ddim_sample(
            unet, vae, text_ctx, style_features,
            uncond_context=uncond_context,
            canvas_width=canvas_width,
            num_steps=num_steps,
            guidance_scale=guidance_scale,
            device=device,
        )
        img = postprocess_word(img)
        img = pad_clipped_descender(img)
        score = quality_score(
            img,
            reference_stroke_width=reference_stroke_width,
            word_len=len(base_word) if num_candidates > 1 else 0,
        )
        if ocr_fn is not None:
            ocr_acc = ocr_fn(img, base_word)
            combined = (1 - OCR_SELECTION_WEIGHT) * score + OCR_SELECTION_WEIGHT * ocr_acc
        else:
            combined = score
        if combined > best_score:
            best_score = combined
            best_img = img

    # Derive mark properties and attach
    ink_pixels = best_img[best_img < 180]
    ink_intensity = int(np.median(ink_pixels)) if len(ink_pixels) > 0 else 60
    body_h = compute_x_height(best_img)

    mark_img = _render_trailing_mark_or_fallback(mark, ink_intensity, body_h)
    result = _attach_mark_to_word(best_img, mark_img, word=base_word, mark=mark)

    log.debug(
        "punctuated word: %s (%dx%d) + '%s' -> %dx%d",
        base_word, best_img.shape[1], best_img.shape[0],
        mark, result.shape[1], result.shape[0],
    )
    return result


def _ink_density_profile(img: np.ndarray, ink_thresh: int = 180) -> np.ndarray:
    """Compute vertical ink-density profile: fraction of ink pixels per row.

    Returns a 1D array of length img.shape[0], where each element is the
    fraction of pixels in that row that are below ink_thresh.
    """
    ink = img < ink_thresh
    if img.shape[1] == 0:
        return np.zeros(img.shape[0], dtype=np.float64)
    return np.mean(ink, axis=1).astype(np.float64)


def _cross_correlation_offset(
    profile_a: np.ndarray,
    profile_b: np.ndarray,
    max_shift: int | None = None,
) -> int:
    """Find vertical offset that maximizes cross-correlation between profiles.

    Returns the offset d such that profile_b shifted down by d pixels
    best aligns with profile_a. Positive d means profile_b should be
    placed lower relative to profile_a.

    Uses normalized cross-correlation (zero-mean, unit-variance) so that
    the body zone (dense ink) naturally dominates the signal.
    """
    la, lb = len(profile_a), len(profile_b)
    if max_shift is None:
        max_shift = max(la, lb) // 2

    # Normalize profiles (zero-mean, unit-variance)
    def _norm(p):
        std = np.std(p)
        if std < 1e-8:
            return p - np.mean(p)
        return (p - np.mean(p)) / std

    a = _norm(profile_a)
    b = _norm(profile_b)

    best_corr = -np.inf
    best_d = 0

    for d in range(-max_shift, max_shift + 1):
        # Overlapping range after shifting b by d
        a_start = max(0, d)
        a_end = min(la, lb + d)
        b_start = max(0, -d)
        b_end = b_start + (a_end - a_start)

        if a_end <= a_start or b_end > lb:
            continue

        overlap = a_end - a_start
        if overlap < 4:
            continue

        corr = np.dot(a[a_start:a_end], b[b_start:b_end]) / overlap
        if corr > best_corr:
            best_corr = corr
            best_d = d

    return best_d


def align_chunks_cross_correlation(
    chunks: list[np.ndarray],
    ink_thresh: int = 180,
) -> list[np.ndarray]:
    """Align chunks vertically using ink-profile cross-correlation.

    Computes the vertical ink-density profile for each chunk and finds
    pairwise offsets that maximize cross-correlation. This uses the full
    vertical ink distribution rather than single-point baseline detection,
    producing more robust alignment when chunks have different ascender/
    descender distributions.

    Returns a list of vertically padded chunks, all the same height,
    aligned by their ink density profiles.
    """
    if len(chunks) <= 1:
        return chunks

    profiles = [_ink_density_profile(c, ink_thresh) for c in chunks]

    # Compute offsets relative to the first chunk
    offsets = [0]
    for i in range(1, len(chunks)):
        d = _cross_correlation_offset(profiles[0], profiles[i])
        offsets.append(d)

    # Convert to absolute top-padding amounts
    min_offset = min(offsets)
    top_pads = [o - min_offset for o in offsets]

    # Compute maximum total height needed
    max_h = max(
        top_pads[i] + chunks[i].shape[0] for i in range(len(chunks))
    )

    padded = []
    for i, chunk in enumerate(chunks):
        tp = top_pads[i]
        bp = max_h - tp - chunk.shape[0]
        if tp > 0:
            pad_top = np.full((tp, chunk.shape[1]), 255, dtype=np.uint8)
            chunk = np.vstack([pad_top, chunk])
        if bp > 0:
            pad_bot = np.full((bp, chunk.shape[1]), 255, dtype=np.uint8)
            chunk = np.vstack([chunk, pad_bot])
        padded.append(chunk)

    return padded


def stitch_chunks(chunks: list[np.ndarray], alignment: str = "cross_correlation") -> np.ndarray:
    """Stitch word chunks with ink-height alignment and overlap blending.

    - Measure each chunk's ink region (top/bottom ink rows)
    - Scale chunks so ink heights match (median ink height)
    - Align by ink bottom (baseline) or cross-correlation, per alignment param
    - Overlap blending at stitch boundaries

    Args:
        alignment: "ink_bottom" (default, current method) or
            "cross_correlation" (experimental ink-profile matching).
    """
    import cv2

    from reforge.quality.ink_metrics import compute_x_height

    if len(chunks) == 1:
        return chunks[0]

    # Horizontal tight-crop: strip leading/trailing whitespace columns
    # from each chunk to eliminate the gap between stitched pieces
    INK_THRESH = 180
    cropped = []
    for chunk in chunks:
        col_has_ink = np.any(chunk < INK_THRESH, axis=0)
        if np.any(col_has_ink):
            first_col = np.argmax(col_has_ink)
            last_col = len(col_has_ink) - 1 - np.argmax(col_has_ink[::-1])
            # Keep 2px margin on each side for overlap blending
            first_col = max(0, first_col - 2)
            last_col = min(chunk.shape[1] - 1, last_col + 2)
            chunk = chunk[:, first_col:last_col + 1]
        cropped.append(chunk)
    chunks = cropped

    # Measure x-height (body zone, excluding ascenders/descenders)
    # for normalization, plus ink bounds for baseline alignment
    x_heights = []
    ink_bottoms = []  # distance from image bottom to last ink row
    for chunk in chunks:
        x_h = compute_x_height(chunk)
        x_heights.append(x_h)
        # Find last ink row (baseline position)
        ink_rows = np.any(chunk < INK_THRESH, axis=1)
        if np.any(ink_rows):
            last_ink = len(ink_rows) - 1 - np.argmax(ink_rows[::-1])
            ink_bottoms.append(chunk.shape[0] - 1 - last_ink)
        else:
            ink_bottoms.append(0)

    # Scale each chunk so x-height matches the median x-height.
    # X-height normalization matches the letter body size, not the total
    # ink extent, preventing "under" (tall) and "standing" (short body)
    # from looking mismatched when stitched.
    median_x_h = int(np.median(x_heights))
    if median_x_h < 4:
        median_x_h = max(x_heights)  # fallback for very small ink

    normalized = []
    for i, chunk in enumerate(chunks):
        if x_heights[i] > 0 and x_heights[i] != median_x_h:
            scale = median_x_h / x_heights[i]
            new_h = max(1, int(chunk.shape[0] * scale))
            new_w = max(1, int(chunk.shape[1] * scale))
            chunk = cv2.resize(chunk, (new_w, new_h), interpolation=cv2.INTER_AREA)
        normalized.append(chunk)

    if alignment == "cross_correlation":
        # C1: experimental ink-profile cross-correlation alignment
        padded = align_chunks_cross_correlation(normalized, INK_THRESH)
        max_h = padded[0].shape[0] if padded else 0
    else:
        # Default: ink-bottom (baseline) alignment
        # Re-measure ink bottoms after scaling (scaling shifts pixel positions)
        scaled_ink_bottoms = []
        for chunk in normalized:
            ink_rows = np.any(chunk < INK_THRESH, axis=1)
            if np.any(ink_rows):
                last_ink = len(ink_rows) - 1 - np.argmax(ink_rows[::-1])
                scaled_ink_bottoms.append(chunk.shape[0] - 1 - last_ink)
            else:
                scaled_ink_bottoms.append(0)

        # Align by ink bottom (baseline): pad so all chunks have the same
        # distance from their last ink row to the image bottom
        max_ink_bottom = max(scaled_ink_bottoms)
        max_h = max(c.shape[0] + (max_ink_bottom - scaled_ink_bottoms[i])
                    for i, c in enumerate(normalized))

        padded = []
        for i, chunk in enumerate(normalized):
            # Pad at bottom to align baselines
            bottom_pad = max_ink_bottom - scaled_ink_bottoms[i]
            if bottom_pad > 0:
                pad_bottom = np.full((bottom_pad, chunk.shape[1]), 255, dtype=np.uint8)
                chunk = np.vstack([chunk, pad_bottom])
            # Pad at top to equalize total height
            if chunk.shape[0] < max_h:
                pad_top = np.full((max_h - chunk.shape[0], chunk.shape[1]), 255, dtype=np.uint8)
                chunk = np.vstack([pad_top, chunk])
            padded.append(chunk)

    # Stitch with overlap blending
    total_width = sum(c.shape[1] for c in padded) - STITCH_OVERLAP_PX * (len(padded) - 1)
    result = np.full((max_h, total_width), 255, dtype=np.uint8)

    x = 0
    for i, chunk in enumerate(padded):
        if i == 0:
            result[:, x : x + chunk.shape[1]] = chunk
            x += chunk.shape[1] - STITCH_OVERLAP_PX
        else:
            # Blend overlap region
            overlap_start = x
            overlap_end = x + STITCH_OVERLAP_PX

            for ox in range(STITCH_OVERLAP_PX):
                alpha = ox / STITCH_OVERLAP_PX  # 0->1 from left to right
                col_idx = overlap_start + ox
                if col_idx < result.shape[1]:
                    prev_col = result[:, col_idx].astype(np.float32)
                    new_col = chunk[:, ox].astype(np.float32)
                    result[:, col_idx] = ((1 - alpha) * prev_col + alpha * new_col).astype(np.uint8)

            # Copy rest of chunk
            rest_start = STITCH_OVERLAP_PX
            dest_start = overlap_end
            rest_width = chunk.shape[1] - rest_start
            if dest_start + rest_width <= result.shape[1]:
                result[:, dest_start : dest_start + rest_width] = chunk[:, rest_start:]

            x = dest_start + rest_width - STITCH_OVERLAP_PX

    return result
