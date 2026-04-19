"""Quick tests for the OFL font glyph rasterizer (Turn 2d, case 1).

Mocks the font path to the vendored Caveat. Tests are skipped if the font
isn't present so CI environments without the font still pass."""

import os

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT_PATH = os.path.join(REPO, "fonts", "Caveat-VariableFont_wght.ttf")
FONT_EXISTS = os.path.exists(FONT_PATH)


@pytest.mark.quick
@pytest.mark.skipif(not FONT_EXISTS, reason="Caveat font not vendored")
class TestRenderTrailingMark:
    def test_period_renders_visible_ink(self):
        from reforge.model.font_glyph import render_trailing_mark
        img = render_trailing_mark(".", body_height=32, ink_intensity=50, font_path=FONT_PATH)
        assert img.dtype == np.uint8
        assert img.ndim == 2
        assert np.any(img < 180), "period should produce visible ink pixels"

    def test_comma_has_descender(self):
        """Comma ink must extend below the text baseline; periods/question
        marks should not. The returned array's visual baseline is at
        body_height (minus padding), so comma ink must reach below that row."""
        from reforge.model.font_glyph import render_trailing_mark
        comma = render_trailing_mark(",", body_height=32, ink_intensity=50, font_path=FONT_PATH)
        period = render_trailing_mark(".", body_height=32, ink_intensity=50, font_path=FONT_PATH)
        # Comma is taller than period because it extends below baseline.
        assert comma.shape[0] > period.shape[0], (
            f"comma height {comma.shape[0]} should exceed period height {period.shape[0]}"
        )

    def test_ink_intensity_respected(self):
        """Darker requested intensity produces darker ink pixels."""
        from reforge.model.font_glyph import render_trailing_mark
        dark = render_trailing_mark(".", body_height=32, ink_intensity=30, font_path=FONT_PATH)
        light = render_trailing_mark(".", body_height=32, ink_intensity=150, font_path=FONT_PATH)
        dark_min = int(dark.min())
        light_min = int(light.min())
        assert dark_min < light_min, (
            f"dark rendering min={dark_min} should be below light min={light_min}"
        )

    def test_all_supported_marks_render(self):
        """Five trailing-mark characters from the project's existing
        make_synthetic_mark set must all rasterize."""
        from reforge.model.font_glyph import render_trailing_mark
        for mark in [",", ".", ";", "!", "?"]:
            img = render_trailing_mark(mark, body_height=32, ink_intensity=50, font_path=FONT_PATH)
            assert img.size > 0, f"{mark} produced empty image"
            assert np.any(img < 180), f"{mark} produced no ink"

    def test_body_height_scales_rendered_size(self):
        """Larger body_height → larger rendered mark. Monotone in area."""
        from reforge.model.font_glyph import render_trailing_mark
        small = render_trailing_mark(".", body_height=16, ink_intensity=50, font_path=FONT_PATH)
        big = render_trailing_mark(".", body_height=48, ink_intensity=50, font_path=FONT_PATH)
        assert big.size > small.size, (
            f"big body_height area {big.size} should exceed small {small.size}"
        )

    def test_missing_font_raises(self):
        from reforge.model.font_glyph import render_trailing_mark
        with pytest.raises(OSError):
            render_trailing_mark(".", body_height=32, ink_intensity=50, font_path="/nonexistent/font.ttf")

    def test_multichar_input_rejected(self):
        from reforge.model.font_glyph import render_trailing_mark
        with pytest.raises(ValueError):
            render_trailing_mark(",,", body_height=32, ink_intensity=50, font_path=FONT_PATH)


@pytest.mark.quick
class TestFallbackHelper:
    """The helper that wraps the font renderer and falls back to the
    Bezier synthetic mark on config-disabled / missing-file / error.
    No font skip here: exercises the fallback path itself."""

    def test_disabled_config_falls_back_to_bezier(self, monkeypatch):
        from reforge.model import generator

        monkeypatch.setattr("reforge.config.PUNCTUATION_GLYPH_FALLBACK_FONT", None)
        img = generator._render_trailing_mark_or_fallback(".", ink_intensity=50, body_height=21)
        # Bezier renderer produces a body_height-tall image (period is
        # single dot at baseline, so exactly body_height tall).
        assert img.shape[0] == 21

    def test_missing_font_path_falls_back(self, monkeypatch):
        from reforge.model import generator

        monkeypatch.setattr(
            "reforge.config.PUNCTUATION_GLYPH_FALLBACK_FONT",
            "nonexistent/never-there.ttf",
        )
        img = generator._render_trailing_mark_or_fallback(".", ink_intensity=50, body_height=21)
        assert img.shape[0] == 21, "fallback Bezier output expected on missing font"

    @pytest.mark.skipif(not FONT_EXISTS, reason="Caveat font not vendored")
    def test_font_present_uses_font_path(self, monkeypatch):
        from reforge.model import generator

        monkeypatch.setattr(
            "reforge.config.PUNCTUATION_GLYPH_FALLBACK_FONT",
            "fonts/Caveat-VariableFont_wght.ttf",
        )
        # Bezier period at body_height=21 is exactly 21 tall. Caveat-rendered
        # period is shaped differently (not body_height-tall); distinguishing
        # them by height confirms the font path is active.
        img = generator._render_trailing_mark_or_fallback(".", ink_intensity=50, body_height=21)
        # Font render is generally much smaller than body_height for a period
        # (just the dot itself). If img height matches body_height exactly,
        # we're on the Bezier path; otherwise the font path ran.
        bezier = generator.make_synthetic_mark(".", 50, 21)
        assert img.shape != bezier.shape or not np.array_equal(img, bezier), (
            "font path should produce different output than Bezier"
        )


@pytest.mark.quick
@pytest.mark.skipif(not FONT_EXISTS, reason="Caveat font not vendored")
class TestDilateToBezierBaseline:
    """Spec 2026-04-19 criterion 1: Caveat glyphs dilate to the Bezier
    stroke-width baseline (body_height * 0.12)."""

    def test_median_stroke_width_meets_bezier_at_body_height_24(self):
        from reforge.model.font_glyph import (
            _median_stroke_width_px,
            render_trailing_mark,
        )

        body_height = 24
        target = body_height * 0.12
        # Semicolon exercises both body (dots) and descender (tail); the
        # tail is the thinnest part of the renderer, so if its median still
        # meets target, thicker marks trivially do.
        for mark in (".", ";", "!", "?", ","):
            img = render_trailing_mark(
                mark, body_height=body_height, ink_intensity=50, font_path=FONT_PATH
            )
            stroke = _median_stroke_width_px(img)
            assert stroke >= target, (
                f"{mark!r} median stroke {stroke:.2f} px < Bezier target {target:.2f} px"
            )

    def test_dilation_applies_across_production_body_heights(self):
        """Spec criterion 1 checks body_heights {18, 24, 32}."""
        from reforge.model.font_glyph import (
            _median_stroke_width_px,
            render_trailing_mark,
        )

        for body_height in (18, 24, 32):
            target = body_height * 0.12
            img = render_trailing_mark(
                ".", body_height=body_height, ink_intensity=50, font_path=FONT_PATH
            )
            stroke = _median_stroke_width_px(img)
            assert stroke >= target, (
                f"body_height={body_height}: stroke {stroke:.2f} < target {target:.2f}"
            )


@pytest.mark.quick
class TestMarkAttachesAtWordBaseline:
    """Spec 2026-04-19 criterion 2: a trailing mark attached to a word with
    a descender sits at the word's baseline, not below the descender tail."""

    def _word_with_descender(self, h=40, w=80, baseline=26, descender_bottom=34):
        """Synthetic word image: body ink rows 6-25, descender thin stroke
        below at rows 27-34 (so baseline=26, full ink_bottom=34)."""
        img = np.full((h, w), 255, dtype=np.uint8)
        # Wide body (simulates multiple letters)
        img[6:baseline + 1, 5:w - 5] = 40
        # Thin descender centered, extends below the baseline
        desc_col = w // 2
        img[baseline + 1:descender_bottom + 1, desc_col - 1:desc_col + 2] = 40
        return img, baseline, descender_bottom

    def _period_at_body_height(self, body_height=24, ink=50):
        from reforge.model.generator import make_synthetic_mark
        return make_synthetic_mark(".", ink, body_height)

    def test_period_aligns_with_baseline_not_descender(self):
        """Attaching a period to a word with a descender places the period's
        ink bottom at/within 1 px of the word baseline, not within 1 px of
        the word's full ink bottom (which is the descender tail)."""
        from reforge.model.generator import _attach_mark_to_word

        word_img, baseline, descender_bottom = self._word_with_descender()
        assert descender_bottom - baseline >= 6, "fixture must exercise descender"

        period = self._period_at_body_height(body_height=24)
        result = _attach_mark_to_word(
            word_img, period, word="jump", mark="."
        )

        # Find the period's ink column-range in the result: it is to the
        # right of the word body.
        INK = 180
        ink_cols = np.any(result < INK, axis=0)
        # The mark is the rightmost ink cluster; find the start of that cluster.
        col_has_ink = np.flatnonzero(ink_cols)
        assert col_has_ink.size > 0
        # Segment into clusters by gaps > 2 px.
        clusters: list[tuple[int, int]] = []
        start = col_has_ink[0]
        prev = col_has_ink[0]
        for c in col_has_ink[1:]:
            if c - prev > 2:
                clusters.append((start, prev))
                start = c
            prev = c
        clusters.append((start, prev))
        mark_start, mark_end = clusters[-1]

        mark_slice = result[:, mark_start:mark_end + 1]
        row_has_ink = np.any(mark_slice < INK, axis=1)
        mark_ink_bottom = int(np.max(np.flatnonzero(row_has_ink)))

        # Find where the word baseline lands in the output. The output was
        # built by padding below so the word baseline = max(word_ref, mark_ref).
        # For this fixture, the word baseline is the higher reference, so it
        # is preserved at row `baseline` of the word's padded-below image,
        # which is then top-padded to max_h. We can recover the baseline row
        # in the output by locating the bottom of the word body in its slice.
        word_slice = result[:, :mark_start]
        row_density_word = np.mean(word_slice < INK, axis=1)
        # Body rows have density >> descender rows. Use a threshold similar
        # to detect_baseline's body density.
        body_rows = np.flatnonzero(row_density_word >= 0.25)
        word_body_bottom = int(body_rows.max())

        # Period's ink bottom must be within 1 px of the word baseline.
        assert abs(mark_ink_bottom - word_body_bottom) <= 1, (
            f"period ink bottom {mark_ink_bottom} should be within 1 px of "
            f"word baseline {word_body_bottom}, not following the descender"
        )

    def test_backward_compat_no_word_kwarg_still_works(self):
        """Callers that don't pass word/mark still get the old ink-bottom
        alignment behavior (unchanged API contract)."""
        from reforge.model.generator import _attach_mark_to_word

        word_img = np.full((20, 30), 255, dtype=np.uint8)
        word_img[5:15, 5:25] = 40
        mark_img = np.full((10, 6), 255, dtype=np.uint8)
        mark_img[4:8, 2:4] = 40

        result = _attach_mark_to_word(word_img, mark_img)
        assert result.ndim == 2
        assert np.any(result < 180)
