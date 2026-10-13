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


_STRONG_ASCENDERS = set("bdfhkl'") | set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
_WEAK_ASCENDERS = set("t")
_DESCENDERS = set("gjpqy")


def zone_class(word: str) -> tuple[int, int]:
    """(ascender 0/1/2, descender 0/1) for a word, ignoring trailing marks."""
    core = word.strip().rstrip(".,;:!?\"")
    if any(c in _STRONG_ASCENDERS for c in core):
        asc = 2
    elif any(c in _WEAK_ASCENDERS for c in core):
        asc = 1
    else:
        asc = 0
    return asc, int(any(c in _DESCENDERS for c in core))


def estimate_x_height(img: np.ndarray, word: str) -> float:
    """x-height of a word image in pixels, robust on short words.

    The word's ink height in x-heights is predicted from its letters
    (ZONE_HEIGHT_RATIOS). For words of 4+ letters the prediction is blended
    toward the measured ink/x-height ratio (up to 75% weight at 6+ letters):
    long words have a dense, measurable body band, while short words do not
    (compute_x_height reads "it" as 5-9px of a 64px word).
    """
    from reforge.config import ZONE_HEIGHT_RATIOS

    ink_h = compute_ink_height(img)
    prior = ZONE_HEIGHT_RATIOS[zone_class(word)]
    measured = float(np.clip(ink_h / max(compute_x_height(img), 1), 1.0, 3.5))
    n_letters = len(word.strip().strip(".,;:!?\"'"))
    weight = float(np.clip((n_letters - 3) / 4, 0.0, 0.75))
    ratio = prior ** (1 - weight) * measured ** weight
    return ink_h / ratio


def plan_zone_scales(word_images: list[np.ndarray], words: list[str]) -> list[float]:
    """Scale each word so its estimated x-height lands on ZONE_X_HEIGHT_TARGET."""
    from reforge.config import ZONE_X_HEIGHT_TARGET

    return [
        float(np.clip(ZONE_X_HEIGHT_TARGET / estimate_x_height(img, word), 0.15, 1.6))
        for img, word in zip(word_images, words)
    ]


def plan_word_scales(
    word_images: list[np.ndarray], words: list[str], policy: str | None = None,
) -> list[float]:
    """One scale factor per word under the configured SIZING_POLICY.

    ``policy="zone"`` delegates to ``plan_zone_scales``. ``"total_height"``
    composes the legacy passes, described below.

    Runs the same decisions as ``normalize_font_size`` ->
    ``equalize_body_zones`` -> ``harmonize_heights`` ->
    ``harmonize_heights_pass2``, but on measurements taken once from the
    unscaled images (ink height and x-height scale linearly with the image).

    Applying those passes image-by-image resampled each word up to four
    times. Short all-body words were shrunk to ~0.2x by the body-zone pass
    and re-inflated to ~0.4x by the height passes, losing their dark ink at
    the bottleneck; thin strokes that fell below the ink threshold also
    corrupted the next pass's measurements (audit 2026-10-13).
    """
    from reforge.config import (
        HEIGHT_OUTLIER_THRESHOLD,
        HEIGHT_OUTLIER_THRESHOLD_PASS2,
        HEIGHT_UNDERSIZE_THRESHOLD,
        HEIGHT_UNDERSIZE_THRESHOLD_PASS2,
        SIZING_POLICY,
    )

    policy = policy or SIZING_POLICY
    if policy == "zone":
        return plan_zone_scales(word_images, words)
    if policy != "total_height":
        raise ValueError(f"unknown SIZING_POLICY {policy!r}")

    n = len(word_images)
    ink_h = np.array([compute_ink_height(img) for img in word_images], dtype=np.float64)
    x_h = np.array([compute_x_height(img) for img in word_images], dtype=np.float64)
    scales = np.ones(n, dtype=np.float64)

    # normalize_font_size
    for i, word in enumerate(words):
        target = (
            SHORT_WORD_HEIGHT_TARGET
            if len(word.strip()) <= 2
            else int(SHORT_WORD_HEIGHT_TARGET * 1.08)
        )
        s = float(np.clip(target / ink_h[i], 0.3, 1.6))
        scales[i] = 1.0 if abs(s - 1.0) < 0.05 else s

    # equalize_body_zones (scale down body-zone outliers, up to 3 rounds)
    if n >= 3:
        for _ in range(3):
            eff = np.where(
                (x_h * scales < 5) | (x_h >= ink_h), ink_h * scales, x_h * scales
            )
            median_xh = float(np.median(eff))
            if median_xh <= 0:
                break
            upper = median_xh * 1.05
            over = eff > upper
            if not np.any(over):
                break
            scales[over] *= upper / eff[over]

    # harmonize_heights, then harmonize_heights_pass2
    for hi, lo in (
        (HEIGHT_OUTLIER_THRESHOLD, HEIGHT_UNDERSIZE_THRESHOLD),
        (HEIGHT_OUTLIER_THRESHOLD_PASS2, HEIGHT_UNDERSIZE_THRESHOLD_PASS2),
    ):
        if n == 0:
            break
        h = ink_h * scales
        median_h = float(np.median(h))
        upper, lower = median_h * hi, median_h * lo
        scales = np.where(h > upper, scales * upper / h, scales)
        scales = np.where(h < lower, scales * lower / h, scales)

    return [float(s) for s in scales]


def size_words(
    word_images: list[np.ndarray], words: list[str], policy: str | None = None,
) -> list[np.ndarray]:
    """Resize each word once by its planned scale (see ``plan_word_scales``)."""
    scales = plan_word_scales(word_images, words, policy)
    result = []
    for img, word, s in zip(word_images, words, scales):
        if abs(s - 1.0) < 1e-6:
            result.append(img)
            continue
        new_h = max(1, int(round(img.shape[0] * s)))
        new_w = max(1, int(round(img.shape[1] * s)))
        interp = cv2.INTER_AREA if s < 1.0 else cv2.INTER_CUBIC
        out = cv2.resize(img, (new_w, new_h), interpolation=interp)
        if len(word.strip()) == 1 and s < 0.6:
            out = _reinforce_thin_strokes(out)
        result.append(out)
    return result


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
