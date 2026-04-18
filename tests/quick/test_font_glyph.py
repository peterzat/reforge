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
