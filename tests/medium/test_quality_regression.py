"""Quality regression test: generates fixed words with fixed seed, computes metrics,
and fails if any metric drops below a recorded baseline.

Baselines are stored in tests/medium/quality_baseline.json. If the file does not
exist, the test records new baselines and passes (first run bootstraps the file).
Subsequent runs compare against recorded baselines.

Baseline updates: use `pytest --update-baseline` to regenerate the baseline
unconditionally. Auto-update only occurs when EVERY tracked metric is
non-regressing (no single metric may degrade during auto-update).

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

# Fixed test configuration
SEED = 42
TEST_WORDS = ["Quick", "brown", "foxes", "jump", "high"]

from reforge.config import PRESET_FAST
NUM_STEPS = PRESET_FAST["steps"]
GUIDANCE_SCALE = PRESET_FAST["guidance_scale"]

# Metrics where higher is better (regression = value drops)
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
]

# Metrics where lower is better (regression = value increases)
TRACKED_METRICS_INVERTED = [
    "height_outlier_ratio",
]

# Tolerance: allow up to this much regression before failing
REGRESSION_TOLERANCE = 0.05


_cached_result = None


def _generate_test_words(
    unet, vae, tokenizer, style_features, uncond_context, device,
    style_word_images=None,
):
    """Generate test words with fixed seed for reproducibility.

    Results are cached at module level so both regression tests share
    the same GPU generation (A1: ~7s saved per session).
    """
    global _cached_result
    if _cached_result is not None:
        return _cached_result

    from reforge.evaluate.visual import overall_quality_score
    from reforge.model.generator import generate_word
    from reforge.quality.font_scale import normalize_font_size
    from reforge.quality.harmonize import harmonize_words

    torch.manual_seed(SEED)
    np.random.seed(SEED)

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

    # Compose for full-image metrics (use actual positions from compositor)
    from reforge.compose.render import compose_words

    composed, positions = compose_words(
        imgs, TEST_WORDS, upscale_factor=1, return_positions=True,
    )
    composed_arr = np.array(composed)

    scores = overall_quality_score(
        composed_arr, word_imgs=imgs, word_positions=positions,
        words=TEST_WORDS, style_reference_imgs=style_word_images,
    )
    _cached_result = (scores, imgs, composed_arr)
    return _cached_result


def _load_baseline():
    """Load recorded baseline, or None if not yet recorded."""
    if not os.path.exists(BASELINE_PATH):
        return None
    with open(BASELINE_PATH) as f:
        return json.load(f)


def _save_baseline(scores, reason="auto"):
    """Save current scores as the new baseline."""
    baseline = {
        "seed": SEED,
        "words": TEST_WORDS,
        "num_steps": NUM_STEPS,
        "guidance_scale": GUIDANCE_SCALE,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "update_reason": reason,
        "metrics": {
            k: round(v, 4) if isinstance(v, float) else v
            for k, v in scores.items()
            if k not in ("gates_passed", "gate_details")
        },
    }
    with open(BASELINE_PATH, "w") as f:
        json.dump(baseline, f, indent=2)
    return baseline


def _check_all_non_regressing(scores, baseline_metrics):
    """Check that every tracked metric is non-regressing within tolerance.

    Returns (all_ok, regressions_list, improvements_list).
    """
    regressions = []
    improvements = []
    stable = []

    for metric in TRACKED_METRICS:
        if metric not in scores or metric not in baseline_metrics:
            continue
        current = scores[metric]
        recorded = baseline_metrics[metric]
        if not isinstance(current, (int, float)) or not isinstance(recorded, (int, float)):
            continue
        delta = current - recorded
        if delta < -REGRESSION_TOLERANCE:
            regressions.append(
                f"{metric}: {current:.4f} < baseline {recorded:.4f} (delta {delta:+.4f})"
            )
        elif delta > REGRESSION_TOLERANCE:
            improvements.append(f"{metric}: {current:.4f} (was {recorded:.4f}, +{delta:.4f})")
        else:
            stable.append(metric)

    for metric in TRACKED_METRICS_INVERTED:
        if metric not in scores or metric not in baseline_metrics:
            continue
        current = scores[metric]
        recorded = baseline_metrics[metric]
        if not isinstance(current, (int, float)) or not isinstance(recorded, (int, float)):
            continue
        delta = current - recorded
        if delta > REGRESSION_TOLERANCE:
            regressions.append(
                f"{metric}: {current:.4f} > baseline {recorded:.4f} (delta {delta:+.4f})"
            )
        elif delta < -REGRESSION_TOLERANCE:
            improvements.append(f"{metric}: {current:.4f} (was {recorded:.4f}, {delta:+.4f})")
        else:
            stable.append(metric)

    return len(regressions) == 0, regressions, improvements


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestQualityRegression:
    def test_no_metric_regression(
        self, request, unet, vae, tokenizer, style_features, uncond_context, device,
        style_word_images,
    ):
        """Generate fixed words, compute metrics, compare against baseline."""
        scores, imgs, composed = _generate_test_words(
            unet, vae, tokenizer, style_features, uncond_context, device,
            style_word_images=style_word_images,
        )

        # Record to ledger
        from reforge.evaluate.ledger import append_entry
        append_entry(
            LEDGER_PATH, scores,
            config={"seed": SEED, "num_steps": NUM_STEPS, "guidance_scale": GUIDANCE_SCALE},
            context="regression test",
        )

        force_update = request.config.getoption("--update-baseline", default=False)

        baseline = _load_baseline()
        if baseline is None or force_update:
            reason = "manual --update-baseline" if force_update else "initial bootstrap"
            saved = _save_baseline(scores, reason=reason)
            print(f"Recorded baseline to {BASELINE_PATH} ({reason})")
            for k in TRACKED_METRICS + TRACKED_METRICS_INVERTED:
                if k in scores:
                    print(f"  {k}: {scores[k]:.4f}")
            return

        # Compare against baseline
        baseline_metrics = baseline["metrics"]
        all_ok, regressions, improvements = _check_all_non_regressing(
            scores, baseline_metrics,
        )

        # OCR min gate: any word with OCR < 0.3 is an immediate failure
        ocr_min = scores.get("ocr_min")
        if ocr_min is not None and ocr_min < 0.3:
            per_word = scores.get("ocr_per_word", [])
            pytest.fail(
                f"OCR min gate failed: worst word OCR = {ocr_min:.3f} (threshold: 0.3). "
                f"Per-word OCR: {per_word}"
            )

        if not all_ok:
            msg = "Quality regressions detected:\n" + "\n".join(
                f"  - {r}" for r in regressions
            )
            if improvements:
                msg += "\n\nMetrics that improved:\n" + "\n".join(
                    f"  + {i}" for i in improvements
                )

            # Cross-tier signal: compare against previous ledger entry
            from reforge.evaluate.ledger import recent_runs
            prev_runs = recent_runs(LEDGER_PATH, n=2)
            if len(prev_runs) >= 2:
                prev = prev_runs[-2]["scores"]
                msg += "\n\nDelta from previous run:"
                for m in TRACKED_METRICS + TRACKED_METRICS_INVERTED:
                    cur_v = scores.get(m)
                    prev_v = prev.get(m)
                    if cur_v is not None and prev_v is not None:
                        delta = cur_v - prev_v
                        direction = "+" if delta >= 0 else ""
                        status = "REGRESSED" if m in [r.split(":")[0] for r in regressions] else "ok"
                        msg += f"\n  {m}: {cur_v:.4f} (was {prev_v:.4f}, {direction}{delta:.4f}) [{status}]"

            pytest.fail(msg)

        # Check for drift across recent runs (soft gate: warn, don't fail)
        from reforge.evaluate.ledger import detect_drift
        for metric in TRACKED_METRICS:
            drifted, first_val, last_val = detect_drift(LEDGER_PATH, metric)
            if drifted:
                print(
                    f"WARNING: drift detected in {metric}: "
                    f"{first_val:.4f} -> {last_val:.4f} "
                    f"(declined {first_val - last_val:.4f} over recent runs)"
                )

        # Auto-update only when EVERY metric is non-regressing and at least
        # one metric improved beyond tolerance
        if improvements:
            _save_baseline(scores, reason="auto: all metrics non-regressing")
            print("Baseline updated (all metrics non-regressing):")
            for i in improvements:
                print(f"  + {i}")

    def test_pixel_level_regression(
        self, request, unet, vae, tokenizer, style_features, uncond_context, device,
        style_word_images,
    ):
        """Compare generated output against stored reference image using SSIM."""
        from reforge.evaluate.reference import compute_ssim

        force_update = request.config.getoption("--update-reference", default=False)

        _, imgs, composed = _generate_test_words(
            unet, vae, tokenizer, style_features, uncond_context, device,
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
            # Save the failing output for debugging
            fail_path = os.path.join(os.path.dirname(__file__), "failed_output.png")
            cv2.imwrite(fail_path, composed)
            pytest.fail(
                f"Pixel-level regression: SSIM {ssim:.4f} < {SSIM_THRESHOLD}. "
                f"Output saved to {fail_path} for comparison."
            )
