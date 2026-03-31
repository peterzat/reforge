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
        img = Image.open(output_path)
        assert img.width > 100
        assert img.height > 100
        assert img.mode == "L"

        # Save visual output for inspection
        os.makedirs("tests/full/output", exist_ok=True)
        img.save("tests/full/output/test_e2e.png")
