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
    """Compute fraction of non-white non-ink pixels (noise) in background regions.

    Excludes gray pixels adjacent to ink (anti-aliasing) since those are
    expected from diffusion output, not artifacts. Only counts gray pixels
    that are isolated in background areas.

    Returns score in [0, 1] where 1.0 means clean background.
    """
    if img.size == 0:
        return 1.0

    # Noise = pixels that are neither ink (<128) nor clean background (>240)
    noise = (img >= 128) & (img <= 240)

    # Exclude gray pixels adjacent to ink (within 2px) -- these are anti-aliasing
    ink_mask = img < 128
    if np.any(ink_mask):
        ink_uint8 = ink_mask.astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        near_ink = cv2.dilate(ink_uint8, kernel) > 0
        noise = noise & ~near_ink

    noise_ratio = float(np.mean(noise))

    # 0% noise = perfect, >20% = poor
    return max(0.0, 1.0 - noise_ratio / 0.20)


def overall_quality_score(
    img: np.ndarray,
    word_imgs: list[np.ndarray] | None = None,
    word_positions: list[dict] | None = None,
    words: list[str] | None = None,
) -> dict:
    """Compute composite quality score from all checks.

    When words and word_imgs are provided, OCR accuracy is included as the
    dominant factor. Unreadable words (OCR < 0.5) or blank words (< expected
    ink) tank the overall score.

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

    # OCR accuracy: dominant factor when available
    if word_imgs is not None and words is not None:
        ocr_scores = _compute_ocr_scores(word_imgs, words)
        if ocr_scores is not None:
            scores["ocr_accuracy"] = ocr_scores["mean"]
            scores["ocr_min"] = ocr_scores["min"]

            # Blank word detection: words with < 50% of expected ink pixels
            blank_ratio = _blank_word_ratio(word_imgs, words)
            scores["blank_word_ratio"] = 1.0 - blank_ratio

    # Compute overall: OCR-weighted if available
    component_scores = [v for k, v in scores.items()
                        if k not in ("ocr_min", "blank_word_ratio")]
    if "ocr_accuracy" in scores:
        # Weight OCR accuracy as 40% of overall, rest shares 60%
        non_ocr = [v for k, v in scores.items()
                   if k not in ("ocr_accuracy", "ocr_min", "blank_word_ratio")]
        non_ocr_mean = float(np.mean(non_ocr)) if non_ocr else 0.5
        overall = 0.4 * scores["ocr_accuracy"] + 0.6 * non_ocr_mean

        # Tank overall if any word is unreadable or blank
        if scores.get("ocr_min", 1.0) < 0.5:
            overall = min(overall, 0.45)
        if scores.get("blank_word_ratio", 1.0) < 0.8:
            overall = min(overall, 0.45)
    else:
        overall = float(np.mean(component_scores))

    scores["overall"] = overall
    return scores


def _compute_ocr_scores(
    word_imgs: list[np.ndarray], words: list[str],
) -> dict | None:
    """Compute per-word OCR accuracy. Returns None if OCR is unavailable."""
    try:
        from reforge.evaluate.ocr import ocr_accuracy
    except ImportError:
        return None

    accuracies = []
    for img, word in zip(word_imgs, words):
        if img is None or word is None:
            continue
        acc = ocr_accuracy(img, word)
        accuracies.append(acc)

    if not accuracies:
        return None

    return {
        "mean": float(np.mean(accuracies)),
        "min": float(np.min(accuracies)),
        "per_word": accuracies,
    }


def _blank_word_ratio(
    word_imgs: list[np.ndarray], words: list[str],
) -> float:
    """Fraction of words with fewer ink pixels than expected.

    A word is considered blank if its ink pixel count is less than
    50% of (word_length * 50) pixels (rough expected minimum).
    """
    if not word_imgs or not words:
        return 0.0

    blank_count = 0
    total = 0
    for img, word in zip(word_imgs, words):
        if img is None or word is None:
            continue
        total += 1
        expected_ink = len(word) * 50  # rough minimum
        actual_ink = int(np.sum(img < 128))
        if actual_ink < expected_ink * 0.5:
            blank_count += 1

    if total == 0:
        return 0.0
    return blank_count / total
