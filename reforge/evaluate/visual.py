"""CV-based quality evaluation functions.

Each function takes numpy array inputs and returns numeric scores.
These enable autonomous quality validation without manual visual inspection.
"""

import cv2
import numpy as np


def check_gray_boxes(img: np.ndarray) -> bool:
    """Detect rectangular gray artifacts in the image.

    Returns True if gray boxes are detected (bad), False if clean.
    """
    if img.size == 0:
        return False

    # Look for rectangular regions of consistent gray (150-220 range)
    gray_mask = (img > 140) & (img < 220)
    gray_ratio = np.mean(gray_mask)

    # If a large fraction is gray, likely has gray box artifacts
    if gray_ratio < 0.05:
        return False

    # Check for rectangular structure using connected components
    gray_uint8 = gray_mask.astype(np.uint8) * 255
    contours, _ = cv2.findContours(gray_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 100:
            continue
        # Check rectangularity
        x, y, w, h = cv2.boundingRect(contour)
        rect_area = w * h
        if rect_area == 0:
            continue
        fill_ratio = area / rect_area
        # Gray boxes tend to be highly rectangular
        if fill_ratio > 0.7 and w > 20 and h > 10:
            return True

    return False


def check_ink_contrast(img: np.ndarray) -> float:
    """Compute ink-to-background contrast ratio.

    Returns a score in [0, 1] where higher means better contrast.
    """
    if img.size == 0:
        return 0.0

    ink_pixels = img[img < 128]
    bg_pixels = img[img > 200]

    if len(ink_pixels) == 0 or len(bg_pixels) == 0:
        return 0.0

    contrast = float(np.mean(bg_pixels)) - float(np.mean(ink_pixels))
    # Normalize: 200 difference is perfect
    return min(1.0, max(0.0, contrast / 200.0))


def check_baseline_alignment(img: np.ndarray, word_positions: list[dict]) -> float:
    """Compute vertical consistency score for word baseline alignment.

    Args:
        img: Full page image (grayscale uint8).
        word_positions: List of dicts with 'x', 'y', 'width', 'height', 'line' keys.

    Returns:
        Score in [0, 1] where 1.0 means perfectly aligned baselines.
    """
    if not word_positions:
        return 1.0

    # Group by line
    lines = {}
    for pos in word_positions:
        line_num = pos.get("line", 0)
        if line_num not in lines:
            lines[line_num] = []
        lines[line_num].append(pos)

    if not lines:
        return 1.0

    # For each line, check y-position variance
    line_scores = []
    for line_num, positions in lines.items():
        if len(positions) < 2:
            line_scores.append(1.0)
            continue

        # Bottom positions (baseline proxy)
        bottoms = [p["y"] + p.get("height", 0) for p in positions]
        std = float(np.std(bottoms))
        # 0 std = perfect, >10 pixels = poor
        score = max(0.0, 1.0 - std / 10.0)
        line_scores.append(score)

    return float(np.mean(line_scores))


def check_stroke_weight_consistency(word_imgs: list[np.ndarray]) -> float:
    """Compute cross-word ink median spread.

    Returns score in [0, 1] where 1.0 means perfectly consistent stroke weight.
    """
    if len(word_imgs) < 2:
        return 1.0

    medians = []
    for img in word_imgs:
        ink = img[img < 180]
        if len(ink) > 0:
            medians.append(float(np.median(ink)))

    if len(medians) < 2:
        return 1.0

    spread = float(np.std(medians))
    # 0 spread = perfect, >30 = poor
    return max(0.0, 1.0 - spread / 30.0)


def check_word_height_ratio(word_imgs: list[np.ndarray]) -> float:
    """Compute max/min ink height ratio.

    Returns score in [0, 1] where 1.0 means perfectly consistent heights.
    Lower scores indicate more variation.
    """
    if len(word_imgs) < 2:
        return 1.0

    heights = []
    for img in word_imgs:
        ink_rows = np.any(img < 180, axis=1)
        if np.any(ink_rows):
            first = int(np.argmax(ink_rows))
            last = len(ink_rows) - 1 - int(np.argmax(ink_rows[::-1]))
            heights.append(last - first + 1)

    if len(heights) < 2:
        return 1.0

    ratio = max(heights) / max(1, min(heights))
    # Ratio of 1.0 = perfect, > 2.0 = poor
    return max(0.0, 1.0 - (ratio - 1.0) / 1.0)


def check_background_cleanliness(img: np.ndarray) -> float:
    """Compute fraction of non-white non-ink pixels (noise).

    Returns score in [0, 1] where 1.0 means clean background.
    """
    if img.size == 0:
        return 1.0

    # Noise = pixels that are neither ink (<128) nor clean background (>240)
    noise = (img >= 128) & (img <= 240)
    noise_ratio = float(np.mean(noise))

    # 0% noise = perfect, >20% = poor
    return max(0.0, 1.0 - noise_ratio / 0.20)


def overall_quality_score(img: np.ndarray, word_imgs: list[np.ndarray] | None = None, word_positions: list[dict] | None = None) -> dict:
    """Compute composite quality score from all checks.

    Returns dict with individual scores and overall score.
    """
    scores = {
        "gray_boxes": 0.0 if check_gray_boxes(img) else 1.0,
        "ink_contrast": check_ink_contrast(img),
        "background_cleanliness": check_background_cleanliness(img),
    }

    if word_imgs is not None:
        scores["stroke_weight_consistency"] = check_stroke_weight_consistency(word_imgs)
        scores["word_height_ratio"] = check_word_height_ratio(word_imgs)

    if word_positions is not None:
        scores["baseline_alignment"] = check_baseline_alignment(img, word_positions)

    scores["overall"] = float(np.mean(list(scores.values())))
    return scores
