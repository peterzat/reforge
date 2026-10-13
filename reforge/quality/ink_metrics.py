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


# Mirrors model.generator.SYNTHETIC_MARKS (not imported: generator pulls torch).
TRAILING_MARKS = ",.?!;"


def drop_trailing_mark_runs(img: np.ndarray, word: str) -> np.ndarray:
    """Crop off synthetic trailing marks so only the base word remains.

    Marks are attached after a tight crop plus a 1px gap, so each one is its
    own ink column run at the right edge. Row coordinates are unchanged, so
    rows measured on the result (baselines, x-height) apply to ``img``.
    Returns ``img`` unchanged when the word has no trailing marks or the
    image does not have enough column runs to separate them.
    """
    stripped = word.strip()
    n_marks = len(stripped) - len(stripped.rstrip(TRAILING_MARKS))
    if n_marks == 0 or n_marks == len(stripped):
        return img
    cols = np.any(img < 180, axis=0).astype(np.int8)
    starts = np.flatnonzero(np.diff(np.concatenate(([0], cols))) == 1)
    if len(starts) <= n_marks:
        return img
    return img[:, :starts[-n_marks]]


def compute_x_height_subpixel(img: np.ndarray, frac: float = 0.5) -> float:
    """Body-band height with sub-pixel edges.

    Same band as compute_x_height (rows whose ink density is at least
    ``frac`` of the peak), but each edge is placed where the density profile
    crosses the threshold, interpolated between rows. Measurements move
    continuously with the image instead of in whole-pixel steps.
    """
    d = np.mean(img < 180, axis=1)
    if d.size == 0 or d.max() <= 0:
        return 0.0
    t = d.max() * frac
    idx = np.flatnonzero(d >= t)
    top, bot = int(idx[0]), int(idx[-1])

    def _overshoot(inside: int, outside: int) -> float:
        return (d[inside] - t) / max(d[inside] - d[outside], 1e-9)

    top_edge = top - (_overshoot(top, top - 1) if top > 0 else 0.0)
    bot_edge = bot + (_overshoot(bot, bot + 1) if bot + 1 < len(d) else 0.0)
    return float(bot_edge - top_edge)
