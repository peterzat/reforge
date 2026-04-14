"""Word compositing onto canvas with upscaling and halo cleanup.

Implements compositor ink-only compositing (Layer 4) and
post-upscale halo cleanup (Layer 5). Uses a ruled-line model (F1)
for vertical positioning: non-descending words align their ink
bottom to the line's ruled baseline; descending words align their
body bottom (above descender) to the ruled baseline.
"""

import cv2
import numpy as np
from PIL import Image

from reforge.config import (
    COMPOSITOR_INK_THRESHOLD,
    DEFAULT_PAGE_WIDTH,
    LINE_SPACING,
    PAGE_MARGIN,
    PARAGRAPH_SPACING,
)
from reforge.compose.layout import (
    compute_page_width,
    compute_word_positions,
    detect_baseline,
)
from reforge.model.generator import halo_cleanup

# Descender detection threshold (F2): ink extending more than this
# fraction of ink height below the baseline indicates a descender.
DESCENDER_FRACTION = 0.15


def _has_descender(img: np.ndarray, baseline: int) -> bool:
    """Detect whether a word image has ink descending below the baseline (F2).

    A word has a descender if ink extends more than DESCENDER_FRACTION of
    total ink height below the detected baseline.
    """
    ink_rows = np.any(img < 180, axis=1)
    if not np.any(ink_rows):
        return False
    first_ink = int(np.argmax(ink_rows))
    last_ink = len(ink_rows) - 1 - int(np.argmax(ink_rows[::-1]))
    ink_height = last_ink - first_ink + 1
    if ink_height < 3:
        return False
    below_baseline = last_ink - baseline
    return below_baseline > ink_height * DESCENDER_FRACTION


def compose_words(
    word_images: list,
    words: list,
    page_width: int | None = None,
    upscale_factor: int = 2,
    return_positions: bool = False,
    page_ratio: str = "auto",
) -> Image.Image | tuple:
    """Compose word images onto a canvas with baseline alignment.

    None entries in word_images / words indicate paragraph breaks.

    Args:
        word_images: List of grayscale uint8 arrays (or None for paragraph break).
        words: List of word strings (or None for paragraph break).
        page_width: Canvas width in pixels. If None with page_ratio="auto",
            computed dynamically based on text volume.
        upscale_factor: Upscale factor for final output.
        return_positions: If True, return (image, adjusted_positions) tuple.
        page_ratio: "auto" for dynamic page width, or explicit width override.

    Returns:
        PIL Image in mode "L" (grayscale), or tuple of (Image, positions)
        if return_positions is True. Positions reflect baseline-adjusted y values.
    """
    # Tight-crop word images horizontally to ink bounds.
    # Generated images have large white padding (e.g. 30px each side for short
    # words) that makes WORD_SPACING ineffective. Horizontal cropping ensures
    # the layout engine controls the actual visual gap between words.
    # Vertical dimensions are preserved for baseline alignment.
    word_images = list(word_images)  # avoid mutating caller's list
    for i, img in enumerate(word_images):
        if img is None:
            continue
        ink_cols = np.any(img < COMPOSITOR_INK_THRESHOLD, axis=0)
        if not np.any(ink_cols):
            continue
        left = int(np.argmax(ink_cols))
        right = len(ink_cols) - 1 - int(np.argmax(ink_cols[::-1]))
        pad = 2  # minimal margin to avoid clipping antialiased edges
        left = max(0, left - pad)
        right = min(img.shape[1] - 1, right + pad)
        word_images[i] = img[:, left:right + 1]

    # Compute dynamic page width if not explicitly set
    if page_width is None:
        if page_ratio == "auto":
            real_imgs = [img for img in word_images if img is not None]
            if real_imgs:
                avg_w = float(np.mean([img.shape[1] for img in real_imgs]))
                avg_h = float(np.mean([img.shape[0] for img in real_imgs]))
                page_width = compute_page_width(len(real_imgs), avg_w, avg_h)
            else:
                page_width = DEFAULT_PAGE_WIDTH
        else:
            page_width = DEFAULT_PAGE_WIDTH

    # Compute proportional horizontal margin
    margin_h = int(page_width * 0.06)
    margin_h = max(int(page_width * 0.05), min(margin_h, int(page_width * 0.08)))

    positions = compute_word_positions(word_images, words, page_width, margin_h=margin_h)

    if not positions:
        return Image.new("L", (page_width, 100), 255)

    # Detect baselines for each word (F1)
    baselines = {}
    for pos in positions:
        idx = pos["word_idx"]
        img = word_images[idx]
        if img is not None:
            word_text = words[idx] if idx < len(words) and words[idx] is not None else None
            baselines[idx] = detect_baseline(img, word=word_text)

    # Group positions by line
    lines = {}
    for pos in positions:
        line_num = pos["line"]
        if line_num not in lines:
            lines[line_num] = []
        lines[line_num].append(pos)

    # Ruled-line model (F1): for each line, the ruled baseline is computed
    # from the median of per-word baselines. Using median instead of max
    # makes baseline robust to individual words with bad detection (e.g.
    # descender-heavy words where the density scan misfires). Outlier
    # baselines (> 20% from median) are clamped to the median.
    line_baselines = {}
    for line_num, line_positions in lines.items():
        word_baselines = []
        for pos in line_positions:
            idx = pos["word_idx"]
            if idx in baselines:
                word_baselines.append(baselines[idx])
        if not word_baselines:
            line_baselines[line_num] = 0
            continue
        median_bl = int(np.median(word_baselines))
        # Clamp outliers: snap baselines > 20% from median to the median
        for pos in line_positions:
            idx = pos["word_idx"]
            if idx in baselines:
                deviation = abs(baselines[idx] - median_bl)
                if median_bl > 0 and deviation / median_bl > 0.20:
                    baselines[idx] = median_bl
        line_baselines[line_num] = median_bl

    # Pre-compute y-offsets using ruled-line model (F1) + micro-jitter (F3)
    jitter_rng = np.random.RandomState(42)
    y_offsets = {}
    for pos in positions:
        idx = pos["word_idx"]
        img = word_images[idx]
        if img is None:
            continue
        line_num = pos["line"]
        shared_bl = line_baselines[line_num]
        word_bl = baselines.get(idx, img.shape[0] - 1)
        offset = shared_bl - word_bl
        offset += int(jitter_rng.randint(-1, 2))  # F3: +/- 1px jitter
        y_offsets[idx] = offset

    # Compute canvas height
    max_y = 0
    for pos in positions:
        idx = pos["word_idx"]
        img = word_images[idx]
        if img is None:
            continue
        y_adjusted = pos["y"] + y_offsets.get(idx, 0)
        bottom = y_adjusted + img.shape[0]
        max_y = max(max_y, bottom)

    content_h = int(max_y)
    # Proportional vertical margin (3-5% of estimated page height)
    margin_v = max(int(content_h * 0.04), int(content_h * 0.03))
    margin_v = min(margin_v, int(content_h * 0.06))
    canvas_h = content_h + 2 * margin_v
    canvas = np.full((canvas_h, page_width), 255, dtype=np.uint8)

    # Composite each word (Layer 4: ink-only compositing)
    adjusted_positions = []
    for pos in positions:
        idx = pos["word_idx"]
        img = word_images[idx]
        if img is None:
            continue

        y_adjusted = pos["y"] + y_offsets.get(idx, 0) + margin_v

        # Record baseline-adjusted position
        adj = dict(pos)
        adj["y"] = int(y_adjusted)
        adjusted_positions.append(adj)

        x_start = pos["x"]
        y_start = int(y_adjusted)

        h, w = img.shape[:2]
        # Clip to canvas bounds
        y_end = min(y_start + h, canvas_h)
        x_end = min(x_start + w, page_width)
        src_h = y_end - y_start
        src_w = x_end - x_start

        if y_start < 0 or x_start < 0 or src_h <= 0 or src_w <= 0:
            continue

        # Layer 4: Only composite ink pixels (< threshold)
        src_region = img[:src_h, :src_w]
        ink_mask = src_region < COMPOSITOR_INK_THRESHOLD
        canvas_region = canvas[y_start:y_end, x_start:x_end]
        canvas_region[ink_mask] = src_region[ink_mask]

    # Trim bottom: match bottom margin to top margin (margin_v)
    # Find last row with ink
    last_ink_row = canvas_h - 1
    for r in range(canvas_h - 1, -1, -1):
        if np.any(canvas[r] < 250):
            last_ink_row = r
            break
    trimmed_h = last_ink_row + margin_v + 1
    if trimmed_h < canvas_h:
        canvas = canvas[:trimmed_h]

    # Upscale
    if upscale_factor > 1:
        new_h = canvas.shape[0] * upscale_factor
        new_w = canvas.shape[1] * upscale_factor
        canvas = cv2.resize(canvas, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

        # Layer 5: Post-upscale halo cleanup
        canvas = halo_cleanup(canvas)

    result = Image.fromarray(canvas, mode="L")
    if return_positions:
        return result, adjusted_positions
    return result
