"""Parameter optimality tests: verify generation presets match experimental optima.

Sweeps generation parameters (candidates, DDIM steps, guidance scale) and
checks that preset values sit near the measured quality peak or diminishing
returns knee. Catches parameter drift when code changes shift the quality
curve.

Severity (quality delta from sweep best):
  NOTE   <2% quality preset, <5% fast/draft  -- near-optimal
  WARN   2-5% quality, 5-10% fast/draft      -- suboptimal but functional
  BLOCK  >5% quality, >10% fast/draft        -- likely regression, needs fix

Runtime: ~60-90s (models shared via session-scoped conftest fixtures).
"""

import time
import warnings

import numpy as np
import pytest
import torch

from reforge.config import (
    PRESET_DRAFT,
    PRESET_FAST,
    PRESET_QUALITY,
)

pytestmark = [pytest.mark.medium, pytest.mark.gpu]

SKIP_REASON = "Requires CUDA GPU"

# Fixed test words across all sweeps for comparability.
# Same words as the regression test.
SWEEP_WORDS = ["Quick", "brown", "foxes", "jump", "high"]


def _sweep(words, unet, vae, tokenizer, style_features, uncond_context,
           device, param_name, values, include_ocr=False, **fixed):
    """Sweep one parameter, return {value: mean_quality} and {value: mean_time_s}.

    Args:
        include_ocr: Blend OCR accuracy into the quality metric (50/50).
            Use for sweeps where readability varies across parameter values
            (e.g. guidance_scale), since quality_score alone measures image
            properties but not readability.
    """
    from reforge.model.generator import generate_word
    from reforge.quality.score import quality_score

    ocr_fn = None
    if include_ocr:
        from reforge.evaluate.ocr import ocr_accuracy
        ocr_fn = ocr_accuracy

    qualities = {}
    timings = {}

    # Save RNG state so sweeps are transparent to subsequent tests.
    # Without this, torch.manual_seed calls inside the sweep shift the
    # global RNG, changing the random sequence for any generation that
    # runs after the sweep in the same pytest session.
    rng_state = torch.random.get_rng_state()
    cuda_rng_state = torch.cuda.get_rng_state() if torch.cuda.is_available() else None

    for val in values:
        kwargs = dict(fixed)
        kwargs[param_name] = val

        gs = kwargs.get("guidance_scale", 3.0)
        uc = uncond_context if gs != 1.0 else None

        scores = []
        t0 = time.monotonic()
        for i, word in enumerate(words):
            torch.manual_seed(42 + i)
            img = generate_word(
                word, unet, vae, tokenizer, style_features,
                uncond_context=uc,
                num_steps=kwargs.get("num_steps", 20),
                guidance_scale=gs,
                num_candidates=kwargs.get("num_candidates", 1),
                device=device,
            )
            qs = quality_score(img)
            if ocr_fn is not None:
                ocr = ocr_fn(img, word)
                qs = 0.5 * qs + 0.5 * ocr
            scores.append(qs)

        elapsed = time.monotonic() - t0
        qualities[val] = float(np.mean(scores))
        timings[val] = elapsed / len(words)

    # Restore RNG state
    torch.random.set_rng_state(rng_state)
    if cuda_rng_state is not None:
        torch.cuda.set_rng_state(cuda_rng_state)

    return qualities, timings


def _report_and_check(sweep_name, qualities, timings, checks):
    """Print sweep results and check presets. Fails on BLOCK severity.

    Args:
        sweep_name: Header for the output table.
        qualities: {param_value: mean_quality} from sweep.
        timings: {param_value: mean_time_per_word} from sweep.
        checks: list of (label, value, warn_pct, block_pct) tuples.
            label: e.g. "QUALITY.candidates"
            value: the preset's current value for this parameter
            warn_pct: delta fraction triggering WARN (e.g. 0.02 = 2%)
            block_pct: delta fraction triggering BLOCK (e.g. 0.05 = 5%)
    """
    values = sorted(qualities.keys())
    best_val = max(qualities, key=qualities.get)
    best_q = qualities[best_val]

    # Marker map: which presets land on which value
    markers = {}
    for label, val, _, _ in checks:
        markers.setdefault(val, []).append(label)

    print(f"\n{'=' * 56}")
    print(f"  {sweep_name}")
    print(f"{'=' * 56}")

    prev_q = None
    for val in values:
        q = qualities[val]
        t = timings.get(val, 0)
        parts = [f"  {str(val):>5}:  quality={q:.3f}  time={t:.2f}s/word"]
        if prev_q is not None and prev_q > 0:
            gain = (q - prev_q) / prev_q * 100
            parts.append(f"({gain:+.1f}%)")
        if val in markers:
            parts.append(f" <-- {', '.join(markers[val])}")
        print("  ".join(parts))
        prev_q = q

    print(f"  Best: {best_val} (quality={best_q:.3f})")

    # Diminishing returns analysis: find knee where marginal gain < 1%
    sorted_vals = sorted(qualities.keys())
    for i in range(len(sorted_vals) - 1):
        cur_q = qualities[sorted_vals[i]]
        nxt_q = qualities[sorted_vals[i + 1]]
        if cur_q > 0:
            marginal = (nxt_q - cur_q) / cur_q
            if marginal < 0.01:
                print(f"  Knee: {sorted_vals[i]} (gain from {sorted_vals[i+1]} "
                      f"is {marginal:.1%}, below 1%)")
                break

    # Check each preset
    failures = []
    for label, val, warn_pct, block_pct in checks:
        if val not in qualities:
            print(f"  {label} ({val}): SKIP -- not in sweep range")
            continue

        preset_q = qualities[val]
        if best_q <= 0:
            continue

        delta = (best_q - preset_q) / best_q

        if delta < warn_pct:
            print(f"  {label} ({val}): NOTE -- {delta:.1%} below best")
        elif delta < block_pct:
            msg = (f"TUNING: {label}={val} is {delta:.1%} below sweep best "
                   f"({best_val}, quality {best_q:.3f} vs {preset_q:.3f})")
            print(f"  {label} ({val}): WARN -- {delta:.1%} below best")
            warnings.warn(msg, stacklevel=2)
        else:
            msg = (f"TUNING: {label}={val} is {delta:.1%} below sweep best "
                   f"({best_val}, quality {best_q:.3f} vs {preset_q:.3f})")
            print(f"  {label} ({val}): BLOCK -- {delta:.1%} below best")
            failures.append(msg)

    print()
    if failures:
        pytest.fail("\n".join(failures))


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestParameterOptimality:
    """Verify generation presets are near experimentally measured optima.

    Each test sweeps one parameter, measures quality using the per-word
    quality_score (same function used for candidate selection), and checks
    that preset values are near the sweep's best.

    Uses a fixed per-word seed (42+i) for reproducibility. Stochastic
    variation from candidates > 1 is intentional (that IS what candidates
    measure). Thresholds are set wide enough to absorb run-to-run noise.
    """

    def test_candidates_optimality(
        self, unet, vae, tokenizer, style_features, uncond_context, device,
    ):
        """Sweep num_candidates: verify presets are at diminishing returns knee.

        More candidates is always at least as good (max of N draws), but the
        cost scales linearly. The QUALITY preset should be near the knee
        where marginal gain per candidate drops below 1%.
        """
        qualities, timings = _sweep(
            SWEEP_WORDS, unet, vae, tokenizer, style_features,
            uncond_context, device,
            param_name="num_candidates",
            values=[1, 2, 3, 5],
            num_steps=20,
            guidance_scale=3.0,
        )

        _report_and_check(
            "Candidates Sweep (steps=20, guidance=3.0)",
            qualities, timings,
            checks=[
                ("FAST.candidates", PRESET_FAST["candidates"], 0.05, 0.10),
                ("QUALITY.candidates", PRESET_QUALITY["candidates"], 0.02, 0.05),
            ],
        )

    def test_steps_optimality(
        self, unet, vae, tokenizer, style_features, uncond_context, device,
    ):
        """Sweep DDIM steps: verify presets bracket the quality plateau.

        Quality plateaus at some step count; more steps beyond that is
        wasted compute. FAST should be at or near the plateau. QUALITY
        can be at or beyond it.
        """
        qualities, timings = _sweep(
            SWEEP_WORDS, unet, vae, tokenizer, style_features,
            uncond_context, device,
            param_name="num_steps",
            values=[10, 15, 20, 30, 50],
            num_candidates=1,
            guidance_scale=3.0,
        )

        _report_and_check(
            "Steps Sweep (candidates=1, guidance=3.0)",
            qualities, timings,
            checks=[
                ("DRAFT.steps", PRESET_DRAFT["steps"], 0.05, 0.10),
                ("FAST.steps", PRESET_FAST["steps"], 0.02, 0.05),
                ("QUALITY.steps", PRESET_QUALITY["steps"], 0.02, 0.05),
            ],
        )

    def test_guidance_optimality(
        self, unet, vae, tokenizer, style_features, uncond_context, device,
    ):
        """Sweep guidance_scale: verify default is in the peak quality range.

        Guidance has a sweet spot: too low (1.0) disables CFG and produces
        unreadable output; too high (>5.0) can over-sharpen. Uses blended
        quality+OCR metric because CFG's main benefit is readability, which
        quality_score alone does not capture.
        """
        qualities, timings = _sweep(
            SWEEP_WORDS, unet, vae, tokenizer, style_features,
            uncond_context, device,
            param_name="guidance_scale",
            values=[1.0, 2.0, 3.0, 4.0, 5.0],
            num_candidates=1,
            num_steps=20,
            include_ocr=True,
        )

        _report_and_check(
            "Guidance Sweep (candidates=1, steps=20)",
            qualities, timings,
            checks=[
                ("DRAFT.guidance", PRESET_DRAFT["guidance_scale"], 0.05, 0.10),
                ("FAST.guidance", PRESET_FAST["guidance_scale"], 0.02, 0.05),
                ("QUALITY.guidance", PRESET_QUALITY["guidance_scale"], 0.02, 0.05),
            ],
        )
