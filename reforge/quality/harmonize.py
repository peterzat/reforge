"""Cross-word harmonization: stroke weight and height normalization.

Stroke weight: shift each word's ink median toward the global median.
Height: scale DOWN outliers > HEIGHT_OUTLIER_THRESHOLD of median, scale UP undersized < HEIGHT_UNDERSIZE_THRESHOLD of median.
"""

import cv2
import numpy as np

from reforge.config import (
    HEIGHT_OUTLIER_THRESHOLD,
    HEIGHT_OUTLIER_THRESHOLD_PASS2,
    HEIGHT_UNDERSIZE_THRESHOLD,
    HEIGHT_UNDERSIZE_THRESHOLD_PASS2,
    STROKE_WEIGHT_SHIFT_STRENGTH,
)
from reforge.quality.ink_metrics import compute_ink_height


def compute_ink_median(img: np.ndarray) -> float:
    """Compute median brightness of ink pixels in a word image."""
    ink_pixels = img[img < 180]
    if len(ink_pixels) == 0:
        return 128.0
    return float(np.median(ink_pixels))


def compute_mean_stroke_width(img: np.ndarray) -> float:
    """Compute mean stroke width via distance transform on ink mask (B1).

    Returns the mean distance from ink pixels to the nearest background
    pixel, which approximates half the stroke width. Multiply by 2 for
    full stroke width.
    """
    ink_mask = (img < 180).astype(np.uint8)
    if np.sum(ink_mask) < 10:
        return 0.0
    dist = cv2.distanceTransform(ink_mask, cv2.DIST_L2, 5)
    ink_dists = dist[ink_mask > 0]
    return float(np.mean(ink_dists, dtype=np.float64)) * 2.0


def harmonize_stroke_width(word_images: list[np.ndarray]) -> list[np.ndarray]:
    """Normalize stroke widths across words using blended morphological operations.

    Per-word correction: each word more than 15% from the median stroke width
    gets a partial erosion (too thick) or dilation (too thin). Instead of
    hard pixel removal, the morphed image is alpha-blended with the original
    proportional to the deviation. This avoids destroying thin letterforms
    while still converging stroke widths.
    """
    if len(word_images) < 2:
        return word_images

    widths = [compute_mean_stroke_width(img) for img in word_images]
    valid_widths = [w for w in widths if w > 0]
    if len(valid_widths) < 2:
        return word_images

    median_w = float(np.median(valid_widths))
    if median_w <= 0:
        return word_images

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    result = []
    for img, w in zip(word_images, widths):
        deviation = abs(w - median_w) / median_w
        if w <= 0 or deviation < 0.15:
            result.append(img)
            continue

        # Blend factor: 0 at 15% deviation, capped at 0.7 for large deviations.
        # Partial blending preserves letterform detail.
        alpha = min(0.7, (deviation - 0.15) / 0.35)

        morphed = img.copy()
        if w > median_w * 1.15:
            ink_mask = (morphed < 180).astype(np.uint8) * 255
            eroded = cv2.erode(ink_mask, kernel, iterations=1)
            removed = (ink_mask > 0) & (eroded == 0)
            morphed[removed] = 255
        elif w < median_w * 0.85:
            ink_mask = (morphed < 180).astype(np.uint8) * 255
            dilated = cv2.dilate(ink_mask, kernel, iterations=1)
            added = (dilated > 0) & (ink_mask == 0)
            ink_brightness = compute_ink_median(img)
            morphed[added] = int(np.clip(ink_brightness, 0, 179))

        # Blend: partial application of the morphological change
        blended = (img.astype(np.float32) * (1 - alpha) + morphed.astype(np.float32) * alpha)
        result.append(np.clip(blended, 0, 255).astype(np.uint8))

    return result


def harmonize_stroke_weight(word_images: list[np.ndarray]) -> list[np.ndarray]:
    """Adjust stroke weight across all words to converge on global median.

    Shifts each word's ink brightness toward the global median ink brightness.
    """
    if not word_images:
        return word_images

    medians = [compute_ink_median(img) for img in word_images]
    global_median = float(np.median(medians))

    result = []
    for img, local_median in zip(word_images, medians):
        if abs(local_median - global_median) < 5:
            result.append(img)
            continue

        shift = (global_median - local_median) * STROKE_WEIGHT_SHIFT_STRENGTH
        adjusted = img.copy().astype(np.float32)

        # Only shift ink pixels, leave background alone
        ink_mask = img < 180
        adjusted[ink_mask] += shift
        adjusted = np.clip(adjusted, 0, 255).astype(np.uint8)
        result.append(adjusted)

    return result


def harmonize_heights(word_images: list[np.ndarray]) -> list[np.ndarray]:
    """Scale words toward median body-zone height to reduce height variance.

    Scale DOWN words above HEIGHT_OUTLIER_THRESHOLD of median.
    Scale UP words below HEIGHT_UNDERSIZE_THRESHOLD of median.
    Preserves aspect ratio during scaling.
    """
    if not word_images:
        return word_images

    heights = [compute_ink_height(img) for img in word_images]
    median_h = float(np.median(heights))
    upper = median_h * HEIGHT_OUTLIER_THRESHOLD
    lower = median_h * HEIGHT_UNDERSIZE_THRESHOLD

    result = []
    for img, h in zip(word_images, heights):
        if lower <= h <= upper:
            result.append(img)
            continue

        if h > upper:
            target = upper
        else:
            target = lower
        scale = target / h
        new_h = max(1, int(img.shape[0] * scale))
        new_w = max(1, int(img.shape[1] * scale))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        scaled = cv2.resize(img, (new_w, new_h), interpolation=interp)
        result.append(scaled)

    return result


def harmonize_heights_pass2(word_images: list[np.ndarray]) -> list[np.ndarray]:
    """Second-pass height harmonization with tighter thresholds (E2).

    Applied after font normalization has already reduced variance. The
    tighter thresholds (105%/93%) are safe here because scaling factors
    are small. The A1 lesson (no tightening beyond 110%/88%) applies
    to the first pass on raw DiffusionPen output, not to pre-normalized data.
    """
    if not word_images:
        return word_images

    heights = [compute_ink_height(img) for img in word_images]
    median_h = float(np.median(heights))
    upper = median_h * HEIGHT_OUTLIER_THRESHOLD_PASS2
    lower = median_h * HEIGHT_UNDERSIZE_THRESHOLD_PASS2

    result = []
    for img, h in zip(word_images, heights):
        if lower <= h <= upper:
            result.append(img)
            continue

        if h > upper:
            target = upper
        else:
            target = lower
        scale = target / h
        new_h = max(1, int(img.shape[0] * scale))
        new_w = max(1, int(img.shape[1] * scale))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        scaled = cv2.resize(img, (new_w, new_h), interpolation=interp)
        result.append(scaled)

    return result


def harmonize_words(word_images: list[np.ndarray]) -> list[np.ndarray]:
    """Apply height harmonization (two passes), then stroke weight.

    Pass 1: standard thresholds (110%/88%) on raw DiffusionPen output.
    Pass 2: tighter thresholds (105%/93%) on already-normalized output (E2).
    Stroke weight harmonization last to converge ink medians properly.
    """
    result = harmonize_heights(word_images)
    result = harmonize_heights_pass2(result)
    result = harmonize_stroke_width(result)  # B2: after height, before brightness
    result = harmonize_stroke_weight(result)
    return result
