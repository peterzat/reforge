"""Medium-tier regression test for contraction chunk sizing.

Spec 2026-04-19 criterion 1: after `_match_chunk_to_reference` runs, the
right chunk of a contraction (e.g. `'t` in `can't`) is within a tight
tolerance of the left chunk's stroke width, ink intensity, and ink height.
Before the fix, `'t` measured stroke 3.0-3.4 and x-height 4-6 against
`can` stroke 6.1-6.4 and x-height 52-57 — the defect visible in
`docs/output-history/20260419-161539.png`.

This test runs the real inference path for a direct comparison. It is
intentionally strict; the match helper is bounded (CHUNK_MAX_UPSCALE=1.8,
CHUNK_MAX_DILATE_ITER=4), so pathological inputs can still fall outside
the gate — those should be documented and the helper bounds revisited.
"""

import numpy as np
import pytest
import torch

pytestmark = [
    pytest.mark.medium,
    pytest.mark.gpu,
    pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required"),
]

WORDS = ("can't", "don't", "it's", "they'd")
SEEDS = (42, 137, 2718)

MIN_STROKE_RATIO = 0.85   # right / left stroke width
MAX_INK_DELTA = 0.20      # |right - left| / max(left, 1) for median ink intensity
MAX_HEIGHT_DELTA = 0.15   # |right - left| / max(left, 1) for ink height


def _generate_chunk(text, unet, vae, tokenizer, style_features, uncond_context, device):
    from reforge.config import PRESET_FAST
    from reforge.model.generator import (
        compute_canvas_width, ddim_sample, pad_clipped_descender,
        postprocess_word,
    )
    canvas_width = compute_canvas_width(len(text))
    ctx = tokenizer(text, return_tensors="pt", padding="max_length", max_length=16)
    img = ddim_sample(
        unet, vae, ctx, style_features,
        uncond_context=uncond_context,
        canvas_width=canvas_width,
        num_steps=PRESET_FAST["steps"],
        guidance_scale=PRESET_FAST["guidance_scale"],
        device=device,
    )
    img = postprocess_word(img)
    img = pad_clipped_descender(img)
    return img


def test_right_chunk_matches_left(
    unet, vae, tokenizer, style_features, uncond_context, device,
):
    from reforge.model.generator import (
        _match_chunk_to_reference, split_contraction,
    )
    from reforge.quality.harmonize import (
        compute_ink_median, compute_mean_stroke_width,
    )
    from reforge.quality.ink_metrics import compute_ink_height

    failures: list[str] = []
    for word in WORDS:
        left_text, right_text = split_contraction(word)
        for seed in SEEDS:
            torch.manual_seed(seed)
            np.random.seed(seed)
            left_img = _generate_chunk(
                left_text, unet, vae, tokenizer, style_features,
                uncond_context, device,
            )
            right_raw = _generate_chunk(
                right_text, unet, vae, tokenizer, style_features,
                uncond_context, device,
            )
            right_img = _match_chunk_to_reference(right_raw, left_img)

            l_stroke = compute_mean_stroke_width(left_img)
            r_stroke = compute_mean_stroke_width(right_img)
            l_ink = compute_ink_median(left_img)
            r_ink = compute_ink_median(right_img)
            l_h = compute_ink_height(left_img)
            r_h = compute_ink_height(right_img)

            if l_stroke > 0 and r_stroke < MIN_STROKE_RATIO * l_stroke:
                failures.append(
                    f"{word} seed={seed}: right stroke {r_stroke:.2f} < "
                    f"{MIN_STROKE_RATIO} * left {l_stroke:.2f}"
                )
            if l_ink > 0:
                ink_delta = abs(r_ink - l_ink) / max(l_ink, 1.0)
                if ink_delta > MAX_INK_DELTA:
                    failures.append(
                        f"{word} seed={seed}: right ink {r_ink:.1f} vs left "
                        f"{l_ink:.1f} delta {ink_delta:.2%} > {MAX_INK_DELTA:.0%}"
                    )
            if l_h > 0:
                height_delta = abs(r_h - l_h) / max(l_h, 1)
                if height_delta > MAX_HEIGHT_DELTA:
                    failures.append(
                        f"{word} seed={seed}: right ink_height {r_h} vs left "
                        f"{l_h} delta {height_delta:.2%} > {MAX_HEIGHT_DELTA:.0%}"
                    )

    assert not failures, "chunk sizing mismatches:\n  " + "\n  ".join(failures)
