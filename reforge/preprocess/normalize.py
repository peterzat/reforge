"""Per-word normalization: deskew, contrast normalization, tensor conversion.

These operations happen AFTER segmentation, on individual word crops only.
Never apply deskew or morphological cleanup to the full sentence image.
"""

import cv2
import numpy as np
import torch

from reforge.config import STYLE_TENSOR_SHAPE


def deskew_word(gray: np.ndarray) -> np.ndarray:
    """Deskew a single word image using minimum area rectangle angle.

    Only operates on individual word crops, never on full sentence images.
    """
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15
    )
    coords = cv2.findNonZero(binary)
    if coords is None or len(coords) < 10:
        return gray

    rect = cv2.minAreaRect(coords)
    angle = rect[1][0]  # width
    rect_angle = rect[2]

    # Correct angle interpretation
    if rect[1][0] < rect[1][1]:
        rect_angle = rect_angle + 90

    # Only correct small angles (< 30 degrees)
    if abs(rect_angle) > 30:
        return gray

    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    # Use white (255) as border fill to avoid dark borders
    M = cv2.getRotationMatrix2D(center, rect_angle, 1.0)
    rotated = cv2.warpAffine(
        gray, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=255
    )

    # Tight crop after rotation
    binary_rot = cv2.adaptiveThreshold(
        rotated, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15
    )
    coords_rot = cv2.findNonZero(binary_rot)
    if coords_rot is not None:
        x, y, rw, rh = cv2.boundingRect(coords_rot)
        rotated = rotated[y : y + rh, x : x + rw]

    return rotated


def normalize_contrast(gray: np.ndarray) -> np.ndarray:
    """Normalize contrast of a word image using CLAHE."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    return clahe.apply(gray)


def word_to_tensor(gray: np.ndarray) -> torch.Tensor:
    """Convert a grayscale word image to a style tensor of shape (1, 3, 64, 256).

    Uses DiffusionPen normalization: (pixel/255 - 0.5) / 0.5
    NOT ImageNet normalization.
    """
    target_h, target_w = STYLE_TENSOR_SHAPE[2], STYLE_TENSOR_SHAPE[3]

    # Resize preserving aspect ratio, pad to target size
    h, w = gray.shape[:2]
    scale = min(target_h / h, target_w / w)
    new_h, new_w = int(h * scale), int(w * scale)
    resized = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # Pad to target size with white (255)
    canvas = np.full((target_h, target_w), 255, dtype=np.uint8)
    y_off = (target_h - new_h) // 2
    x_off = (target_w - new_w) // 2
    canvas[y_off : y_off + new_h, x_off : x_off + new_w] = resized

    # Convert to 3-channel
    rgb = np.stack([canvas, canvas, canvas], axis=0).astype(np.float32)

    # DiffusionPen normalization: (pixel/255 - 0.5) / 0.5 = pixel/127.5 - 1
    tensor = torch.from_numpy(rgb) / 127.5 - 1.0

    return tensor.unsqueeze(0)  # (1, 3, 64, 256)


def preprocess_words(word_images: list[np.ndarray]) -> list[torch.Tensor]:
    """Full preprocessing pipeline for segmented word images.

    Applies per-word deskew and contrast normalization, then converts to tensors.
    """
    tensors = []
    for img in word_images:
        deskewed = deskew_word(img)
        normalized = normalize_contrast(deskewed)
        tensor = word_to_tensor(normalized)
        tensors.append(tensor)
    return tensors
