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
    result = cv2.resize(img, (new_w, new_h), interpolation=interp)

    # Single-char words with aggressive downscaling lose ink: INTER_AREA
    # averages a 2-3px stroke into 1px of gray. Reinforce by darkening
    # faint pixels that were created by the averaging.
    if word_len == 1 and scale < 0.6:
        result = _reinforce_thin_strokes(result)

    return result


def _reinforce_thin_strokes(img: np.ndarray) -> np.ndarray:
    """Darken faint ink pixels created by INTER_AREA averaging.

    When a thin stroke (2-3px) is scaled down by 0.4-0.6x, INTER_AREA
    produces gray (120-200) pixels instead of preserving the dark ink.
    This re-darkens those faint pixels so the stroke remains legible.

    Set ``REFORGE_DISABLE_REINFORCEMENT=1`` to short-circuit this path
    (used by the spec 2026-04-17 A variance check to compare HEAD against
    a no-op baseline).
    """
    import os
    if os.environ.get("REFORGE_DISABLE_REINFORCEMENT", "") == "1":
        return img
    # Find pixels that have some ink signal but are washed out
    faint_ink = (img >= 80) & (img < 200)
    if not np.any(faint_ink):
        return img
    result = img.copy()
    # Pull faint ink darker: 0.65x scales [80, 200] toward [52, 130].
    # Preserves the gradient (anti-aliasing) while making ink visible.
    result_f = result.astype(np.float32)
    result_f[faint_ink] = result_f[faint_ink] * 0.65
    return np.clip(result_f, 0, 255).astype(np.uint8)


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
