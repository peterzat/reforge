"""Line wrapping, baseline detection, and paragraph layout.

Baseline detection accounts for thin and looped descenders using
top-down scanning from midpoint.
"""

import math

import numpy as np

from reforge.config import (
    BASELINE_BODY_DENSITY,
    BASELINE_DENSITY_DROP,
    BASELINE_MIN_DIP_RATIO,
    DEFAULT_PAGE_WIDTH,
    LINE_SPACING,
    MARGIN_H_RATIO,
    MAX_PAGE_WIDTH,
    MIN_PAGE_WIDTH,
    PAGE_MARGIN,
    PARAGRAPH_INDENT,
    PARAGRAPH_SPACING,
    TARGET_ASPECT_MAX,
    TARGET_ASPECT_MIN,
    WORD_SPACING,
)


def compute_page_width(
    word_count: int,
    avg_word_width: float,
    avg_word_height: float,
) -> int:
    """Compute page width that targets a near-square aspect ratio.

    Estimates the page height for a given width, then picks the width
    that brings the aspect ratio closest to 1.0 within the allowed range.
    """
    if word_count <= 0 or avg_word_width <= 0 or avg_word_height <= 0:
        return DEFAULT_PAGE_WIDTH

    # Total text width if everything were on one line
    total_text_w = word_count * avg_word_width + (word_count - 1) * WORD_SPACING
    line_height = avg_word_height + LINE_SPACING

    best_width = DEFAULT_PAGE_WIDTH
    best_diff = float("inf")

    # Search over candidate widths
    for pw in range(MIN_PAGE_WIDTH, MAX_PAGE_WIDTH + 1, 10):
        margin_h = int(pw * MARGIN_H_RATIO)
        usable = pw - 2 * margin_h - PARAGRAPH_INDENT
        if usable <= 0:
            continue
        # Estimate number of lines (first line has indent)
        first_line_w = usable
        remaining_w = total_text_w - first_line_w
        if remaining_w <= 0:
            n_lines = 1
        else:
            full_usable = pw - 2 * margin_h
            n_lines = 1 + math.ceil(remaining_w / max(1, full_usable))

        est_height = n_lines * line_height + PARAGRAPH_SPACING
        if est_height <= 0:
            continue
        ratio = pw / est_height
        # Distance from target range midpoint (1.0)
        if TARGET_ASPECT_MIN <= ratio <= TARGET_ASPECT_MAX:
            diff = abs(ratio - 1.0)
        else:
            diff = min(abs(ratio - TARGET_ASPECT_MIN), abs(ratio - TARGET_ASPECT_MAX)) + 1.0
        if diff < best_diff:
            best_diff = diff
            best_width = pw

    return best_width


def compute_margins(page_width: int, page_height: int) -> tuple[int, int]:
    """Compute proportional margins.

    Returns (margin_h, margin_v) where:
    - margin_h is 5-8% of page_width (clamped)
    - margin_v is 3-5% of page_height (clamped)
    """
    margin_h = max(
        int(page_width * 0.05),
        min(int(page_width * MARGIN_H_RATIO), int(page_width * 0.08)),
    )
    margin_v = max(
        int(page_height * 0.03),
        min(int(page_height * 0.04), int(page_height * 0.05)),
    )
    return margin_h, margin_v


def detect_baseline(img: np.ndarray) -> int:
    """Detect the baseline of a word image.

    Uses top-down scan from midpoint, looking for density drop below 15%
    with no body rows below. Walks back to last 35%-density row.
    Rejects spurious dips < 15% of total ink height.
    """
    ink_mask = img < 180
    row_density = np.mean(ink_mask, axis=1)

    # Find ink extent
    ink_rows = row_density > 0.01
    if not np.any(ink_rows):
        return img.shape[0] - 1

    first_ink = int(np.argmax(ink_rows))
    last_ink = len(ink_rows) - 1 - int(np.argmax(ink_rows[::-1]))
    ink_height = last_ink - first_ink + 1

    if ink_height < 3:
        return last_ink

    mid = first_ink + ink_height // 2

    # Scan down from midpoint looking for density drop
    baseline = last_ink
    for r in range(mid, last_ink + 1):
        if row_density[r] < BASELINE_DENSITY_DROP:
            # Check if there are body rows below this
            has_body_below = False
            for rb in range(r + 1, last_ink + 1):
                if row_density[rb] >= BASELINE_BODY_DENSITY:
                    has_body_below = True
                    break

            if not has_body_below:
                # Check this isn't a spurious dip
                dip_height = last_ink - r
                if dip_height >= ink_height * BASELINE_MIN_DIP_RATIO:
                    # Walk back to last body-density row
                    for rb in range(r, mid - 1, -1):
                        if row_density[rb] >= BASELINE_BODY_DENSITY:
                            baseline = rb
                            break
                    break

    return baseline


def compute_word_positions(
    word_images: list,
    words: list,
    page_width: int = DEFAULT_PAGE_WIDTH,
    margin_h: int | None = None,
) -> list[dict]:
    """Compute positions for words on the page with line wrapping.

    None entries in word_images indicate paragraph breaks.

    Args:
        margin_h: Horizontal margin override. If None, uses PAGE_MARGIN.

    Returns list of dicts with keys: x, y, word_idx, line, is_paragraph_start.
    """
    margin = margin_h if margin_h is not None else PAGE_MARGIN
    usable_width = page_width - 2 * margin

    positions = []
    x = margin
    y = 0
    line = 0
    is_paragraph_start = True
    max_line_height = 0

    for i, (img, word) in enumerate(zip(word_images, words)):
        if img is None:
            # Paragraph break sentinel
            if max_line_height > 0:
                from reforge.config import PARAGRAPH_SPACING
                y += max_line_height + PARAGRAPH_SPACING
            x = margin + PARAGRAPH_INDENT
            line += 1
            max_line_height = 0
            is_paragraph_start = True
            continue

        h, w = img.shape[:2]

        # Check if word fits on current line
        if x + w > margin + usable_width and x > margin + (PARAGRAPH_INDENT if is_paragraph_start else 0):
            # Wrap to next line
            from reforge.config import LINE_SPACING
            y += max_line_height + LINE_SPACING
            x = margin
            line += 1
            max_line_height = 0
            is_paragraph_start = False

        if is_paragraph_start and x == margin:
            x = margin + PARAGRAPH_INDENT

        positions.append({
            "x": x,
            "y": y,
            "word_idx": i,
            "line": line,
            "is_paragraph_start": is_paragraph_start,
            "width": w,
            "height": h,
        })

        max_line_height = max(max_line_height, h)
        x += w + WORD_SPACING
        is_paragraph_start = False

    return positions
