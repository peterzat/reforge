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


def compute_x_height(img: np.ndarray) -> int:
    """Compute x-height: distance from baseline to top of lowercase body.

    Excludes ascenders (t, l, h tops) and descenders (g, y tails) by
    finding the densest horizontal band of ink. The x-height is the
    vertical extent of the row range where ink density stays above 50%
    of the peak density.

    Falls back to total ink height if the image has no clear body zone.
    Returns at least 1.
    """
    ink_mask = img < 180
    row_density = np.mean(ink_mask, axis=1)

    if not np.any(row_density > 0.01):
        return max(1, img.shape[0])

    # Find ink extent
    ink_rows = row_density > 0.01
    first_ink = int(np.argmax(ink_rows))
    last_ink = len(ink_rows) - 1 - int(np.argmax(ink_rows[::-1]))
    ink_h = last_ink - first_ink + 1

    if ink_h < 3:
        return max(1, ink_h)

    # Find peak density and the body zone (rows >= 50% of peak)
    peak_density = np.max(row_density[first_ink:last_ink + 1])
    body_threshold = peak_density * 0.50

    body_rows = row_density >= body_threshold
    body_indices = np.where(body_rows)[0]
    if len(body_indices) < 2:
        return max(1, ink_h)

    body_top = int(body_indices[0])
    body_bottom = int(body_indices[-1])
    x_height = body_bottom - body_top + 1

    return max(1, x_height)
