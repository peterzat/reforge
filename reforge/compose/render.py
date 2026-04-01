"""Word compositing onto canvas with upscaling and halo cleanup.

Implements compositor ink-only compositing (Layer 4) and
post-upscale halo cleanup (Layer 5).
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
from reforge.compose.layout import compute_word_positions, detect_baseline
from reforge.model.generator import halo_cleanup


def compose_words(
    word_images: list,
    words: list,
    page_width: int = DEFAULT_PAGE_WIDTH,
    upscale_factor: int = 2,
    return_positions: bool = False,
) -> Image.Image | tuple:
    """Compose word images onto a canvas with baseline alignment.

    None entries in word_images / words indicate paragraph breaks.

    Args:
        word_images: List of grayscale uint8 arrays (or None for paragraph break).
        words: List of word strings (or None for paragraph break).
        page_width: Canvas width in pixels.
        upscale_factor: Upscale factor for final output.
        return_positions: If True, return (image, adjusted_positions) tuple.

    Returns:
        PIL Image in mode "L" (grayscale), or tuple of (Image, positions)
        if return_positions is True. Positions reflect baseline-adjusted y values.
    """
    positions = compute_word_positions(word_images, words, page_width)

    if not positions:
        return Image.new("L", (page_width, 100), 255)

    # Detect baselines for each word
    baselines = {}
    for pos in positions:
        idx = pos["word_idx"]
        img = word_images[idx]
        if img is not None:
            baselines[idx] = detect_baseline(img)

    # Group positions by line and compute shared baseline per line
    lines = {}
    for pos in positions:
        line_num = pos["line"]
        if line_num not in lines:
            lines[line_num] = []
        lines[line_num].append(pos)

    # For each line, shared baseline = max baseline offset
    line_baselines = {}
    for line_num, line_positions in lines.items():
        max_baseline = 0
        for pos in line_positions:
            idx = pos["word_idx"]
            if idx in baselines:
                max_baseline = max(max_baseline, baselines[idx])
        line_baselines[line_num] = max_baseline

    # Compute canvas height
    max_y = 0
    for pos in positions:
        idx = pos["word_idx"]
        img = word_images[idx]
        if img is None:
            continue
        line_num = pos["line"]
        shared_bl = line_baselines[line_num]
        word_bl = baselines.get(idx, img.shape[0] - 1)
        # y position adjusted for baseline alignment
        y_adjusted = pos["y"] + (shared_bl - word_bl)
        bottom = y_adjusted + img.shape[0]
        max_y = max(max_y, bottom)

    canvas_h = int(max_y + PAGE_MARGIN)
    canvas = np.full((canvas_h, page_width), 255, dtype=np.uint8)

    # Composite each word (Layer 4: ink-only compositing)
    adjusted_positions = []
    for pos in positions:
        idx = pos["word_idx"]
        img = word_images[idx]
        if img is None:
            continue

        line_num = pos["line"]
        shared_bl = line_baselines[line_num]
        word_bl = baselines.get(idx, img.shape[0] - 1)
        y_adjusted = pos["y"] + (shared_bl - word_bl)

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
