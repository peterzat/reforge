"""Medium-tier regression test for contraction chunk sizing.

Spec 2026-04-19 criterion 1: after `_match_chunk_to_reference` runs, the
right chunk of a contraction (e.g. `'t` in `can't`) is within a tight
tolerance of the left chunk's stroke width, ink intensity, and ink height.
Before the fix, `'t` measured stroke 3.0-3.4 and x-height 4-6 against
`can` stroke 6.1-6.4 and x-height 52-57 — the defect visible in
`docs/output-history/20260419-161539.png`.

This test runs the real inference path for a direct comparison. The
match helper is bounded (CHUNK_MAX_UPSCALE=1.8, CHUNK_MAX_DILATE_ITER=6),
so inputs near the gate can land on either side depending on CUDA state
from prior test tiers. The stroke-ratio threshold constant below
documents the 0.85 to 0.83 widening under spec 2026-04-20 criterion 8;
values below 0.83 require a fresh human review before moving.
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

# Spec 2026-04-20 criterion 8: widened 0.85 -> 0.83 to tolerate the measured
# run-to-run variance at the boundary of CHUNK_MAX_DILATE_ITER. Standalone
# invocations (pytest tests/medium/test_contraction_sizing.py alone) stay at
# ~0.85+ on can't seed=2718; the make test-full ordering (root conftest pulls
# quick + medium into any full invocation, so tests/full/ warms CUDA state
# first) observes ~0.844, a residual shift that option (b) fixture hardening
# (deterministic cudnn, manual_seed_all, empty_cache + synchronize inside
# the test) did not eliminate. 0.83 is the floor per spec without a fresh
# human review; widening further requires one.
MIN_STROKE_RATIO = 0.83   # right / left stroke width
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

    # Isolate CUDA state from prior test tiers. reforge.pipeline sets
    # cudnn.benchmark=True at import, so when tests/full/ runs first in the
    # make test-full DAG (root conftest pulls quick+medium into any full
    # invocation), kernel-selection state and memory allocator layout both
    # differ from the standalone case. Clamp cudnn to deterministic, clear
    # the CUDA allocator, and let the stroke-ratio gate at 0.83 tolerate
    # the residual float variance at the boundary of CHUNK_MAX_DILATE_ITER.
    saved_benchmark = torch.backends.cudnn.benchmark
    saved_deterministic = torch.backends.cudnn.deterministic
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

    failures: list[str] = []
    try:
        for word in WORDS:
            left_text, right_text = split_contraction(word)
            for seed in SEEDS:
                torch.manual_seed(seed)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(seed)
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
    finally:
        torch.backends.cudnn.benchmark = saved_benchmark
        torch.backends.cudnn.deterministic = saved_deterministic

    assert not failures, "chunk sizing mismatches:\n  " + "\n  ".join(failures)
