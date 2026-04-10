"""B1 diagnostic: measure descender clipping at generation and composition stages.

Generates words with known descenders and reports:
- How much ink falls below the detected baseline
- Whether ink reaches the canvas bottom (generation-stage clipping)
- Whether baseline detection places descender words correctly
"""

import numpy as np
import pytest
import torch

from reforge.compose.layout import detect_baseline
from reforge.config import DEFAULT_CANVAS_HEIGHT
from reforge.model.generator import generate_word, postprocess_word, ddim_sample, compute_canvas_width


@pytest.mark.medium
@pytest.mark.gpu
class TestDescenderDiagnostic:
    """B1: Diagnose descender clipping at generation vs composition stage."""

    DESCENDER_WORDS = ["jumping", "quickly", "gypsy", "peppy", "gasp"]

    def test_descender_clipping_diagnosis(
        self, unet, vae, tokenizer, style_features, uncond_context, device,
    ):
        """Generate descender words and measure ink position relative to canvas."""
        results = []

        for word in self.DESCENDER_WORDS:
            canvas_width = compute_canvas_width(len(word))
            text_ctx = tokenizer(word, return_tensors="pt", padding="max_length", max_length=16)

            # Generate raw image (before postprocessing) to see full canvas usage
            raw_img = ddim_sample(
                unet, vae, text_ctx, style_features,
                uncond_context=uncond_context,
                canvas_width=canvas_width,
                device=device,
            )
            processed_img = postprocess_word(raw_img)

            # Measure ink extent on processed image
            ink_mask = processed_img < 180
            if not np.any(ink_mask):
                results.append({"word": word, "has_ink": False})
                continue

            ink_rows = np.any(ink_mask, axis=1)
            first_ink_row = int(np.argmax(ink_rows))
            last_ink_row = len(ink_rows) - 1 - int(np.argmax(ink_rows[::-1]))
            canvas_h = processed_img.shape[0]

            # Detect baseline
            baseline = detect_baseline(processed_img)

            # Measure descender depth
            ink_below_baseline = last_ink_row - baseline if last_ink_row > baseline else 0
            ink_at_canvas_bottom = last_ink_row >= canvas_h - 2  # within 2px of bottom

            # Raw image: check if strong ink (< 128) touches canvas bottom
            raw_ink_rows = np.any(raw_img < 128, axis=1)
            raw_last_ink = len(raw_ink_rows) - 1 - int(np.argmax(raw_ink_rows[::-1])) if np.any(raw_ink_rows) else 0
            raw_at_bottom = raw_last_ink >= raw_img.shape[0] - 2

            results.append({
                "word": word,
                "has_ink": True,
                "canvas_h": canvas_h,
                "first_ink_row": first_ink_row,
                "last_ink_row": last_ink_row,
                "baseline": baseline,
                "ink_below_baseline": ink_below_baseline,
                "ink_at_canvas_bottom": ink_at_canvas_bottom,
                "raw_at_bottom": raw_at_bottom,
                "descender_pct": ink_below_baseline / (last_ink_row - first_ink_row + 1) * 100 if last_ink_row > first_ink_row else 0,
            })

        # Report findings
        print("\n=== Descender Clipping Diagnostic ===")
        generation_clipping = 0
        composition_issues = 0

        for r in results:
            if not r["has_ink"]:
                print(f"  {r['word']}: NO INK (generation failed)")
                continue

            status = []
            if r["raw_at_bottom"]:
                status.append("GEN-CLIPPED")
                generation_clipping += 1
            if r["ink_below_baseline"] > 0 and r["descender_pct"] > 30:
                status.append(f"LARGE-DESCENDER({r['descender_pct']:.0f}%)")
            if r["ink_at_canvas_bottom"] and not r["raw_at_bottom"]:
                status.append("COMPOSITION-ISSUE")
                composition_issues += 1

            flags = " ".join(status) if status else "OK"
            print(
                f"  {r['word']:12s}: canvas={r['canvas_h']}px "
                f"ink=[{r['first_ink_row']}-{r['last_ink_row']}] "
                f"baseline={r['baseline']} "
                f"below_baseline={r['ink_below_baseline']}px "
                f"({r['descender_pct']:.0f}%) "
                f"{flags}"
            )

        print(f"\nGeneration-stage clipping: {generation_clipping}/{len(results)}")
        print(f"Composition-stage issues: {composition_issues}/{len(results)}")

        # This is diagnostic: no hard assertion, just record findings.
        # The test passes regardless; findings inform B2/B3 decisions.
        assert True
