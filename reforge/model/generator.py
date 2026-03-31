"""Word generation: DDIM sampling with CFG, best-of-N, chunking, stitching, postprocessing.

Implements all five gray-box defense layers in postprocessing.
"""

import numpy as np
import torch
import torch.nn.functional as F

from reforge.config import (
    BACKGROUND_PERCENTILE,
    BODY_ZONE_BOTTOM,
    BODY_ZONE_INK_THRESHOLD,
    BODY_ZONE_TOP,
    CC_BOUNDARY_BONUS,
    CLUSTER_GAP_PX,
    COMPOSITOR_INK_THRESHOLD,
    CONSONANT_PENALTY,
    CV_BOUNDARY_BONUS,
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
    DEFAULT_DDIM_STEPS,
    DEFAULT_GUIDANCE_SCALE,
    DEFAULT_NUM_CANDIDATES,
    HALO_DILATE_RADIUS,
    HALO_GRAY_THRESHOLD,
    INK_THRESHOLD_RATIO,
    MAX_CANVAS_WIDTH,
    MAX_WORD_LENGTH,
    MIN_CHUNK_CHARS,
    STITCH_OVERLAP_PX,
    VAE_SCALE_FACTOR,
    WIDTH_MULTIPLE,
)

VOWELS = set("aeiouAEIOU")
CONSONANTS = set("bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ")


# --- Syllable splitting ---

def score_split(word: str, pos: int) -> float:
    """Score a split position in a word.

    Considers:
    - Balance: prefer equal-length chunks
    - Consonant penalty: -3 if >= 3 trailing consonants in left chunk
    - Boundary bonus: +2 for CC boundary, +1 for CV boundary
    """
    left, right = word[:pos], word[pos:]
    if len(left) < MIN_CHUNK_CHARS or len(right) < MIN_CHUNK_CHARS:
        return -999

    # Balance score: prefer equal halves
    balance = 1.0 - abs(len(left) - len(right)) / len(word)

    # Consonant cluster penalty
    trailing_consonants = 0
    for c in reversed(left):
        if c in CONSONANTS:
            trailing_consonants += 1
        else:
            break
    consonant_score = CONSONANT_PENALTY if trailing_consonants >= 3 else 0

    # Boundary bonus
    boundary_score = 0
    if pos > 0 and pos < len(word):
        left_char = word[pos - 1]
        right_char = word[pos]
        if left_char in CONSONANTS and right_char in CONSONANTS:
            boundary_score = CC_BOUNDARY_BONUS
        elif left_char in CONSONANTS and right_char in VOWELS:
            boundary_score = CV_BOUNDARY_BONUS

    return balance * 10 + consonant_score + boundary_score


def split_long_word(word: str) -> list[str]:
    """Split a long word into chunks using score-based syllable splitting.

    Each chunk is guaranteed to be >= MIN_CHUNK_CHARS characters.
    """
    if len(word) <= MAX_WORD_LENGTH:
        return [word]

    # Find best split point
    best_pos = None
    best_score = -999
    for pos in range(MIN_CHUNK_CHARS, len(word) - MIN_CHUNK_CHARS + 1):
        s = score_split(word, pos)
        if s > best_score:
            best_score = s
            best_pos = pos

    if best_pos is None:
        # Cannot split while maintaining minimum chunk size
        return [word]

    left = word[:best_pos]
    right = word[best_pos:]

    # Recursively split if chunks are still too long
    chunks = []
    if len(left) > MAX_WORD_LENGTH:
        chunks.extend(split_long_word(left))
    else:
        chunks.append(left)

    if len(right) > MAX_WORD_LENGTH:
        chunks.extend(split_long_word(right))
    else:
        chunks.append(right)

    return chunks


# --- Adaptive canvas width ---

def compute_canvas_width(word_len: int) -> int:
    """Compute canvas width based on word length, up to MAX_CANVAS_WIDTH."""
    if word_len <= 8:
        width = DEFAULT_CANVAS_WIDTH
    else:
        # Scale linearly from 256 to 320 for 8-10 char words
        ratio = min((word_len - 8) / 2, 1.0)
        width = int(DEFAULT_CANVAS_WIDTH + ratio * (MAX_CANVAS_WIDTH - DEFAULT_CANVAS_WIDTH))
    # Round up to multiple of WIDTH_MULTIPLE
    width = ((width + WIDTH_MULTIPLE - 1) // WIDTH_MULTIPLE) * WIDTH_MULTIPLE
    return min(width, MAX_CANVAS_WIDTH)


# --- Postprocessing: 5 gray-box defense layers ---

def adaptive_background_estimate(img: np.ndarray) -> float:
    """Layer 1: 90th-percentile pixel value as background estimate."""
    return float(np.percentile(img, BACKGROUND_PERCENTILE))


def apply_ink_threshold(img: np.ndarray, bg_estimate: float) -> np.ndarray:
    """Create ink mask using adaptive threshold at 70% of background estimate."""
    threshold = bg_estimate * INK_THRESHOLD_RATIO
    ink_mask = img < threshold
    return ink_mask


def body_zone_noise_removal(img: np.ndarray, ink_mask: np.ndarray) -> np.ndarray:
    """Layer 2: Blank columns without sufficient body-zone ink."""
    h, w = img.shape[:2]
    body_top = int(h * BODY_ZONE_TOP)
    body_bottom = int(h * BODY_ZONE_BOTTOM)
    body_zone = ink_mask[body_top:body_bottom, :]

    col_ink_ratio = np.mean(body_zone, axis=0)
    valid_cols = col_ink_ratio >= BODY_ZONE_INK_THRESHOLD

    result = img.copy()
    for c in range(w):
        if not valid_cols[c]:
            result[:, c] = 255
    return result


def isolated_cluster_filter(img: np.ndarray, ink_mask: np.ndarray) -> np.ndarray:
    """Layer 3: Discard body-column clusters separated by large gaps from main cluster."""
    h, w = img.shape[:2]
    body_top = int(h * BODY_ZONE_TOP)
    body_bottom = int(h * BODY_ZONE_BOTTOM)
    body_zone = ink_mask[body_top:body_bottom, :]

    col_has_ink = np.any(body_zone, axis=0)

    # Find connected runs of ink columns
    clusters = []
    start = None
    for c in range(w):
        if col_has_ink[c] and start is None:
            start = c
        elif not col_has_ink[c] and start is not None:
            clusters.append((start, c))
            start = None
    if start is not None:
        clusters.append((start, w))

    if len(clusters) <= 1:
        return img

    # Find main cluster (widest)
    main_idx = max(range(len(clusters)), key=lambda i: clusters[i][1] - clusters[i][0])
    main_start, main_end = clusters[main_idx]

    result = img.copy()
    for i, (cs, ce) in enumerate(clusters):
        if i == main_idx:
            continue
        # Check gap distance to main cluster
        gap = min(abs(cs - main_end), abs(main_start - ce))
        if gap >= CLUSTER_GAP_PX:
            result[:, cs:ce] = 255

    return result


def postprocess_word(img: np.ndarray) -> np.ndarray:
    """Apply all 5 gray-box defense layers to a generated word image.

    Args:
        img: Grayscale uint8 word image from VAE decode.

    Returns:
        Cleaned grayscale uint8 image.
    """
    # Layer 1: Adaptive background estimation
    bg_estimate = adaptive_background_estimate(img)
    ink_mask = apply_ink_threshold(img, bg_estimate)

    # Layer 2: Body-zone noise removal
    img = body_zone_noise_removal(img, ink_mask)

    # Recompute ink mask after layer 2
    ink_mask = apply_ink_threshold(img, bg_estimate)

    # Layer 3: Isolated cluster filtering
    img = isolated_cluster_filter(img, ink_mask)

    # Layer 4 (compositor ink-only) is applied during composition in render.py

    # Layer 5 (post-upscale halo cleanup) is applied after upscaling in render.py

    return img


def halo_cleanup(img: np.ndarray) -> np.ndarray:
    """Layer 5: Post-upscale halo cleanup.

    Dilate strong-ink mask, blank gray pixels not near dilated ink.
    """
    import cv2

    # Find strong ink pixels
    strong_ink = img < 128
    strong_ink_uint8 = strong_ink.astype(np.uint8) * 255

    # Dilate to create neighborhood mask
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (HALO_DILATE_RADIUS * 2 + 1, HALO_DILATE_RADIUS * 2 + 1)
    )
    dilated = cv2.dilate(strong_ink_uint8, kernel)
    near_ink = dilated > 0

    # Blank gray pixels not near ink
    result = img.copy()
    gray_pixels = (img > 128) & (img < HALO_GRAY_THRESHOLD)
    cleanup_mask = gray_pixels & ~near_ink
    result[cleanup_mask] = 255

    return result


# --- DDIM Sampling ---

def ddim_sample(
    unet,
    vae,
    text_context: dict,
    style_features: torch.Tensor,
    canvas_width: int = DEFAULT_CANVAS_WIDTH,
    num_steps: int = DEFAULT_DDIM_STEPS,
    guidance_scale: float = DEFAULT_GUIDANCE_SCALE,
    device: str = "cuda",
) -> np.ndarray:
    """Run DDIM sampling to generate a single word image.

    Args:
        unet: DiffusionPen UNet model.
        vae: SD 1.5 VAE decoder.
        text_context: Canine-C tokenizer output dict.
        style_features: (5, 1280) raw style features.
        canvas_width: Width of generation canvas.
        num_steps: Number of DDIM steps.
        guidance_scale: CFG scale (1.0 disables CFG).
        device: Torch device.

    Returns:
        Grayscale uint8 numpy array.
    """
    from diffusers import DDIMScheduler

    scheduler = DDIMScheduler(
        beta_start=0.00085,
        beta_end=0.012,
        beta_schedule="scaled_linear",
        clip_sample=False,
        set_alpha_cumprod_to_one=False,
    )
    scheduler.set_timesteps(num_steps, device=device)

    latent_h = DEFAULT_CANVAS_HEIGHT // 8
    latent_w = canvas_width // 8

    # Start from noise
    latents = torch.randn(1, 4, latent_h, latent_w, device=device)

    # Move inputs to device
    text_ctx = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in text_context.items()}
    style_feat = style_features.to(device)

    # Prepare unconditional inputs for CFG
    use_cfg = guidance_scale != 1.0
    if use_cfg:
        from transformers import CanineTokenizer
        tokenizer = CanineTokenizer.from_pretrained("google/canine-c")
        uncond_ctx = tokenizer(" ", return_tensors="pt", padding="max_length", max_length=text_ctx["input_ids"].shape[1])
        uncond_ctx = {k: v.to(device) if isinstance(v, torch.Tensor) else v for k, v in uncond_ctx.items()}
        zero_style = torch.zeros_like(style_feat)

    for t in scheduler.timesteps:
        t_batch = t.unsqueeze(0) if t.dim() == 0 else t

        # Conditional prediction
        # UNet forward: (x, timesteps, context, y, style_extractor)
        # When style_extractor is provided, UNet uses it as style features
        # and does reshape(b,5,-1) + mean + style_lin internally
        noise_pred_cond = unet(
            latents, t_batch, context=text_ctx, y=style_feat,
            style_extractor=style_feat,
        )

        if use_cfg:
            # Unconditional prediction
            noise_pred_uncond = unet(
                latents, t_batch, context=uncond_ctx, y=zero_style,
                style_extractor=zero_style,
            )
            noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_cond - noise_pred_uncond)
        else:
            noise_pred = noise_pred_cond

        latents = scheduler.step(noise_pred, t, latents).prev_sample

    # VAE decode
    with torch.no_grad():
        decoded = vae.decode(latents / VAE_SCALE_FACTOR).sample
        # (x/2 + 0.5).clamp(0,1) -> [0,1] RGB
        decoded = (decoded / 2 + 0.5).clamp(0, 1)

    # Convert to grayscale uint8
    img = decoded[0].mean(dim=0).cpu().numpy()  # average RGB channels
    img = (img * 255).astype(np.uint8)

    return img


def generate_word(
    word: str,
    unet,
    vae,
    tokenizer,
    style_features: torch.Tensor,
    num_steps: int = DEFAULT_DDIM_STEPS,
    guidance_scale: float = DEFAULT_GUIDANCE_SCALE,
    num_candidates: int = DEFAULT_NUM_CANDIDATES,
    device: str = "cuda",
) -> np.ndarray:
    """Generate a single word image with best-of-N candidate selection.

    Long words (>10 chars) are split, generated as chunks, and stitched.
    """
    from reforge.quality.score import quality_score

    chunks = split_long_word(word)

    if len(chunks) == 1:
        # Single word generation with best-of-N
        canvas_width = compute_canvas_width(len(word))
        text_ctx = tokenizer(word, return_tensors="pt", padding="max_length", max_length=16)

        best_img = None
        best_score = -1

        for _ in range(num_candidates):
            img = ddim_sample(
                unet, vae, text_ctx, style_features,
                canvas_width=canvas_width,
                num_steps=num_steps,
                guidance_scale=guidance_scale,
                device=device,
            )
            img = postprocess_word(img)
            score = quality_score(img)
            if score > best_score:
                best_score = score
                best_img = img

        return best_img

    # Multi-chunk: generate each chunk, normalize heights, baseline-align, stitch
    chunk_images = []
    for chunk in chunks:
        canvas_width = compute_canvas_width(len(chunk))
        text_ctx = tokenizer(chunk, return_tensors="pt", padding="max_length", max_length=16)

        best_img = None
        best_score = -1
        for _ in range(num_candidates):
            img = ddim_sample(
                unet, vae, text_ctx, style_features,
                canvas_width=canvas_width,
                num_steps=num_steps,
                guidance_scale=guidance_scale,
                device=device,
            )
            img = postprocess_word(img)
            score = quality_score(img)
            if score > best_score:
                best_score = score
                best_img = img

        chunk_images.append(best_img)

    return stitch_chunks(chunk_images)


def stitch_chunks(chunks: list[np.ndarray]) -> np.ndarray:
    """Stitch word chunks with baseline alignment and overlap blending.

    - Normalize chunk heights to median
    - Align at bottom (baseline)
    - Overlap blending at stitch boundaries
    """
    import cv2

    if len(chunks) == 1:
        return chunks[0]

    # Normalize heights to median
    heights = [c.shape[0] for c in chunks]
    median_h = int(np.median(heights))

    normalized = []
    for chunk in chunks:
        if chunk.shape[0] != median_h:
            scale = median_h / chunk.shape[0]
            new_w = max(1, int(chunk.shape[1] * scale))
            chunk = cv2.resize(chunk, (new_w, median_h), interpolation=cv2.INTER_AREA)
        normalized.append(chunk)

    # Baseline-aligned stitching (align at bottom, pad at top)
    max_h = max(c.shape[0] for c in normalized)
    padded = []
    for chunk in normalized:
        if chunk.shape[0] < max_h:
            pad = np.full((max_h - chunk.shape[0], chunk.shape[1]), 255, dtype=np.uint8)
            chunk = np.vstack([pad, chunk])  # pad at top, align bottom
        padded.append(chunk)

    # Stitch with overlap blending
    total_width = sum(c.shape[1] for c in padded) - STITCH_OVERLAP_PX * (len(padded) - 1)
    result = np.full((max_h, total_width), 255, dtype=np.uint8)

    x = 0
    for i, chunk in enumerate(padded):
        if i == 0:
            result[:, x : x + chunk.shape[1]] = chunk
            x += chunk.shape[1] - STITCH_OVERLAP_PX
        else:
            # Blend overlap region
            overlap_start = x
            overlap_end = x + STITCH_OVERLAP_PX

            for ox in range(STITCH_OVERLAP_PX):
                alpha = ox / STITCH_OVERLAP_PX  # 0->1 from left to right
                col_idx = overlap_start + ox
                if col_idx < result.shape[1]:
                    prev_col = result[:, col_idx].astype(np.float32)
                    new_col = chunk[:, ox].astype(np.float32)
                    result[:, col_idx] = ((1 - alpha) * prev_col + alpha * new_col).astype(np.uint8)

            # Copy rest of chunk
            rest_start = STITCH_OVERLAP_PX
            dest_start = overlap_end
            rest_width = chunk.shape[1] - rest_start
            if dest_start + rest_width <= result.shape[1]:
                result[:, dest_start : dest_start + rest_width] = chunk[:, rest_start:]

            x = dest_start + rest_width - STITCH_OVERLAP_PX

    return result
