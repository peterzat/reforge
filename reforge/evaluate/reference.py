"""Reference image comparison using Structural Similarity (SSIM).

SSIM computes luminance, contrast, and structure similarity between two
grayscale images. This catches visual degradation (letter distortion,
over-normalization) that per-metric regression tests miss.
"""

import cv2
import numpy as np


def compute_ssim(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """Compute SSIM between two grayscale images.

    Images are resized to match if dimensions differ. Returns a float
    in [-1, 1] where 1.0 means identical images.
    """
    if img_a.size == 0 or img_b.size == 0:
        return 0.0

    # Ensure 2D grayscale
    if img_a.ndim == 3:
        img_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
    if img_b.ndim == 3:
        img_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)

    # Resize to match dimensions (use the larger image's size)
    if img_a.shape != img_b.shape:
        h = max(img_a.shape[0], img_b.shape[0])
        w = max(img_a.shape[1], img_b.shape[1])
        img_a = cv2.resize(img_a, (w, h), interpolation=cv2.INTER_AREA)
        img_b = cv2.resize(img_b, (w, h), interpolation=cv2.INTER_AREA)

    # Convert to float64 for precision
    a = img_a.astype(np.float64)
    b = img_b.astype(np.float64)

    # SSIM constants (for 8-bit images, L=255)
    L = 255.0
    k1, k2 = 0.01, 0.03
    c1 = (k1 * L) ** 2
    c2 = (k2 * L) ** 2

    # Gaussian-windowed statistics (11x11 window, sigma=1.5)
    ksize = (11, 11)
    sigma = 1.5
    mu_a = cv2.GaussianBlur(a, ksize, sigma)
    mu_b = cv2.GaussianBlur(b, ksize, sigma)

    mu_a_sq = mu_a * mu_a
    mu_b_sq = mu_b * mu_b
    mu_ab = mu_a * mu_b

    sigma_a_sq = cv2.GaussianBlur(a * a, ksize, sigma) - mu_a_sq
    sigma_b_sq = cv2.GaussianBlur(b * b, ksize, sigma) - mu_b_sq
    sigma_ab = cv2.GaussianBlur(a * b, ksize, sigma) - mu_ab

    # SSIM map
    numerator = (2 * mu_ab + c1) * (2 * sigma_ab + c2)
    denominator = (mu_a_sq + mu_b_sq + c1) * (sigma_a_sq + sigma_b_sq + c2)

    ssim_map = numerator / denominator
    return float(np.mean(ssim_map))
