"""Length-aware and case-aware font normalization.

Unified height-based strategy with case-aware adjustments. All-caps and
single-capital words use a lower target because DiffusionPen renders them
at full canvas height, making them visually oversized compared to lowercase
words. In real handwriting, cap height is roughly 70% of total ink height
when descenders are present.
"""

import cv2
import numpy as np

from reforge.config import SHORT_WORD_HEIGHT_TARGET
from reforge.quality.ink_metrics import compute_ink_height  # noqa: F401 (re-exported)

# Cap height ratio: in natural handwriting, uppercase letters are roughly
# this fraction of the total ink height of words with ascenders/descenders.
# Human feedback: "lowercase body should be roughly 1/2 the size of capital I."
# Cap height ~= 1.3x x-height, total ink height ~= 1.8x x-height (with
# descenders), so cap height / total ~= 0.72.
CAP_HEIGHT_RATIO = 0.72


def _is_all_caps(word: str) -> bool:
    """Check if a word is all uppercase letters (ignoring punctuation)."""
    alpha_chars = [c for c in word if c.isalpha()]
    return len(alpha_chars) > 0 and all(c.isupper() for c in alpha_chars)


def normalize_font_size(img: np.ndarray, word: str) -> np.ndarray:
    """Normalize a word image to consistent ink height.

    Case-aware: all-caps words (including single capital letters like "I")
    use a lower target height so they don't tower over lowercase words.
    In real handwriting, cap height is shorter than the full extent of
    lowercase words with ascenders and descenders.
    """
    current_height = compute_ink_height(img)
    if current_height <= 0:
        return img

    word_stripped = word.strip()
    word_len = len(word_stripped)

    # Base target: standard height for most words
    base_target = int(SHORT_WORD_HEIGHT_TARGET * 1.08)

    if word_len <= 2 and not _is_all_caps(word_stripped):
        target_height = SHORT_WORD_HEIGHT_TARGET
    elif _is_all_caps(word_stripped):
        # All-caps words: scale down to cap height ratio of the base target.
        # This prevents "I", "A", "THE" from towering over lowercase words.
        target_height = int(base_target * CAP_HEIGHT_RATIO)
    else:
        target_height = base_target

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
