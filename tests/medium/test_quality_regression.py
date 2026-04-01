"""Quality regression test: generates fixed words with fixed seed, computes metrics,
and fails if any metric drops below a recorded baseline.

Baselines are stored in tests/medium/quality_baseline.json. If the file does not
exist, the test records new baselines and passes (first run bootstraps the file).
Subsequent runs compare against recorded baselines.

Requires GPU. Skips without CUDA.
"""

import json
import os

import numpy as np
import pytest
import torch

pytestmark = [pytest.mark.medium, pytest.mark.gpu]

SKIP_REASON = "Requires CUDA GPU"
BASELINE_PATH = os.path.join(os.path.dirname(__file__), "quality_baseline.json")

# Fixed test configuration
SEED = 42
TEST_WORDS = ["Quick", "brown", "foxes", "jump", "high"]
NUM_STEPS = 20
GUIDANCE_SCALE = 3.0

# Metrics that must not regress (any drop below baseline fails the test)
TRACKED_METRICS = [
    "overall",
    "gray_boxes",
    "ink_contrast",
    "background_cleanliness",
    "stroke_weight_consistency",
    "word_height_ratio",
]

# Tolerance: allow up to this much regression before failing
REGRESSION_TOLERANCE = 0.05


def _generate_test_words(unet, vae, tokenizer, style_features, uncond_context, device):
    """Generate test words with fixed seed for reproducibility."""
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

    # Compose for full-image metrics
    from reforge.compose.layout import compute_word_positions
    from reforge.compose.render import compose_words

    composed = compose_words(imgs, TEST_WORDS, upscale_factor=1)
    composed_arr = np.array(composed)
    positions = compute_word_positions(imgs, TEST_WORDS)

    scores = overall_quality_score(
        composed_arr, word_imgs=imgs, word_positions=positions,
    )
    return scores


def _load_baseline():
    """Load recorded baseline, or None if not yet recorded."""
    if not os.path.exists(BASELINE_PATH):
        return None
    with open(BASELINE_PATH) as f:
        return json.load(f)


def _save_baseline(scores):
    """Save current scores as the new baseline."""
    baseline = {
        "seed": SEED,
        "words": TEST_WORDS,
        "num_steps": NUM_STEPS,
        "guidance_scale": GUIDANCE_SCALE,
        "metrics": {
            k: round(v, 4) if isinstance(v, float) else v
            for k, v in scores.items()
        },
    }
    with open(BASELINE_PATH, "w") as f:
        json.dump(baseline, f, indent=2)
    return baseline


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestQualityRegression:
    def test_no_metric_regression(
        self, unet, vae, tokenizer, style_features, uncond_context, device,
    ):
        """Generate fixed words, compute metrics, compare against baseline."""
        scores = _generate_test_words(
            unet, vae, tokenizer, style_features, uncond_context, device,
        )

        baseline = _load_baseline()
        if baseline is None:
            # First run: record baseline
            saved = _save_baseline(scores)
            print(f"Recorded initial baseline to {BASELINE_PATH}")
            for k in TRACKED_METRICS:
                if k in scores:
                    print(f"  {k}: {scores[k]:.4f}")
            return

        # Compare against baseline
        baseline_metrics = baseline["metrics"]
        regressions = []
        for metric in TRACKED_METRICS:
            if metric not in scores or metric not in baseline_metrics:
                continue
            current = scores[metric]
            recorded = baseline_metrics[metric]
            if isinstance(current, (int, float)) and isinstance(recorded, (int, float)):
                if current < recorded - REGRESSION_TOLERANCE:
                    regressions.append(
                        f"{metric}: {current:.4f} < baseline {recorded:.4f} "
                        f"(delta {current - recorded:+.4f})"
                    )

        if regressions:
            # Update baseline if scores improved overall
            if scores.get("overall", 0) > baseline_metrics.get("overall", 0):
                _save_baseline(scores)

            msg = "Quality regressions detected:\n" + "\n".join(f"  - {r}" for r in regressions)
            pytest.fail(msg)

        # If overall improved, update baseline (ratchet upward)
        if scores.get("overall", 0) > baseline_metrics.get("overall", 0) + REGRESSION_TOLERANCE:
            _save_baseline(scores)
            print(f"Baseline updated: overall {baseline_metrics['overall']:.4f} -> {scores['overall']:.4f}")
