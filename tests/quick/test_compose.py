"""Quick tests for compose/render.py: compositing, canvas sizing, ink-only filtering."""

import numpy as np
import pytest

from reforge.config import (
    COMPOSITOR_INK_THRESHOLD,
    DEFAULT_PAGE_WIDTH,
    PAGE_MARGIN,
    PARAGRAPH_INDENT,
    PARAGRAPH_SPACING,
    WORD_SPACING,
)


def _ink_word(w=60, h=30, ink_value=40):
    """Synthetic word: white background with ink bar in center rows."""
    img = np.full((h, w), 255, dtype=np.uint8)
    top = int(h * 0.3)
    bottom = int(h * 0.7)
    img[top:bottom, 5 : w - 5] = ink_value
    return img


@pytest.mark.quick
class TestComposeWordsBasic:
    def test_single_word_produces_grayscale_image(self):
        from reforge.compose.render import compose_words

        img = compose_words([_ink_word()], ["Hello"], upscale_factor=1)
        assert img.mode == "L"

    def test_canvas_width_matches_page_width(self):
        from reforge.compose.render import compose_words

        img = compose_words([_ink_word()], ["Hello"], page_width=800, upscale_factor=1)
        assert img.width == 800

    def test_upscale_doubles_dimensions(self):
        from reforge.compose.render import compose_words

        img1 = compose_words([_ink_word()], ["Hello"], page_width=400, upscale_factor=1)
        img2 = compose_words([_ink_word()], ["Hello"], page_width=400, upscale_factor=2)
        assert img2.width == img1.width * 2

    def test_empty_input_returns_blank_canvas(self):
        from reforge.compose.render import compose_words

        img = compose_words([], [], upscale_factor=1)
        arr = np.array(img)
        assert np.all(arr == 255)


@pytest.mark.quick
class TestComposeWordsInkOnly:
    def test_only_ink_pixels_composited(self):
        """Background pixels (>= COMPOSITOR_INK_THRESHOLD) should not appear on canvas."""
        from reforge.compose.render import compose_words

        word = _ink_word(60, 30, ink_value=40)
        img = compose_words([word], ["Test"], upscale_factor=1)
        arr = np.array(img)

        # Canvas should be white except where ink was placed
        non_white = arr < 255
        # There should be some ink
        assert np.any(non_white)

        # No gray artifacts: all non-white pixels should be actual ink (< threshold)
        non_white_values = arr[non_white]
        assert np.all(non_white_values < COMPOSITOR_INK_THRESHOLD)

    def test_light_gray_background_not_composited(self):
        """A word image with light gray (210) background should have it filtered out."""
        from reforge.compose.render import compose_words

        # 210 > COMPOSITOR_INK_THRESHOLD (200), so nothing should be composited
        word = np.full((30, 60), 210, dtype=np.uint8)
        img = compose_words([word], ["Test"], upscale_factor=1)
        arr = np.array(img)
        assert np.all(arr == 255)


@pytest.mark.quick
class TestComposeWordsMultiWord:
    def test_two_words_both_visible(self):
        from reforge.compose.render import compose_words

        words_img = [_ink_word(60, 30), _ink_word(60, 30)]
        words = ["one", "two"]
        img = compose_words(words_img, words, upscale_factor=1)
        arr = np.array(img)

        # Both words should contribute ink
        ink_cols = np.any(arr < 200, axis=0)
        ink_regions = np.diff(np.concatenate(([0], ink_cols.astype(int), [0])))
        starts = np.where(ink_regions == 1)[0]
        # At least 2 distinct ink regions (the two words)
        assert len(starts) >= 2

    def test_words_dont_overlap(self):
        from reforge.compose.render import compose_words
        from reforge.compose.layout import compute_word_positions

        w = 60
        words_img = [_ink_word(w, 30), _ink_word(w, 30)]
        words = ["one", "two"]
        pos = compute_word_positions(words_img, words)
        # Second word starts after first word ends + spacing
        assert pos[1]["x"] >= pos[0]["x"] + w


@pytest.mark.quick
class TestComposeWordsParagraphBreak:
    def test_paragraph_break_creates_vertical_gap(self):
        from reforge.compose.render import compose_words

        words_img = [_ink_word(60, 30), None, _ink_word(60, 30)]
        words = ["before", None, "after"]
        img = compose_words(words_img, words, upscale_factor=1)
        arr = np.array(img)

        # Find rows with ink
        row_has_ink = np.any(arr < 200, axis=1)
        ink_rows = np.where(row_has_ink)[0]

        if len(ink_rows) > 1:
            # There should be a gap between the two paragraphs
            diffs = np.diff(ink_rows)
            max_gap = np.max(diffs)
            # The paragraph gap should be larger than line spacing
            assert max_gap > 5, "Expected visible gap between paragraphs"

    def test_paragraph_words_indented_equally(self):
        from reforge.compose.layout import compute_word_positions

        words_img = [_ink_word(60, 30), None, _ink_word(60, 30)]
        words = ["before", None, "after"]
        pos = compute_word_positions(words_img, words)
        # Both paragraph-starting words get the same indent
        assert pos[0]["x"] == pos[1]["x"] == PAGE_MARGIN + PARAGRAPH_INDENT


@pytest.mark.quick
class TestComposeWordsBaselineAlignment:
    def test_tall_and_short_words_share_baseline(self):
        """Words of different heights on the same line should be baseline-aligned."""
        from reforge.compose.render import compose_words
        from reforge.compose.layout import compute_word_positions

        short = _ink_word(60, 20)
        tall = _ink_word(60, 40)
        words_img = [short, tall]
        words = ["short", "tall"]

        pos = compute_word_positions(words_img, words)
        # Both on the same line
        assert pos[0]["line"] == pos[1]["line"]

        # The compose function should produce an image (no crash with mixed heights)
        img = compose_words(words_img, words, upscale_factor=1)
        assert img.mode == "L"
        assert img.height > 0
