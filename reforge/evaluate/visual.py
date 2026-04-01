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


def _ink_height_extent(img: np.ndarray) -> tuple[int, int, int]:
    """Return (first_ink_row, last_ink_row, ink_height) for a word image."""
    ink_rows = np.any(img < 180, axis=1)
    if not np.any(ink_rows):
        return 0, 0, 0
    first = int(np.argmax(ink_rows))
    last = len(ink_rows) - 1 - int(np.argmax(ink_rows[::-1]))
    return first, last, last - first + 1


def _median_ink_brightness(img: np.ndarray) -> float:
    """Median brightness of ink pixels (< 180). Returns 128.0 if no ink."""
    ink = img[img < 180]
    if len(ink) == 0:
        return 128.0
    return float(np.median(ink))


def _estimate_slant_angle(img: np.ndarray) -> float:
    """Estimate slant angle in degrees via ink centroid regression per row.

    Positive = rightward slant, negative = leftward. Returns 0.0 if
    insufficient data for a reliable estimate.
    """
    ink_mask = img < 180
    rows_with_ink = np.any(ink_mask, axis=1)
    if np.sum(rows_with_ink) < 5:
        return 0.0

    row_indices = np.where(rows_with_ink)[0]
    centroids = []
    for r in row_indices:
        cols = np.where(ink_mask[r])[0]
        if len(cols) > 0:
            centroids.append(float(np.mean(cols)))
        else:
            centroids.append(np.nan)

    centroids = np.array(centroids)
    valid = ~np.isnan(centroids)
    if np.sum(valid) < 5:
        return 0.0

    y = row_indices[valid].astype(float)
    x = centroids[valid]
    # Linear regression: x = slope * y + intercept
    y_mean = np.mean(y)
    x_mean = np.mean(x)
    denom = np.sum((y - y_mean) ** 2)
    if denom == 0:
        return 0.0
    slope = np.sum((y - y_mean) * (x - x_mean)) / denom
    return float(np.degrees(np.arctan(slope)))


def _xheight_ratio(img: np.ndarray) -> float:
    """Ratio of x-height (above baseline) to total ink height.

    Uses a simple baseline estimate: scan from bottom for first row
    with >15% ink density. Returns 0.5 if insufficient data.
    """
    first, last, ink_h = _ink_height_extent(img)
    if ink_h < 5:
        return 0.5

    ink_mask = img < 180
    row_density = np.mean(ink_mask, axis=1)

    # Find baseline: scan up from bottom of ink, find last row with >15% density
    baseline = last
    for r in range(last, first + ink_h // 2, -1):
        if row_density[r] < 0.15:
            baseline = r + 1
            break

    above_baseline = baseline - first
    if ink_h == 0:
        return 0.5
    return above_baseline / ink_h


def compute_style_similarity(
    generated_img: np.ndarray,
    style_reference_imgs: list[np.ndarray],
) -> float:
    """Compare a generated word image against style reference images.

    Compares three features:
    - Stroke weight (median ink brightness)
    - Slant angle (ink centroid regression)
    - X-height ratio (above-baseline height / total ink height)

    Returns 0-1 score where 1.0 means a perfect match.
    """
    if generated_img.size == 0 or not style_reference_imgs:
        return 0.5

    # Generated image features
    gen_brightness = _median_ink_brightness(generated_img)
    gen_slant = _estimate_slant_angle(generated_img)
    gen_xh = _xheight_ratio(generated_img)

    # Style reference features (average across all references)
    ref_brightnesses = [_median_ink_brightness(r) for r in style_reference_imgs]
    ref_slants = [_estimate_slant_angle(r) for r in style_reference_imgs]
    ref_xhs = [_xheight_ratio(r) for r in style_reference_imgs]

    ref_brightness = float(np.mean(ref_brightnesses))
    ref_slant = float(np.mean(ref_slants))
    ref_xh = float(np.mean(ref_xhs))

    # Sub-scores
    brightness_score = max(0.0, 1.0 - abs(gen_brightness - ref_brightness) / 100.0)
    slant_score = max(0.0, 1.0 - abs(gen_slant - ref_slant) / 30.0)
    xh_score = max(0.0, 1.0 - abs(gen_xh - ref_xh) / 0.3)

    return float(np.mean([brightness_score, slant_score, xh_score]))


def check_composition_score(
    img: np.ndarray,
    word_positions: list[dict],
) -> float:
    """Measure composition quality: aspect ratio, margins, line fill consistency.

    Sub-scores:
    - Aspect ratio proximity to 1.0 (0.7-1.3 range is ideal)
    - Margin proportion check
    - Line fill consistency (non-final lines should have similar fill)

    Returns 0-1 score.
    """
    h, w = img.shape[:2]
    if h == 0 or w == 0 or not word_positions:
        return 0.5

    # (a) Aspect ratio: 1.0 is ideal, 0.5 or 2.0 are poor
    ratio = w / h
    if 0.7 <= ratio <= 1.3:
        aspect_score = 1.0 - abs(ratio - 1.0) / 0.3 * 0.2  # mild penalty within range
    else:
        aspect_score = max(0.0, 1.0 - abs(ratio - 1.0) / 1.0)

    # (b) Margin proportion
    # Find content bounds from word positions
    if word_positions:
        min_x = min(p["x"] for p in word_positions)
        max_x = max(p["x"] + p.get("width", 0) for p in word_positions)
        min_y = min(p["y"] for p in word_positions)
        max_y = max(p["y"] + p.get("height", 0) for p in word_positions)

        left_margin = min_x / w if w > 0 else 0
        right_margin = (w - max_x) / w if w > 0 else 0
        top_margin = min_y / h if h > 0 else 0
        bottom_margin = (h - max_y) / h if h > 0 else 0

        # Target: left/right 5-8%, top/bottom 3-5%
        def _margin_score(actual, low, high):
            if low <= actual <= high:
                return 1.0
            dist = min(abs(actual - low), abs(actual - high))
            return max(0.0, 1.0 - dist / 0.05)

        margin_score = np.mean([
            _margin_score(left_margin, 0.05, 0.08),
            _margin_score(right_margin, 0.05, 0.08),
            _margin_score(top_margin, 0.03, 0.05),
            _margin_score(bottom_margin, 0.03, 0.05),
        ])
    else:
        margin_score = 0.5

    # (c) Line fill consistency
    lines = {}
    for p in word_positions:
        line = p.get("line", 0)
        if line not in lines:
            lines[line] = []
        lines[line].append(p)

    if len(lines) > 1:
        # Compute fill ratio per line, excluding last line of each paragraph
        # Identify paragraph-final lines: lines where the next line is a different paragraph
        # or is the last line overall
        para_starts = {p.get("line", 0) for p in word_positions if p.get("is_paragraph_start", False)}
        para_final_lines = set()
        sorted_lines = sorted(lines.keys())
        for i, ln in enumerate(sorted_lines):
            if i + 1 < len(sorted_lines) and sorted_lines[i + 1] in para_starts:
                para_final_lines.add(ln)
        para_final_lines.add(sorted_lines[-1])  # last line overall

        usable_width = w * 0.88  # approximate usable width (minus margins)
        fill_ratios = []
        for ln, positions in lines.items():
            if ln in para_final_lines:
                continue
            total_word_w = sum(p.get("width", 0) for p in positions)
            fill = total_word_w / usable_width if usable_width > 0 else 0
            fill_ratios.append(fill)

        if len(fill_ratios) >= 2:
            fill_score = max(0.0, 1.0 - float(np.std(fill_ratios)) / 0.3)
        else:
            fill_score = 1.0
    else:
        fill_score = 1.0

    return float(np.mean([aspect_score, margin_score, fill_score]))


def compute_height_outlier_ratio(word_imgs: list[np.ndarray]) -> float:
    """Compute worst-case word ink height / median ink height.

    Returns 1.0 for perfectly uniform heights. Higher values indicate
    worse outliers. A value of 1.5 means the tallest word is 50% taller
    than the median.
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

    median_h = float(np.median(heights))
    if median_h == 0:
        return 1.0

    return max(heights) / median_h


def overall_quality_score(
    img: np.ndarray,
    word_imgs: list[np.ndarray] | None = None,
    word_positions: list[dict] | None = None,
    words: list[str] | None = None,
    style_reference_imgs: list[np.ndarray] | None = None,
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
        scores["height_outlier_ratio"] = compute_height_outlier_ratio(word_imgs)

    if word_imgs is not None and style_reference_imgs is not None:
        similarities = [
            compute_style_similarity(w, style_reference_imgs)
            for w in word_imgs
        ]
        scores["style_fidelity"] = float(np.mean(similarities))

    if word_positions is not None:
        scores["baseline_alignment"] = check_baseline_alignment(img, word_positions)
        scores["composition_score"] = check_composition_score(img, word_positions)

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
    # Exclude observation-only metrics from weighted score
    _exclude = ("ocr_min", "blank_word_ratio", "height_outlier_ratio",
                 "style_fidelity", "composition_score")
    component_scores = [v for k, v in scores.items() if k not in _exclude]
    if "ocr_accuracy" in scores:
        # Weight OCR accuracy as 40% of overall, rest shares 60%
        non_ocr = [v for k, v in scores.items()
                   if k not in ("ocr_accuracy",) + _exclude]
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
