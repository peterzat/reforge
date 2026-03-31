"""Full e2e tests: run the pipeline with real model weights.

Requires GPU and model weights. Skips without either.
"""

import os
import pytest
import torch

pytestmark = [pytest.mark.full, pytest.mark.gpu]

SKIP_REASON = "Requires CUDA GPU and model weights"


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
            num_steps=20,
            num_candidates=1,
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
            num_steps=20,
            num_candidates=1,
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
            num_steps=20,
            num_candidates=1,
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
