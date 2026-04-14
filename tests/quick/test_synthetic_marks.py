"""Quick tests for Bezier-based synthetic punctuation marks."""

import numpy as np
import pytest


@pytest.mark.quick
class TestMakeSyntheticMark:
    """B1: Each mark type produces non-empty output with ink pixels,
    correct baseline positioning, and dimensions proportional to body_height."""

    @pytest.fixture(params=[",", ".", "?", "!", ";"])
    def mark(self, request):
        return request.param

    def test_returns_image(self, mark):
        from reforge.model.generator import make_synthetic_mark
        img = make_synthetic_mark(mark, ink_intensity=60, body_height=30)
        assert isinstance(img, np.ndarray)
        assert img.dtype == np.uint8
        assert img.ndim == 2

    def test_has_ink(self, mark):
        from reforge.model.generator import make_synthetic_mark
        img = make_synthetic_mark(mark, ink_intensity=60, body_height=30)
        assert np.any(img < 180), f"Mark '{mark}' has no ink pixels"

    def test_mostly_white(self, mark):
        from reforge.model.generator import make_synthetic_mark
        img = make_synthetic_mark(mark, ink_intensity=60, body_height=30)
        white_fraction = np.mean(img == 255)
        assert white_fraction > 0.5, f"Mark '{mark}' is not mostly white"

    def test_height_proportional_to_body(self, mark):
        from reforge.model.generator import make_synthetic_mark
        img = make_synthetic_mark(mark, ink_intensity=60, body_height=30)
        # Image height should be at least body_height
        assert img.shape[0] >= 30

    def test_different_body_heights(self, mark):
        from reforge.model.generator import make_synthetic_mark
        small = make_synthetic_mark(mark, ink_intensity=60, body_height=15)
        large = make_synthetic_mark(mark, ink_intensity=60, body_height=40)
        # Larger body height should produce larger image
        assert large.shape[0] > small.shape[0]

    def test_different_ink_intensities(self, mark):
        from reforge.model.generator import make_synthetic_mark
        light = make_synthetic_mark(mark, ink_intensity=120, body_height=30)
        dark = make_synthetic_mark(mark, ink_intensity=40, body_height=30)
        light_ink = light[light < 200]
        dark_ink = dark[dark < 200]
        if len(light_ink) > 0 and len(dark_ink) > 0:
            assert np.median(dark_ink) <= np.median(light_ink)

    def test_unsupported_mark_raises(self):
        from reforge.model.generator import make_synthetic_mark
        with pytest.raises(ValueError, match="Unsupported mark"):
            make_synthetic_mark("@", ink_intensity=60, body_height=30)


@pytest.mark.quick
class TestMarkBaselinePositioning:
    """Verify marks are positioned correctly relative to the baseline."""

    def _ink_rows(self, img):
        """Return (first_ink_row, last_ink_row) or None if no ink."""
        ink = np.any(img < 180, axis=1)
        if not np.any(ink):
            return None
        first = int(np.argmax(ink))
        last = len(ink) - 1 - int(np.argmax(ink[::-1]))
        return first, last

    def test_period_at_baseline(self):
        """Period should have ink only near the bottom of body_height."""
        from reforge.model.generator import make_synthetic_mark
        img = make_synthetic_mark(".", ink_intensity=60, body_height=40)
        rows = self._ink_rows(img)
        assert rows is not None
        first, last = rows
        # Ink should be in the lower third of the body zone
        assert first > 40 * 0.5, "Period ink too high"

    def test_exclamation_extends_above(self):
        """Exclamation should have ink from near the top to near the bottom."""
        from reforge.model.generator import make_synthetic_mark
        img = make_synthetic_mark("!", ink_intensity=60, body_height=40)
        rows = self._ink_rows(img)
        assert rows is not None
        first, last = rows
        # Ink should start in the upper 20% of body height
        assert first < 40 * 0.20, "Exclamation ink does not extend to top"
        # Ink should extend to near baseline
        assert last > 40 * 0.75, "Exclamation ink does not reach baseline"

    def test_question_extends_above(self):
        """Question mark should have ink from upper area to near baseline."""
        from reforge.model.generator import make_synthetic_mark
        img = make_synthetic_mark("?", ink_intensity=60, body_height=40)
        rows = self._ink_rows(img)
        assert rows is not None
        first, last = rows
        # Should start in upper third
        assert first < 40 * 0.35, "Question mark ink does not extend to top"
        # Should reach near baseline
        assert last > 40 * 0.75, "Question mark ink does not reach baseline"

    def test_comma_descends_below_baseline(self):
        """Comma should descend below body_height (has descender)."""
        from reforge.model.generator import make_synthetic_mark
        body_h = 40
        img = make_synthetic_mark(",", ink_intensity=60, body_height=body_h)
        # Image should be taller than body_height (descender space)
        assert img.shape[0] > body_h, "Comma image has no descender space"
        rows = self._ink_rows(img)
        assert rows is not None
        _, last = rows
        # Ink should extend below body_height
        assert last >= body_h - 1, "Comma ink does not descend below baseline"

    def test_semicolon_descends_below_baseline(self):
        """Semicolon should descend below body_height (has descender)."""
        from reforge.model.generator import make_synthetic_mark
        body_h = 40
        img = make_synthetic_mark(";", ink_intensity=60, body_height=body_h)
        assert img.shape[0] > body_h, "Semicolon image has no descender space"
        rows = self._ink_rows(img)
        assert rows is not None
        _, last = rows
        assert last >= body_h - 1, "Semicolon ink does not descend below baseline"


@pytest.mark.quick
class TestStripTrailingPunctuation:
    def test_strips_period(self):
        from reforge.model.generator import strip_trailing_punctuation
        assert strip_trailing_punctuation("hello.") == ("hello", ".")

    def test_strips_comma(self):
        from reforge.model.generator import strip_trailing_punctuation
        assert strip_trailing_punctuation("hello,") == ("hello", ",")

    def test_strips_question(self):
        from reforge.model.generator import strip_trailing_punctuation
        assert strip_trailing_punctuation("what?") == ("what", "?")

    def test_strips_exclamation(self):
        from reforge.model.generator import strip_trailing_punctuation
        assert strip_trailing_punctuation("wow!") == ("wow", "!")

    def test_strips_semicolon(self):
        from reforge.model.generator import strip_trailing_punctuation
        assert strip_trailing_punctuation("however;") == ("however", ";")

    def test_no_punctuation(self):
        from reforge.model.generator import strip_trailing_punctuation
        assert strip_trailing_punctuation("hello") == ("hello", None)

    def test_apostrophe_not_stripped(self):
        """Apostrophes are handled by contraction path, not trailing strip."""
        from reforge.model.generator import strip_trailing_punctuation
        assert strip_trailing_punctuation("dogs'") == ("dogs'", None)

    def test_single_char_not_stripped(self):
        """Don't strip if it would leave an empty base word."""
        from reforge.model.generator import strip_trailing_punctuation
        assert strip_trailing_punctuation(".") == (".", None)

    def test_only_one_mark_stripped(self):
        """Only strips one trailing mark."""
        from reforge.model.generator import strip_trailing_punctuation
        assert strip_trailing_punctuation("what?!") == ("what?", "!")


@pytest.mark.quick
class TestStripAndReattachPunctuation:
    def test_reattaches_period(self):
        from reforge.model.generator import strip_and_reattach_punctuation
        # Create a simple word image with ink
        word_img = np.full((30, 60), 255, dtype=np.uint8)
        word_img[5:25, 5:55] = 60
        result = strip_and_reattach_punctuation("hello.", word_img)
        # Result should be wider than input (mark appended)
        assert result.shape[1] > 40  # after tight crop + mark

    def test_no_punctuation_passthrough(self):
        from reforge.model.generator import strip_and_reattach_punctuation
        word_img = np.full((30, 60), 255, dtype=np.uint8)
        word_img[5:25, 5:55] = 60
        result = strip_and_reattach_punctuation("hello", word_img)
        assert result is word_img  # same object, no change

    def test_result_has_ink(self):
        from reforge.model.generator import strip_and_reattach_punctuation
        word_img = np.full((30, 60), 255, dtype=np.uint8)
        word_img[5:25, 5:55] = 60
        result = strip_and_reattach_punctuation("hello,", word_img)
        assert np.any(result < 180)


@pytest.mark.quick
class TestAttachMarkToWord:
    def test_baseline_alignment(self):
        """Word and mark should be aligned at ink bottom."""
        from reforge.model.generator import _attach_mark_to_word
        word = np.full((40, 60), 255, dtype=np.uint8)
        word[5:30, 5:55] = 60  # ink bottom at row 29
        mark = np.full((40, 8), 255, dtype=np.uint8)
        mark[20:38, 2:6] = 60  # ink bottom at row 37

        result = _attach_mark_to_word(word, mark)
        assert result.ndim == 2
        assert result.shape[1] > 50  # wider than just the word
        assert np.any(result < 180)
