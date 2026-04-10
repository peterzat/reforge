"""Quality regression test: generates fixed words at multiple seeds, computes
metrics, and fails if any PRIMARY metric drops below its recorded baseline on
any seed.

Baselines are stored in tests/medium/quality_baseline.json, keyed by seed.
The format is documented in TESTING.md. If the file does not exist, the test
records new baselines and passes (first run bootstraps the file). Subsequent
runs compare against recorded baselines.

Gating (spec 2026-04-10 B2-B3, C1):
- Only metrics in PRIMARY_METRICS (from reforge/config.py) gate the build.
- All other TRACKED_METRICS are diagnostics: printed on regression but non-fatal.
- The OCR min gate (0.3) still fires independently as a readability guardrail.
- Every primary metric must be non-regressing on EVERY seed for the gate to pass.
- Baseline updates only via explicit `pytest --update-baseline`. The previous
  auto-update-on-improvement behavior was removed to prevent baseline drift.

Requires GPU. Skips without CUDA.
"""

import json
import os
from datetime import datetime, timezone

import cv2
import numpy as np
import pytest
import torch

pytestmark = [pytest.mark.medium, pytest.mark.gpu]

SKIP_REASON = "Requires CUDA GPU"
BASELINE_PATH = os.path.join(os.path.dirname(__file__), "quality_baseline.json")
LEDGER_PATH = os.path.join(os.path.dirname(__file__), "quality_ledger.jsonl")

# SSIM reference image update procedure:
#   The reference image is only updated via an explicit command:
#     pytest tests/medium/test_quality_regression.py --update-reference -x -s
#   This requires the regression test to pass first (all metrics non-regressing).
#   Never auto-update the reference as a side effect of running tests.
REFERENCE_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "reference_output.png")

# SSIM threshold: identical seed/model should produce near-identical output.
# Allow for minor floating-point variation across runs.
SSIM_THRESHOLD = 0.80

# Fixed test configuration. Three seeds exercise generation variance; the gate
# passes only when all primary metrics are non-regressing on every seed.
SEEDS = [42, 137, 2718]
# The canonical single-seed used for pixel-level reference and legacy comparisons.
REFERENCE_SEED = 42
TEST_WORDS = ["Quick", "brown", "foxes", "jump", "high"]

from reforge.config import PRESET_FAST, PRIMARY_METRICS
NUM_STEPS = PRESET_FAST["steps"]
GUIDANCE_SCALE = PRESET_FAST["guidance_scale"]

# Metrics where higher is better (regression = value drops).
# Everything here that is NOT in PRIMARY_METRICS is a diagnostic.
TRACKED_METRICS = [
    "overall",
    "gray_boxes",
    "ink_contrast",
    "background_cleanliness",
    "stroke_weight_consistency",
    "word_height_ratio",
    "composition_score",
    "ocr_accuracy",
    "style_fidelity",
    "baseline_alignment",
    "height_outlier_score",
]

# Metrics where lower is better (regression = value increases)
TRACKED_METRICS_INVERTED = [
    "height_outlier_ratio",
]

# Tolerance: allow up to this much regression before failing
REGRESSION_TOLERANCE = 0.05


_cached_results: dict[int, tuple] = {}


def _generate_for_seed(
    seed, unet, vae, tokenizer, style_features, uncond_context, device,
    style_word_images=None,
):
    """Generate test words with a specific seed. Cached per seed in-process.

    Models are reused across seeds via the session-scoped fixtures, so only
    the DDIM loop re-runs per seed (~5s per seed on this box).
    """
    if seed in _cached_results:
        return _cached_results[seed]

    from reforge.evaluate.visual import overall_quality_score
    from reforge.model.generator import generate_word
    from reforge.quality.font_scale import normalize_font_size
    from reforge.quality.harmonize import harmonize_words

    torch.manual_seed(seed)
    np.random.seed(seed)

    imgs = []
    for w in TEST_WORDS:
        img = generate_word(
            w, unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=NUM_STEPS, guidance_scale=GUIDANCE_SCALE,
            num_candidates=1, device=device,
        )
        imgs.append(normalize_font_size(img, w))

    imgs = harmonize_words(imgs)

    from reforge.compose.render import compose_words

    composed, positions = compose_words(
        imgs, TEST_WORDS, upscale_factor=1, return_positions=True,
    )
    composed_arr = np.array(composed)

    scores = overall_quality_score(
        composed_arr, word_imgs=imgs, word_positions=positions,
        words=TEST_WORDS, style_reference_imgs=style_word_images,
    )
    _cached_results[seed] = (scores, imgs, composed_arr)
    return _cached_results[seed]


def _load_baseline():
    """Load recorded baseline (dict with per-seed entries), or None."""
    if not os.path.exists(BASELINE_PATH):
        return None
    with open(BASELINE_PATH) as f:
        return json.load(f)


def _save_baseline(per_seed_scores: dict[int, dict], reason="manual"):
    """Save current per-seed scores as the new baseline.

    Format (spec 2026-04-10 C3):
        {
          "words": [...],
          "num_steps": 20,
          "guidance_scale": 3.0,
          "updated_at": "<iso>",
          "update_reason": "<str>",
          "seeds": {
            "42":   { "metrics": {...} },
            "137":  { "metrics": {...} },
            "2718": { "metrics": {...} }
          }
        }
    """
    baseline = {
        "words": TEST_WORDS,
        "num_steps": NUM_STEPS,
        "guidance_scale": GUIDANCE_SCALE,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "update_reason": reason,
        "seeds": {},
    }
    for seed, scores in per_seed_scores.items():
        baseline["seeds"][str(seed)] = {
            "metrics": {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in scores.items()
                if k not in ("gates_passed", "gate_details")
            },
        }
    with open(BASELINE_PATH, "w") as f:
        json.dump(baseline, f, indent=2)
    return baseline


def _seed_baseline_metrics(baseline, seed):
    """Look up per-seed metrics in the baseline, handling legacy format.

    The legacy format (pre-C3) had top-level `metrics` keyed to a single seed.
    We read that for backward compat but always save in the new format.
    """
    if baseline is None:
        return None
    if "seeds" in baseline:
        entry = baseline["seeds"].get(str(seed))
        return entry["metrics"] if entry else None
    # Legacy: single-seed baseline. Only valid for REFERENCE_SEED.
    if seed == REFERENCE_SEED and "metrics" in baseline:
        return baseline["metrics"]
    return None


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestQualityRegression:
    def test_no_metric_regression(
        self, request, unet, vae, tokenizer, style_features, uncond_context, device,
        style_word_images,
    ):
        """Generate across SEEDS, check PRIMARY_METRICS against baseline."""
        from reforge.evaluate.ledger import append_entry
        from reforge.evaluate.regression_gate import (
            check_metric_regressions, check_ocr_min_gate,
        )

        primary_higher = [m for m in PRIMARY_METRICS if m not in TRACKED_METRICS_INVERTED]
        primary_lower = [m for m in PRIMARY_METRICS if m in TRACKED_METRICS_INVERTED]
        diagnostic_higher = [
            m for m in TRACKED_METRICS if m not in PRIMARY_METRICS
        ]
        diagnostic_lower = [
            m for m in TRACKED_METRICS_INVERTED if m not in PRIMARY_METRICS
        ]

        per_seed_scores: dict[int, dict] = {}
        for seed in SEEDS:
            scores, _, _ = _generate_for_seed(
                seed, unet, vae, tokenizer, style_features, uncond_context, device,
                style_word_images=style_word_images,
            )
            per_seed_scores[seed] = scores
            append_entry(
                LEDGER_PATH, scores,
                config={
                    "seed": seed, "num_steps": NUM_STEPS,
                    "guidance_scale": GUIDANCE_SCALE,
                },
                context=f"regression test seed={seed}",
            )

        force_update = request.config.getoption("--update-baseline", default=False)

        baseline = _load_baseline()
        if baseline is None or force_update:
            reason = "manual --update-baseline" if force_update else "initial bootstrap"
            _save_baseline(per_seed_scores, reason=reason)
            print(f"Recorded baseline to {BASELINE_PATH} ({reason})")
            for seed, scores in per_seed_scores.items():
                print(f"\nSeed {seed}:")
                for k in TRACKED_METRICS + TRACKED_METRICS_INVERTED:
                    if k in scores:
                        print(f"  {k}: {scores[k]:.4f}")
            return

        # OCR min gate: any word with OCR < 0.3 on any seed is an immediate failure
        for seed, scores in per_seed_scores.items():
            ok, ocr_min = check_ocr_min_gate(scores, floor=0.3)
            if not ok:
                per_word = scores.get("ocr_per_word", [])
                pytest.fail(
                    f"OCR min gate failed on seed {seed}: worst word OCR = "
                    f"{ocr_min:.3f} (threshold: 0.3). Per-word OCR: {per_word}"
                )

        all_primary_regressions: list[str] = []
        diagnostic_messages: list[str] = []
        all_improvements: list[str] = []

        for seed, scores in per_seed_scores.items():
            baseline_metrics = _seed_baseline_metrics(baseline, seed)
            if baseline_metrics is None:
                pytest.fail(
                    f"Baseline missing for seed {seed}. Run "
                    f"`pytest tests/medium/test_quality_regression.py "
                    f"--update-baseline -x -s` to bootstrap all seeds."
                )

            # Primary metrics: gating
            primary_regs, primary_improvs, _ = check_metric_regressions(
                scores, baseline_metrics,
                metrics_higher=primary_higher,
                metrics_lower=primary_lower,
                tolerance=REGRESSION_TOLERANCE,
            )
            for r in primary_regs:
                all_primary_regressions.append(f"seed={seed}: {r}")
            for i in primary_improvs:
                all_improvements.append(f"seed={seed}: {i}")

            # Diagnostic metrics: logged, never gating
            diag_regs, diag_improvs, _ = check_metric_regressions(
                scores, baseline_metrics,
                metrics_higher=diagnostic_higher,
                metrics_lower=diagnostic_lower,
                tolerance=REGRESSION_TOLERANCE,
            )
            for r in diag_regs:
                diagnostic_messages.append(f"seed={seed}: {r}")
            for i in diag_improvs:
                all_improvements.append(f"seed={seed} [diag]: {i}")

        if diagnostic_messages:
            print("\nDiagnostic regressions (non-fatal, logged only):")
            for m in diagnostic_messages:
                print(f"  - {m}")

        if all_primary_regressions:
            msg = (
                f"Primary metric regressions on {len(SEEDS)}-seed run "
                f"(primary = {PRIMARY_METRICS}):\n"
                + "\n".join(f"  - {r}" for r in all_primary_regressions)
            )
            if diagnostic_messages:
                msg += "\n\nDiagnostic regressions (non-fatal, for context):\n" + "\n".join(
                    f"  - {d}" for d in diagnostic_messages
                )
            if all_improvements:
                msg += "\n\nMetrics that improved:\n" + "\n".join(
                    f"  + {i}" for i in all_improvements
                )
            pytest.fail(msg)

        # Drift check (soft gate, warn only) runs on the reference seed only
        # to keep the ledger view uncluttered and to avoid interpreting
        # cross-seed variance as drift. The ledger now contains interleaved
        # per-seed entries; filtering by context restricts the window to a
        # single seed's history.
        from reforge.evaluate.ledger import detect_drift
        drift_filter = f"regression test seed={REFERENCE_SEED}"
        for metric in PRIMARY_METRICS:
            drifted, first_val, last_val = detect_drift(
                LEDGER_PATH, metric, context_filter=drift_filter,
            )
            if drifted:
                print(
                    f"WARNING: drift detected in {metric}: "
                    f"{first_val:.4f} -> {last_val:.4f} "
                    f"(declined {first_val - last_val:.4f} over recent runs)"
                )

        # Baseline auto-update is disabled (spec 2026-04-10 B3). Improvements
        # are printed so a human can decide whether to run --update-baseline.
        if all_improvements:
            print("\nImprovements observed (baseline NOT updated automatically):")
            for i in all_improvements:
                print(f"  + {i}")
            print("\nRun `pytest --update-baseline -x -s` to promote these.")

    def test_pixel_level_regression(
        self, request, unet, vae, tokenizer, style_features, uncond_context, device,
        style_word_images,
    ):
        """Compare generated output against stored reference image using SSIM.

        Uses the REFERENCE_SEED (42) so the stored PNG is a stable artifact,
        not dependent on iteration order over SEEDS.
        """
        from reforge.evaluate.reference import compute_ssim

        force_update = request.config.getoption("--update-reference", default=False)

        _, _imgs, composed = _generate_for_seed(
            REFERENCE_SEED, unet, vae, tokenizer, style_features, uncond_context, device,
            style_word_images=style_word_images,
        )

        if not os.path.exists(REFERENCE_IMAGE_PATH) or force_update:
            reason = "manual --update-reference" if force_update else "initial bootstrap"
            cv2.imwrite(REFERENCE_IMAGE_PATH, composed)
            print(f"Saved reference image to {REFERENCE_IMAGE_PATH} ({reason})")
            return

        reference = cv2.imread(REFERENCE_IMAGE_PATH, cv2.IMREAD_GRAYSCALE)
        if reference is None:
            pytest.skip(f"Cannot read reference image: {REFERENCE_IMAGE_PATH}")

        ssim = compute_ssim(composed, reference)
        print(f"SSIM against reference: {ssim:.4f} (threshold: {SSIM_THRESHOLD})")

        if ssim < SSIM_THRESHOLD:
            fail_path = os.path.join(os.path.dirname(__file__), "failed_output.png")
            cv2.imwrite(fail_path, composed)
            pytest.fail(
                f"Pixel-level regression: SSIM {ssim:.4f} < {SSIM_THRESHOLD}. "
                f"Output saved to {fail_path} for comparison."
            )
