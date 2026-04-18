"""Quick tests for the apostrophe overlay used by the Turn 2b full-word
contraction path. Mocks pure numpy in/out — no GPU, no DP models."""

import numpy as np
import pytest

from reforge.model.generator import _overlay_apostrophe


@pytest.mark.quick
class TestOverlayApostrophe:
    def _make_word_image(
        self,
        width: int = 200,
        height: int = 80,
        letter_positions: list[tuple[int, int]] = None,
        baseline: int = 60,
        body_top: int = 30,
        ink_val: int = 50,
    ) -> np.ndarray:
        """Build a synthetic word image with rectangular "letters" so the
        overlay's baseline/x-height/inter-letter-gap detection has ground
        truth to chew on. Letters are columns [(x0, x1), ...]; the body
        of each letter fills the rows body_top..baseline."""
        img = np.full((height, width), 255, dtype=np.uint8)
        letter_positions = letter_positions or [(10, 40), (50, 80), (90, 120), (130, 160), (170, 190)]
        for x0, x1 in letter_positions:
            img[body_top:baseline + 1, x0:x1] = ink_val
        return img

    def test_no_apostrophe_returns_unchanged(self):
        img = self._make_word_image()
        result = _overlay_apostrophe(img, "hello")
        assert np.array_equal(img, result), "images without an apostrophe should pass through"

    def test_leading_apostrophe_not_overlaid(self):
        img = self._make_word_image()
        result = _overlay_apostrophe(img, "'twas")
        assert np.array_equal(img, result), "leading apostrophe is a punctuation quote, not contraction"

    def test_trailing_apostrophe_not_overlaid(self):
        img = self._make_word_image()
        result = _overlay_apostrophe(img, "dogs'")
        assert np.array_equal(img, result), "trailing apostrophe is a possessive mark, not contraction"

    def test_blank_image_returns_unchanged(self):
        img = np.full((80, 200), 255, dtype=np.uint8)
        result = _overlay_apostrophe(img, "can't")
        assert np.array_equal(img, result), "blank images have no ink metrics; overlay should no-op"

    def test_applies_overlay_for_contraction(self):
        img = self._make_word_image()
        result = _overlay_apostrophe(img, "can't")
        assert not np.array_equal(img, result), "contraction should produce an overlay"

    def test_overlay_placed_between_letters(self):
        """Apostrophe should land in an inter-letter gap, not inside a letter."""
        img = self._make_word_image(
            letter_positions=[(10, 40), (50, 80), (90, 120), (130, 160), (170, 190)],
        )
        result = _overlay_apostrophe(img, "can't")
        # New ink pixels (where result is darker than img) should be in a
        # region that overlaps one of the inter-letter gaps, not inside a
        # letter column.
        new_ink = (result < 180) & (img >= 180)
        ink_cols = np.where(np.any(new_ink, axis=0))[0]
        assert len(ink_cols) > 0, "expected overlay to draw ink"
        mean_x = ink_cols.mean()
        # For "can't" with 5 chars, apostrophe is at index 3 (the "'") —
        # between "n" (letter 2: x=90-120) and "t" (letter 3: x=130-160).
        # Expected center around x=125 ± letter-width-tolerance.
        assert 110 <= mean_x <= 145, f"overlay should be between 'n' and 't', got x≈{mean_x:.1f}"

    def test_overlay_placed_above_x_height(self):
        """Tapered apostrophe's ink mass should sit in the ascender zone
        (above body_top), not in the middle of the letter body."""
        img = self._make_word_image(baseline=60, body_top=30)
        result = _overlay_apostrophe(img, "can't")
        new_ink = (result < 180) & (img >= 180)
        ink_rows = np.where(np.any(new_ink, axis=1))[0]
        assert len(ink_rows) > 0
        mean_y = ink_rows.mean()
        # body_top = 30, baseline = 60, so body-zone is rows 30-60.
        # Apostrophe should sit above body_top (row ~15-32 per the overlay
        # math: apos_bottom = body_top + 10% of body_h, apos_top higher).
        # Mean y should be well above baseline and above or overlapping body_top.
        assert mean_y < 35, f"apostrophe should sit above x-height line (body_top=30), got y≈{mean_y:.1f}"

    def test_line_body_height_overrides_local(self):
        """When a line-median body_height is passed, the overlay uses it
        regardless of the local image's x-height. This is the fix for the
        'it's → 4x4 apostrophe' failure where compute_x_height collapses."""
        # Narrow body image — local compute_x_height would return very small
        img = self._make_word_image(width=120, baseline=50, body_top=45)
        result_local = _overlay_apostrophe(img, "it's")
        # Inject a generous line-level body_height
        result_line = _overlay_apostrophe(img, "it's", body_height=30)

        def _ink_bbox_height(base, overlaid):
            new_ink = (overlaid < 180) & (base >= 180)
            rows = np.where(np.any(new_ink, axis=1))[0]
            return 0 if len(rows) == 0 else int(rows.max() - rows.min() + 1)

        local_h = _ink_bbox_height(img, result_local)
        line_h = _ink_bbox_height(img, result_line)
        assert line_h > local_h, (
            f"line-level body_height {30} should produce a taller apostrophe "
            f"than collapsed local x-height; got local={local_h}, line={line_h}"
        )

    def test_ink_intensity_override(self):
        """When a line-median ink_intensity is passed, the overlay uses it.
        Darker intensity (lower value) should produce darker ink pixels."""
        img = self._make_word_image()
        result_light = _overlay_apostrophe(img, "can't", ink_intensity=150)
        result_dark = _overlay_apostrophe(img, "can't", ink_intensity=30)

        def _darkest_overlay_pixel(base, overlaid):
            new_ink = (overlaid < 180) & (base >= 180)
            if not np.any(new_ink):
                return 255
            return int(overlaid[new_ink].min())

        dark_min = _darkest_overlay_pixel(img, result_dark)
        light_min = _darkest_overlay_pixel(img, result_light)
        assert dark_min < light_min, (
            f"overlay with ink_intensity=30 should produce darker pixels than 150; "
            f"got dark_min={dark_min}, light_min={light_min}"
        )

    def test_overlay_respects_image_bounds(self):
        """Apostrophe placement near image edges must not error or draw out-of-bounds."""
        img = self._make_word_image(width=60, letter_positions=[(5, 20), (30, 55)])
        result = _overlay_apostrophe(img, "it's")
        assert result.shape == img.shape
        assert result.dtype == np.uint8


@pytest.mark.quick
class TestOverlayWithFallback:
    """The OCR safety valve: if the overlay regresses OCR below
    CONTRACTION_OCR_FLOOR, fall back to the pre-Turn-2b split path
    (_generate_contraction). Mocked OCR + mocked fallback keep this
    in the quick tier without loading TrOCR or DP models."""

    def _fresh_image(self) -> np.ndarray:
        img = np.full((80, 200), 255, dtype=np.uint8)
        img[30:60, 10:190] = 50  # solid letter-ish body
        return img

    def test_overlay_path_kept_when_ocr_above_floor(self, monkeypatch):
        from reforge.model import generator

        img = self._fresh_image()
        fallback_called = {"count": 0}

        monkeypatch.setattr(generator, "_get_ocr_fn", lambda: (lambda _img, _word: 0.85))
        monkeypatch.setattr(
            generator, "_generate_contraction",
            lambda *a, **kw: (fallback_called.update(count=fallback_called["count"] + 1) or img),
        )

        out = generator._apply_contraction_overlay_with_fallback(
            img, "can't",
            unet=None, vae=None, tokenizer=None, style_features=None,
        )
        assert fallback_called["count"] == 0, "OCR above floor should not trigger fallback"
        # Overlay should have drawn something
        assert not np.array_equal(out, img)

    def test_fallback_fires_when_ocr_below_floor(self, monkeypatch):
        from reforge.model import generator

        img = self._fresh_image()
        sentinel = np.full((80, 200), 42, dtype=np.uint8)

        monkeypatch.setattr(generator, "_get_ocr_fn", lambda: (lambda _img, _word: 0.20))
        called_with = {}
        def _fake_gen(left_text, right_text, full_word, *a, **kw):
            called_with["parts"] = (left_text, right_text, full_word)
            return sentinel
        monkeypatch.setattr(generator, "_generate_contraction", _fake_gen)

        out = generator._apply_contraction_overlay_with_fallback(
            img, "can't",
            unet=None, vae=None, tokenizer=None, style_features=None,
        )
        assert called_with.get("parts") == ("can", "t", "can't"), (
            "fallback should be called with the split parts of 'can't'"
        )
        assert np.array_equal(out, sentinel), "below-floor OCR should return fallback output"

    def test_no_ocr_fn_returns_overlay_unchecked(self, monkeypatch):
        from reforge.model import generator

        img = self._fresh_image()
        monkeypatch.setattr(generator, "_get_ocr_fn", lambda: None)

        out = generator._apply_contraction_overlay_with_fallback(
            img, "can't",
            unet=None, vae=None, tokenizer=None, style_features=None,
        )
        # With no OCR available, we just return the overlay without a safety check.
        # Overlay still runs (produces non-equal output).
        assert not np.array_equal(out, img)
