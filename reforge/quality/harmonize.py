"""Cross-word harmonization: stroke weight and height normalization.

Stroke weight: shift each word's ink median toward the global median.
Height: scale DOWN outliers > HEIGHT_OUTLIER_THRESHOLD of median, scale UP undersized < HEIGHT_UNDERSIZE_THRESHOLD of median.
"""

import cv2
import numpy as np

from reforge.config import (
    HEIGHT_OUTLIER_THRESHOLD,
    HEIGHT_UNDERSIZE_THRESHOLD,
    STROKE_WEIGHT_SHIFT_STRENGTH,
)


def compute_ink_median(img: np.ndarray) -> float:
    """Compute median brightness of ink pixels in a word image."""
    ink_pixels = img[img < 180]
    if len(ink_pixels) == 0:
        return 128.0
    return float(np.median(ink_pixels))


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


def compute_ink_height(img: np.ndarray) -> int:
    """Compute the ink height of a word image."""
    ink_rows = np.any(img < 180, axis=1)
    if not np.any(ink_rows):
        return img.shape[0]
    first = np.argmax(ink_rows)
    last = len(ink_rows) - 1 - np.argmax(ink_rows[::-1])
    return last - first + 1


def harmonize_heights(word_images: list[np.ndarray]) -> list[np.ndarray]:
    """Scale words toward median height to reduce height variance.

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

        # Scale toward median (not just to the threshold boundary)
        target = median_h
        scale = target / h
        new_h = max(1, int(img.shape[0] * scale))
        new_w = max(1, int(img.shape[1] * scale))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        scaled = cv2.resize(img, (new_w, new_h), interpolation=interp)
        result.append(scaled)

    return result


def harmonize_words(word_images: list[np.ndarray]) -> list[np.ndarray]:
    """Apply height harmonization first, then stroke weight.

    Height harmonization resizes images (via interpolation), which shifts
    ink pixel values. Applying stroke weight harmonization last ensures
    the final ink medians converge properly.
    """
    result = harmonize_heights(word_images)
    result = harmonize_stroke_weight(result)
    return result
