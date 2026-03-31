"""Length-aware font normalization.

Dual strategy:
- Short words (1-3 chars): normalize by ink height (target ~24px)
- Long words (4+ chars): normalize by area per character (target ~1500 px^2)
"""

import cv2
import numpy as np

from reforge.config import LONG_WORD_AREA_TARGET, SHORT_WORD_HEIGHT_TARGET


def compute_ink_area(img: np.ndarray) -> int:
    """Count the number of ink pixels in an image."""
    return int(np.sum(img < 180))


def compute_ink_height(img: np.ndarray) -> int:
    """Compute vertical extent of ink."""
    ink_rows = np.any(img < 180, axis=1)
    if not np.any(ink_rows):
        return img.shape[0]
    first = np.argmax(ink_rows)
    last = len(ink_rows) - 1 - np.argmax(ink_rows[::-1])
    return max(1, last - first + 1)


def normalize_font_size(img: np.ndarray, word: str) -> np.ndarray:
    """Normalize a word image based on word length.

    Short words (1-3 chars): normalize by ink height to SHORT_WORD_HEIGHT_TARGET.
    Long words (4+ chars): normalize by area per char to LONG_WORD_AREA_TARGET.
    """
    word_len = len(word.strip())

    if word_len <= 3:
        # Height-based normalization
        current_height = compute_ink_height(img)
        if current_height <= 0:
            return img
        scale = SHORT_WORD_HEIGHT_TARGET / current_height
    else:
        # Area-based normalization
        current_area = compute_ink_area(img)
        if current_area <= 0:
            return img
        target_area = LONG_WORD_AREA_TARGET * word_len
        current_area_per_char = current_area / word_len
        scale = np.sqrt(LONG_WORD_AREA_TARGET / max(1, current_area_per_char))

    # Clamp scale to avoid extreme resizing
    scale = np.clip(scale, 0.3, 3.0)

    if abs(scale - 1.0) < 0.05:
        return img

    new_h = max(1, int(img.shape[0] * scale))
    new_w = max(1, int(img.shape[1] * scale))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def normalize_font_sizes(
    word_images: list[np.ndarray], words: list[str]
) -> list[np.ndarray]:
    """Apply length-aware font normalization to all word images."""
    return [normalize_font_size(img, word) for img, word in zip(word_images, words)]
