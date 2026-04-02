"""Shared ink measurement utilities for quality modules."""

import numpy as np


def compute_ink_height(img: np.ndarray) -> int:
    """Compute vertical extent of ink.

    Returns at least 1 to prevent division-by-zero in downstream callers.
    """
    ink_rows = np.any(img < 180, axis=1)
    if not np.any(ink_rows):
        return img.shape[0]
    first = np.argmax(ink_rows)
    last = len(ink_rows) - 1 - np.argmax(ink_rows[::-1])
    return max(1, last - first + 1)
