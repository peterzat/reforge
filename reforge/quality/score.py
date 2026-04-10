"""Per-word quality scoring for best-of-N candidate selection.

Evaluates background cleanliness, ink density, edge sharpness,
height consistency (target closeness), and contrast.
"""

import numpy as np

from reforge.config import QUALITY_WEIGHTS, SHORT_WORD_HEIGHT_TARGET


def _background_score(img: np.ndarray) -> float:
    """Score background cleanliness (1.0 = clean white background)."""
    # Background pixels are those > 200
    bg_pixels = img[img > 200]
    if len(bg_pixels) == 0:
        return 0.0
    # Ideal background is 255; penalize gray backgrounds
    mean_bg = np.mean(bg_pixels)
    return min(1.0, mean_bg / 255.0)


def _ink_density_score(img: np.ndarray) -> float:
    """Score ink density (penalize too little or too much ink)."""
    ink_ratio = np.mean(img < 128)
    # Ideal range: 5-30% ink
    if ink_ratio < 0.01:
        return 0.0
    if ink_ratio > 0.5:
        return 0.2
    if 0.05 <= ink_ratio <= 0.30:
        return 1.0
    if ink_ratio < 0.05:
        return ink_ratio / 0.05
    return max(0.2, 1.0 - (ink_ratio - 0.30) / 0.20)


def _edge_sharpness_score(img: np.ndarray) -> float:
    """Score edge sharpness using gradient magnitude."""
    import cv2
    if img.size == 0:
        return 0.0
    sobelx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
    gradient = np.sqrt(sobelx ** 2 + sobely ** 2)
    # Normalize: higher gradient at ink edges = sharper
    mean_grad = np.mean(gradient)
    # Typical good range: 10-50
    return min(1.0, mean_grad / 30.0)


def _height_consistency_score(img: np.ndarray, word_len: int = 0) -> float:
    """Score ink height closeness to the normalization target.

    When word_len > 0 (selection-time scoring), computes how close
    the candidate's ink height is to the expected target. Candidates
    that fill the full canvas or are extremely short score low.
    When word_len == 0 (legacy/no-word-info), falls back to canvas
    coverage ratio scoring.
    """
    ink_mask = img < 128
    if not np.any(ink_mask):
        return 0.0
    row_ink = np.mean(ink_mask, axis=1)
    ink_rows = row_ink > 0.01
    if not np.any(ink_rows):
        return 0.0
    first_row = int(np.argmax(ink_rows))
    last_row = len(ink_rows) - 1 - int(np.argmax(ink_rows[::-1]))
    ink_height = last_row - first_row + 1

    if word_len > 0:
        # Target-aware scoring: how close is ink height to what
        # font normalization will expect?
        if word_len <= 2:
            target = SHORT_WORD_HEIGHT_TARGET
        else:
            target = int(SHORT_WORD_HEIGHT_TARGET * 1.08)
        # Candidates near the target need minimal scaling later.
        # Linear falloff: 0% deviation = 1.0, 100%+ deviation = 0.0.
        # Asymmetric: penalize canvas-fill (too tall) more than too short,
        # because tall words get aggressively downscaled and lose quality.
        deviation = (ink_height - target) / target
        if deviation > 0:
            # Too tall: heavier penalty (canvas-fill is the main problem)
            return max(0.0, 1.0 - deviation / 0.8)
        else:
            # Too short: gentler penalty
            return max(0.0, 1.0 - abs(deviation) / 1.2)

    # Fallback: canvas coverage ratio (legacy behavior)
    total_height = img.shape[0]
    ratio = ink_height / total_height
    if 0.3 <= ratio <= 0.8:
        return 1.0
    return max(0.0, 1.0 - abs(ratio - 0.55) * 2)


def _contrast_score(img: np.ndarray) -> float:
    """Score ink-to-background contrast."""
    ink_pixels = img[img < 128]
    bg_pixels = img[img > 200]
    if len(ink_pixels) == 0 or len(bg_pixels) == 0:
        return 0.0
    contrast = np.mean(bg_pixels) - np.mean(ink_pixels)
    # Good contrast: > 100
    return min(1.0, contrast / 150.0)


def _stroke_width_score(img: np.ndarray, reference_width: float) -> float:
    """Score stroke width similarity to reference (1.0 = matches reference).

    Uses distance transform to measure mean stroke width, then scores
    based on deviation from the reference. Linear falloff: 0% deviation = 1.0,
    50%+ deviation = 0.0.
    """
    import cv2
    ink_mask = (img < 180).astype(np.uint8)
    if np.sum(ink_mask) < 10 or reference_width <= 0:
        return 0.5  # neutral when unmeasurable
    dist = cv2.distanceTransform(ink_mask, cv2.DIST_L2, 5)
    ink_dists = dist[ink_mask > 0]
    word_width = float(np.mean(ink_dists)) * 2.0
    if word_width <= 0:
        return 0.5
    deviation = abs(word_width - reference_width) / reference_width
    return max(0.0, 1.0 - deviation / 0.5)


def quality_score(
    img: np.ndarray,
    reference_stroke_width: float = 0.0,
    word_len: int = 0,
) -> float:
    """Compute weighted quality score for a word image.

    Args:
        reference_stroke_width: Target stroke width from style images.
            When > 0, stroke width similarity is scored and blended in.
        word_len: Length of the target word. When > 0, height scoring
            uses target-aware closeness instead of canvas coverage ratio.

    Returns a score in [0, 1] where higher is better.
    """
    scores = {
        "background": _background_score(img),
        "ink_density": _ink_density_score(img),
        "edge_sharpness": _edge_sharpness_score(img),
        "height_consistency": _height_consistency_score(img, word_len=word_len),
        "contrast": _contrast_score(img),
    }
    total = sum(scores[k] * QUALITY_WEIGHTS[k] for k in scores)

    if reference_stroke_width > 0:
        sw_score = _stroke_width_score(img, reference_stroke_width)
        # Blend: 80% image quality + 20% stroke width match
        total = total * 0.80 + sw_score * 0.20

    return total
