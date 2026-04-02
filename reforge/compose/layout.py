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
    LINE_SPACING,
    MARGIN_H_RATIO,
    MAX_PAGE_WIDTH,
    MIN_PAGE_WIDTH,
    PAGE_MARGIN,
    PARAGRAPH_INDENT,
    PARAGRAPH_SPACING,
    TARGET_WORDS_PER_LINE,
    WORD_SPACING,
)


def compute_page_width(
    word_count: int,
    avg_word_width: float,
    avg_word_height: float,
) -> int:
    """Compute page width targeting TARGET_WORDS_PER_LINE words per line.

    Sets the page width so that the usable area (after margins) fits
    approximately TARGET_WORDS_PER_LINE words. For short texts that would
    produce fewer than 3 lines, narrows the page to maintain a reasonable
    aspect ratio (max 0.85 width:height).
    """
    if word_count <= 0 or avg_word_width <= 0 or avg_word_height <= 0:
        return DEFAULT_PAGE_WIDTH

    # Width needed for TARGET_WORDS_PER_LINE words plus spacing
    content_w = TARGET_WORDS_PER_LINE * avg_word_width + (TARGET_WORDS_PER_LINE - 1) * WORD_SPACING
    # Add margins: margin_h = pw * MARGIN_H_RATIO, so pw = content_w / (1 - 2 * MARGIN_H_RATIO)
    pw = int(content_w / (1.0 - 2.0 * MARGIN_H_RATIO))
    pw = max(MIN_PAGE_WIDTH, min(pw, MAX_PAGE_WIDTH))

    # For short texts (fewer than 3 lines), narrow the page to avoid
    # very wide-and-short layouts.
    total_text_w = word_count * avg_word_width + (word_count - 1) * WORD_SPACING
    margin_h = int(pw * MARGIN_H_RATIO)
    usable = pw - 2 * margin_h
    if usable > 0:
        import math
        n_lines = max(1, math.ceil(total_text_w / usable))
        if n_lines < 3:
            # Not enough text for a full page. Narrow to fit the content
            # with a reasonable aspect ratio.
            line_height = avg_word_height + LINE_SPACING
            est_height = n_lines * line_height + PARAGRAPH_SPACING
            if est_height > 0:
                pw = max(MIN_PAGE_WIDTH, int(est_height * 0.75))

    return pw


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
    layout_seed: int = 137,
) -> list[dict]:
    """Compute positions for words on the page with line wrapping.

    None entries in word_images indicate paragraph breaks.

    Natural layout variations (seeded for reproducibility):
    - Per-word spacing jitter (+/- 4px)
    - Per-line ragged right margin (5-20% shorter, adjacent lines differ by 3%+)
    - Per-line starting x jitter (+/- 2px)

    Args:
        margin_h: Horizontal margin override. If None, uses PAGE_MARGIN.
        layout_seed: Seed for deterministic layout variation.

    Returns list of dicts with keys: x, y, word_idx, line, is_paragraph_start.
    """
    margin = margin_h if margin_h is not None else PAGE_MARGIN
    usable_width = page_width - 2 * margin
    rng = np.random.RandomState(layout_seed)

    # B1-B2: Pre-compute per-line ragged right shortening.
    # Alternating pattern with wide gap (0-5% vs 28-42%) ensures that
    # adjacent lines differ by at least one word width (~100px), which
    # produces the 8%+ right-edge std required by B1.
    max_lines = max(10, len([i for i in word_images if i is not None]) // 2 + 5)
    line_shorten = np.empty(max_lines)
    for j in range(max_lines):
        if j % 2 == 0:
            line_shorten[j] = rng.uniform(0.00, 0.05)   # full lines
        else:
            line_shorten[j] = rng.uniform(0.28, 0.42)    # short lines
    # Swap some pairs to break strict alternation
    for j in range(0, max_lines - 1, 4):
        if rng.random() < 0.3 and j + 1 < max_lines:
            line_shorten[j], line_shorten[j + 1] = line_shorten[j + 1], line_shorten[j]

    # D3: Per-line starting x jitter (+/- 2px)
    line_x_jitter = rng.randint(-2, 3, size=max_lines)  # -2 to +2

    # D1: Per-word spacing jitter (+/- 4px)
    word_count = len(word_images)
    spacing_jitter = rng.randint(-4, 5, size=max(1, word_count))  # -4 to +4

    positions = []
    x = margin
    y = 0
    line = 0
    is_paragraph_start = True
    max_line_height = 0
    word_on_line = 0

    for i, (img, word) in enumerate(zip(word_images, words)):
        if img is None:
            # Paragraph break sentinel
            if max_line_height > 0:
                y += max_line_height + PARAGRAPH_SPACING
            x = margin + PARAGRAPH_INDENT
            line += 1
            max_line_height = 0
            is_paragraph_start = True
            word_on_line = 0
            continue

        h, w = img.shape[:2]

        # D2: effective usable width for this line (ragged right)
        line_idx = min(line, max_lines - 1)
        effective_usable = usable_width * (1.0 - line_shorten[line_idx])

        # Check if word fits on current line
        if x + w > margin + effective_usable and x > margin + (PARAGRAPH_INDENT if is_paragraph_start else 0):
            # Wrap to next line
            y += max_line_height + LINE_SPACING
            x = margin
            line += 1
            max_line_height = 0
            is_paragraph_start = False
            word_on_line = 0

        if is_paragraph_start and x == margin:
            x = margin + PARAGRAPH_INDENT

        # D3: apply line start jitter to first word on each line
        line_idx = min(line, max_lines - 1)
        if word_on_line == 0 and not is_paragraph_start:
            x += line_x_jitter[line_idx]

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
        # D1: per-word spacing variation
        word_spacing = WORD_SPACING + spacing_jitter[min(i, word_count - 1)]
        x += w + max(4, word_spacing)  # floor at 4px to avoid overlap

        is_paragraph_start = False
        word_on_line += 1

    return positions
