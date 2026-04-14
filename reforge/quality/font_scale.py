"""Length-aware font normalization.

Unified height-based strategy: all words normalize ink height toward a
consistent target, then a cross-word x-height equalization pass corrects
body-zone outliers. This two-step approach keeps total heights consistent
(metric-friendly) while fixing the "gray too big" problem where words
without ascenders appear disproportionately large.
"""

import cv2
import numpy as np

from reforge.config import SHORT_WORD_HEIGHT_TARGET
from reforge.quality.ink_metrics import compute_ink_height  # noqa: F401 (re-exported)
from reforge.quality.ink_metrics import compute_x_height


def normalize_font_size(img: np.ndarray, word: str) -> np.ndarray:
    """Normalize a word image to consistent ink height.

    Uses total ink height as the primary normalization signal for
    stable cross-word consistency. Body-zone equalization is handled
    separately by equalize_body_zones() after all words are normalized.
    Short words (1-3 chars) use a lower target because DiffusionPen
    renders them at full canvas height.
    """
    current_height = compute_ink_height(img)
    if current_height <= 0:
        return img

    word_len = len(word.strip())

    if word_len <= 2:
        target_height = SHORT_WORD_HEIGHT_TARGET
    else:
        # All words 3+ chars get the same target for consistency.
        # The old split at 3 chars created an 8% jump between "the" (26px)
        # and "quick" (28px) that humans perceived as size inconsistency.
        target_height = int(SHORT_WORD_HEIGHT_TARGET * 1.08)

    scale = target_height / current_height

    # Clamp: allow moderate scaling in both directions
    scale = np.clip(scale, 0.3, 1.6)

    if abs(scale - 1.0) < 0.05:
        return img

    new_h = max(1, int(img.shape[0] * scale))
    new_w = max(1, int(img.shape[1] * scale))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    return cv2.resize(img, (new_w, new_h), interpolation=interp)


def normalize_font_sizes(
    word_images: list[np.ndarray], words: list[str]
) -> list[np.ndarray]:
    """Apply length-aware font normalization to all word images."""
    return [normalize_font_size(img, word) for img, word in zip(word_images, words)]


def _effective_x_height(img: np.ndarray) -> int:
    """X-height with degenerate fallback, for body-zone comparison."""
    ink_h = compute_ink_height(img)
    x_h = compute_x_height(img)
    if x_h < 5 or x_h >= ink_h:
        return ink_h
    return x_h


def equalize_body_zones(word_images: list[np.ndarray]) -> list[np.ndarray]:
    """Scale down words whose body zone (x-height) is disproportionately large.

    After ink-height normalization, words without ascenders (like "gray")
    have their entire height as body zone, while words with ascenders
    (like "jumping") have body + ascender. This makes "gray" appear
    bigger even though total heights are equal.

    Two-pass approach for stability:
    1. Scale down words whose x-height exceeds 105% of median
    2. Recompute and repeat for any remaining outliers

    Only scales DOWN (never up) to avoid inflating words that already
    look proportional.
    """
    if len(word_images) < 3:
        return word_images

    result = list(word_images)
    for _ in range(3):
        x_heights = [_effective_x_height(img) for img in result]
        median_xh = float(np.median(x_heights))
        if median_xh <= 0:
            break

        upper = median_xh * 1.05
        changed = False
        for i, (img, xh) in enumerate(zip(result, x_heights)):
            if xh <= upper:
                continue
            scale = upper / xh
            new_h = max(1, int(img.shape[0] * scale))
            new_w = max(1, int(img.shape[1] * scale))
            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
            result[i] = cv2.resize(img, (new_w, new_h), interpolation=interp)
            changed = True

        if not changed:
            break

    return result
