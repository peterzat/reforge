"""Length-aware font normalization.

Unified height-based strategy: all words normalize ink height toward a
consistent target. Short words (1-3 chars) use a lower target because
DiffusionPen renders them at full canvas height, producing oversized glyphs.
"""

import cv2
import numpy as np

from reforge.config import SHORT_WORD_HEIGHT_TARGET


def compute_ink_height(img: np.ndarray) -> int:
    """Compute vertical extent of ink."""
    ink_rows = np.any(img < 180, axis=1)
    if not np.any(ink_rows):
        return img.shape[0]
    first = np.argmax(ink_rows)
    last = len(ink_rows) - 1 - np.argmax(ink_rows[::-1])
    return max(1, last - first + 1)


def normalize_font_size(img: np.ndarray, word: str) -> np.ndarray:
    """Normalize a word image to consistent ink height.

    All words normalize by ink height. Short words (1-3 chars) target
    SHORT_WORD_HEIGHT_TARGET; longer words target a slightly higher value
    (SHORT_WORD_HEIGHT_TARGET * 1.1) to account for their denser ink.
    """
    current_height = compute_ink_height(img)
    if current_height <= 0:
        return img

    word_len = len(word.strip())

    if word_len <= 3:
        target_height = SHORT_WORD_HEIGHT_TARGET
    else:
        # Slightly higher target for longer words to account for denser ink
        target_height = int(SHORT_WORD_HEIGHT_TARGET * 1.1)

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
