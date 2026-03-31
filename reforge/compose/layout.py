"""Line wrapping, baseline detection, and paragraph layout.

Baseline detection accounts for thin and looped descenders using
top-down scanning from midpoint.
"""

import numpy as np

from reforge.config import (
    BASELINE_BODY_DENSITY,
    BASELINE_DENSITY_DROP,
    BASELINE_MIN_DIP_RATIO,
    DEFAULT_PAGE_WIDTH,
    PAGE_MARGIN,
    PARAGRAPH_INDENT,
    WORD_SPACING,
)


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
) -> list[dict]:
    """Compute positions for words on the page with line wrapping.

    None entries in word_images indicate paragraph breaks.

    Returns list of dicts with keys: x, y, word_idx, line, is_paragraph_start.
    """
    margin = PAGE_MARGIN
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
