"""Word segmentation from a handwritten sentence image.

Uses connected components with morphological bridging to group letters
into words, then extracts word bounding boxes in reading order.

Only thresholding, tight crop, and segmentation happen on the full image.
All other processing (deskew, morph cleanup, etc.) is per-word only.
"""

import cv2
import numpy as np


def _binarize(gray: np.ndarray) -> np.ndarray:
    """Adaptive threshold to binary (ink=255, background=0)."""
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15
    )
    return binary


def _tight_crop(binary: np.ndarray) -> tuple[np.ndarray, int, int]:
    """Crop to bounding box of all ink pixels. Returns (cropped, y_offset, x_offset)."""
    coords = cv2.findNonZero(binary)
    if coords is None:
        return binary, 0, 0
    x, y, w, h = cv2.boundingRect(coords)
    return binary[y : y + h, x : x + w], y, x


def segment_sentence_image(image: np.ndarray) -> list[np.ndarray]:
    """Segment a handwritten sentence image into individual word images.

    Uses morphological dilation to bridge gaps between letters within words,
    then finds connected components as word regions. Returns grayscale word
    crops in reading order (top-to-bottom, left-to-right).

    Args:
        image: Grayscale or BGR uint8 image of a handwritten sentence.

    Returns:
        List of grayscale uint8 word images in reading order.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    binary = _binarize(gray)

    # Use horizontal dilation to bridge gaps between letters within a word.
    # The kernel width determines how large a gap can be bridged.
    # Too small = letters split into separate "words"
    # Too large = adjacent words merge
    h, w = binary.shape
    kernel_w = max(15, w // 30)  # adaptive to image width
    kernel_h = 3
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, kernel_h))
    dilated = cv2.dilate(binary, kernel, iterations=1)

    # Also dilate vertically a bit to merge components of same letter
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 5))
    dilated = cv2.dilate(dilated, kernel_v, iterations=1)

    # Find connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        dilated, connectivity=8
    )

    # Collect bounding boxes, filtering noise
    min_area = max(200, h * w * 0.001)  # at least 0.1% of image area or 200px
    min_dim = max(20, min(h, w) // 20)

    boxes = []
    for i in range(1, num_labels):  # skip background (0)
        x, y, bw, bh, area = stats[i]
        if area < min_area:
            continue
        if bw < min_dim or bh < min_dim:
            continue
        boxes.append((x, y, bw, bh, centroids[i][1], centroids[i][0]))

    if not boxes:
        # Fallback: return the whole image
        coords = cv2.findNonZero(binary)
        if coords is not None:
            bx, by, bw, bh = cv2.boundingRect(coords)
            return [gray[by : by + bh, bx : bx + bw]]
        return [gray]

    # Sort in reading order: primarily by row (y centroid), then by column (x)
    # Group into lines first using y-centroid clustering
    boxes.sort(key=lambda b: b[4])  # sort by y centroid

    lines = []
    current_line = [boxes[0]]
    for box in boxes[1:]:
        prev_cy = current_line[-1][4]
        curr_cy = box[4]
        # Same line if y centroids are within half the typical word height
        avg_h = np.mean([b[3] for b in current_line])
        if abs(curr_cy - prev_cy) < avg_h * 0.5:
            current_line.append(box)
        else:
            lines.append(current_line)
            current_line = [box]
    lines.append(current_line)

    # Sort words within each line by x position
    words = []
    for line in lines:
        line.sort(key=lambda b: b[0])  # sort by x
        for x, y, bw, bh, cy, cx in line:
            # Extract from original grayscale using the bounding box
            # but re-crop tightly from the binary to remove padding
            region_binary = binary[y : y + bh, x : x + bw]
            region_gray = gray[y : y + bh, x : x + bw]
            coords = cv2.findNonZero(region_binary)
            if coords is None:
                continue
            rx, ry, rw, rh = cv2.boundingRect(coords)
            word_crop = region_gray[ry : ry + rh, rx : rx + rw]
            if word_crop.size > 0:
                words.append(word_crop)

    return words
