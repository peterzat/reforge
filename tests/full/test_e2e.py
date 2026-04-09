"""Full e2e tests: run the pipeline with real model weights.

Requires GPU and model weights. Skips without either.

SSIM reference update procedure:
  To update the demo reference image after a validated quality improvement:
    pytest tests/full/test_e2e.py::TestDemoQualityGate::test_demo_quality_baseline \
        --update-demo-baseline --update-demo-reference -x -s
  Only update when the regression test (make test-regression) passes and
  the output has been visually reviewed.
"""

import json
import os
import pytest
import torch

from reforge.config import PRESET_FAST, PRESET_QUALITY

pytestmark = [pytest.mark.full, pytest.mark.gpu]

SKIP_REASON = "Requires CUDA GPU and model weights"

DEMO_TEXT = (
    "The morning sun cast long shadows across the quiet garden. "
    "Birds sang their familiar songs while dew drops sparkled on fresh green leaves.\n"
    "She sat near the old stone wall, reading her favorite book. "
    "The pages felt warm and soft under her fingers."
)
DEMO_BASELINE_PATH = os.path.join(os.path.dirname(__file__), "demo_baseline.json")
DEMO_REFERENCE_PATH = os.path.join(os.path.dirname(__file__), "demo_reference.png")

# Loose SSIM threshold: 43 words with 3 candidates and no fixed seed
# produces SSIM ~0.65-0.70 between consecutive runs of identical code.
# This threshold catches catastrophic regressions (blank output, wrong
# style) while tolerating normal stochastic variation. The quality
# metrics test (test_demo_quality_baseline) is the real quality guard.
DEMO_SSIM_THRESHOLD = 0.55

# Tolerance for quality metric regression
DEMO_REGRESSION_TOLERANCE = 0.05


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestE2EPipeline:
    def test_generate_note(self, tmp_path):
        """Run the full pipeline and produce a valid output image."""
        from reforge.pipeline import run

        output_path = str(tmp_path / "test_output.png")
        result = run(
            style_path="styles/hw-sample.png",
            text="Hello world from reforge",
            output_path=output_path,
            num_steps=PRESET_FAST["steps"],
            num_candidates=PRESET_FAST["candidates"],
            device="cuda",
        )

        assert os.path.exists(output_path)
        assert result["quality_scores"]["overall"] > 0

        # Check output dimensions
        from PIL import Image
        import numpy as np
        img = Image.open(output_path)
        assert img.width > 100
        assert img.height > 100
        assert img.mode == "L"

        # CV quality assertions on the composed output
        from reforge.evaluate.visual import (
            check_gray_boxes,
            check_ink_contrast,
            check_background_cleanliness,
        )
        img_arr = np.array(img)
        assert not check_gray_boxes(img_arr), "Gray box artifacts in e2e output"
        assert check_ink_contrast(img_arr) > 0.3, "Ink contrast too low in e2e output"
        assert check_background_cleanliness(img_arr) > 0.3, "Background too noisy in e2e output"

        # Save visual output for inspection
        os.makedirs("tests/full/output", exist_ok=True)
        img.save("tests/full/output/test_e2e.png")

    def test_multi_paragraph(self, tmp_path):
        """Multi-paragraph text produces output with proper vertical spacing."""
        from reforge.pipeline import run

        output_path = str(tmp_path / "test_multi_para.png")
        result = run(
            style_path="styles/hw-sample.png",
            text="First paragraph here\nSecond paragraph here",
            output_path=output_path,
            num_steps=PRESET_FAST["steps"],
            num_candidates=PRESET_FAST["candidates"],
            device="cuda",
        )

        assert os.path.exists(output_path)
        assert result["quality_scores"]["overall"] > 0

        from PIL import Image
        import numpy as np
        img = Image.open(output_path)
        assert img.mode == "L"
        arr = np.array(img)

        # Verify two distinct ink regions separated by a vertical gap
        row_has_ink = np.any(arr < 200, axis=1)
        ink_rows = np.where(row_has_ink)[0]
        assert len(ink_rows) > 0, "No ink in multi-paragraph output"

        # Find gaps (consecutive row differences > 1)
        diffs = np.diff(ink_rows)
        large_gaps = diffs[diffs > 10]
        assert len(large_gaps) >= 1, (
            "Expected at least one large vertical gap between paragraphs"
        )

        # Paragraph positions should show two paragraph starts
        positions = result["word_positions"]
        para_starts = [p for p in positions if p["is_paragraph_start"]]
        assert len(para_starts) >= 2, (
            f"Expected >= 2 paragraph starts, got {len(para_starts)}"
        )

        # CV quality assertions
        from reforge.evaluate.visual import check_gray_boxes, check_ink_contrast
        assert not check_gray_boxes(arr), "Gray boxes in multi-paragraph output"
        assert check_ink_contrast(arr) > 0.3, "Ink contrast too low"

        os.makedirs("tests/full/output", exist_ok=True)
        img.save("tests/full/output/test_multi_para.png")

    def test_long_sentence(self, tmp_path):
        """A sentence with many words forces line wrapping in the pipeline."""
        from reforge.pipeline import run

        output_path = str(tmp_path / "test_long_sentence.png")
        text = "The quick brown fox jumps over the lazy dog near the river"
        result = run(
            style_path="styles/hw-sample.png",
            text=text,
            output_path=output_path,
            num_steps=PRESET_FAST["steps"],
            num_candidates=PRESET_FAST["candidates"],
            device="cuda",
        )

        assert os.path.exists(output_path)

        from PIL import Image
        import numpy as np
        img = Image.open(output_path)
        arr = np.array(img)

        # Should have multiple lines
        positions = result["word_positions"]
        lines = set(p["line"] for p in positions)
        assert len(lines) >= 2, (
            f"12-word sentence should wrap to multiple lines, got {len(lines)}"
        )

        from reforge.evaluate.visual import (
            check_gray_boxes,
            check_background_cleanliness,
        )
        assert not check_gray_boxes(arr), "Gray boxes in long sentence output"
        assert check_background_cleanliness(arr) > 0.3

        os.makedirs("tests/full/output", exist_ok=True)
        img.save("tests/full/output/test_long_sentence.png")


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestDemoQualityGate:
    """Quality gate for the full 43-word demo output.

    Compares quality metrics against a stored baseline and pixel-level
    SSIM against a stored reference image. Looser thresholds than the
    5-word regression test because multi-paragraph output with 3 candidates
    introduces more stochasticity.
    """

    def test_demo_quality_baseline(self, request):
        """Generate the full demo text and compare against quality baseline."""
        from reforge.pipeline import run

        output_path = "tests/full/output/demo_quality_gate.png"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        result = run(
            style_path="styles/hw-sample.png",
            text=DEMO_TEXT,
            output_path=output_path,
            num_steps=PRESET_QUALITY["steps"],
            num_candidates=PRESET_QUALITY["candidates"],
            device="cuda",
        )

        # Pipeline already computes full quality scores (OCR, style, composition)
        scores = result["quality_scores"]

        print(f"\nDemo quality metrics:")
        for k, v in scores.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.4f}")

        force_update = request.config.getoption("--update-demo-baseline", default=False)

        if not os.path.exists(DEMO_BASELINE_PATH) or force_update:
            reason = "manual --update-demo-baseline" if force_update else "initial bootstrap"
            baseline = {
                "text_length": len(DEMO_TEXT.split()),
                "updated_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
                "update_reason": reason,
                "metrics": {
                    k: round(v, 4) if isinstance(v, float) else v
                    for k, v in scores.items()
                    if k not in ("gates_passed", "gate_details", "ocr_per_word")
                },
            }
            with open(DEMO_BASELINE_PATH, "w") as f:
                json.dump(baseline, f, indent=2)
            print(f"Recorded demo baseline to {DEMO_BASELINE_PATH} ({reason})")
            return

        # Compare against baseline
        with open(DEMO_BASELINE_PATH) as f:
            baseline = json.load(f)

        baseline_metrics = baseline["metrics"]
        tracked = [
            "overall", "ink_contrast", "background_cleanliness",
            "stroke_weight_consistency", "composition_score",
        ]
        regressions = []
        for metric in tracked:
            if metric not in scores or metric not in baseline_metrics:
                continue
            current = scores[metric]
            recorded = baseline_metrics[metric]
            if not isinstance(current, (int, float)) or not isinstance(recorded, (int, float)):
                continue
            if current < recorded - DEMO_REGRESSION_TOLERANCE:
                regressions.append(
                    f"{metric}: {current:.4f} < baseline {recorded:.4f}"
                )

        if regressions:
            pytest.fail(
                "Demo quality regressions:\n" + "\n".join(f"  - {r}" for r in regressions)
            )

    def test_demo_ssim(self, request):
        """Compare demo output against stored reference image using SSIM."""
        import cv2
        import numpy as np
        from reforge.pipeline import run
        from reforge.evaluate.reference import compute_ssim

        output_path = "tests/full/output/demo_quality_gate.png"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Generate if not already present from the baseline test
        if not os.path.exists(output_path):
            run(
                style_path="styles/hw-sample.png",
                text=DEMO_TEXT,
                output_path=output_path,
                num_steps=PRESET_QUALITY["steps"],
                num_candidates=PRESET_QUALITY["candidates"],
                device="cuda",
            )

        composed = cv2.imread(output_path, cv2.IMREAD_GRAYSCALE)
        assert composed is not None, f"Cannot read {output_path}"

        force_update = request.config.getoption("--update-demo-reference", default=False)

        if not os.path.exists(DEMO_REFERENCE_PATH) or force_update:
            reason = "manual --update-demo-reference" if force_update else "initial bootstrap"
            cv2.imwrite(DEMO_REFERENCE_PATH, composed)
            print(f"Saved demo reference image to {DEMO_REFERENCE_PATH} ({reason})")
            return

        reference = cv2.imread(DEMO_REFERENCE_PATH, cv2.IMREAD_GRAYSCALE)
        if reference is None:
            pytest.skip(f"Cannot read demo reference: {DEMO_REFERENCE_PATH}")

        ssim = compute_ssim(composed, reference)
        print(f"Demo SSIM against reference: {ssim:.4f} (threshold: {DEMO_SSIM_THRESHOLD})")

        if ssim < DEMO_SSIM_THRESHOLD:
            fail_path = "tests/full/output/demo_ssim_failed.png"
            cv2.imwrite(fail_path, composed)
            pytest.fail(
                f"Demo pixel-level regression: SSIM {ssim:.4f} < {DEMO_SSIM_THRESHOLD}. "
                f"Output saved to {fail_path}."
            )
