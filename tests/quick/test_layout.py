"""Quick tests for compose/layout.py: line wrapping, paragraph breaks, positioning."""

import numpy as np
import pytest

from reforge.config import (
    DEFAULT_PAGE_WIDTH,
    LINE_SPACING,
    MAX_PAGE_WIDTH,
    MIN_PAGE_WIDTH,
    PAGE_MARGIN,
    PARAGRAPH_INDENT,
    PARAGRAPH_SPACING,
    TARGET_ASPECT_MAX,
    TARGET_ASPECT_MIN,
    WORD_SPACING,
)
from reforge.compose.layout import (
    compute_margins,
    compute_page_width,
    compute_word_positions,
    detect_baseline,
)


def _fake_word(w=60, h=30):
    """Create a synthetic word image (white background, dark horizontal bar in middle)."""
    img = np.full((h, w), 255, dtype=np.uint8)
    # Draw ink in the middle 40% of rows
    top = int(h * 0.3)
    bottom = int(h * 0.7)
    img[top:bottom, 5 : w - 5] = 40
    return img


@pytest.mark.quick
class TestComputeWordPositionsSingleLine:
    def test_single_word(self):
        imgs = [_fake_word(60, 30)]
        words = ["Hello"]
        pos = compute_word_positions(imgs, words)
        assert len(pos) == 1
        # First word gets paragraph indent
        assert pos[0]["x"] == PAGE_MARGIN + PARAGRAPH_INDENT
        assert pos[0]["y"] == 0
        assert pos[0]["line"] == 0

    def test_three_words_fit_on_one_line(self):
        imgs = [_fake_word(60, 30) for _ in range(3)]
        words = ["one", "two", "three"]
        pos = compute_word_positions(imgs, words)
        assert len(pos) == 3
        # All on line 0
        assert all(p["line"] == 0 for p in pos)
        # x positions increase
        assert pos[0]["x"] < pos[1]["x"] < pos[2]["x"]
        # Spacing between words
        expected_x1 = PAGE_MARGIN + PARAGRAPH_INDENT + 60 + WORD_SPACING
        assert pos[1]["x"] == expected_x1

    def test_word_spacing_correct(self):
        w = 80
        imgs = [_fake_word(w, 30) for _ in range(2)]
        words = ["aa", "bb"]
        pos = compute_word_positions(imgs, words)
        gap = pos[1]["x"] - (pos[0]["x"] + w)
        assert gap == WORD_SPACING


@pytest.mark.quick
class TestComputeWordPositionsLineWrap:
    def test_wraps_when_exceeding_page_width(self):
        # First line usable = page - 2*margin - indent (paragraph start)
        first_line = DEFAULT_PAGE_WIDTH - 2 * PAGE_MARGIN - PARAGRAPH_INDENT
        # Pick width so 2 words fit but 3 don't
        w = (first_line - WORD_SPACING) // 2
        imgs = [_fake_word(w, 30) for _ in range(3)]
        words = ["aaa", "bbb", "ccc"]
        pos = compute_word_positions(imgs, words)
        assert len(pos) == 3
        assert pos[0]["line"] == 0
        assert pos[1]["line"] == 0
        assert pos[2]["line"] == 1

    def test_wrapped_line_starts_at_margin(self):
        first_line = DEFAULT_PAGE_WIDTH - 2 * PAGE_MARGIN - PARAGRAPH_INDENT
        w = (first_line - WORD_SPACING) // 2
        imgs = [_fake_word(w, 30) for _ in range(3)]
        words = ["aaa", "bbb", "ccc"]
        pos = compute_word_positions(imgs, words)
        # Wrapped line starts at margin (no indent, since not paragraph start)
        assert pos[2]["x"] == PAGE_MARGIN

    def test_y_advances_by_line_height_plus_spacing(self):
        first_line = DEFAULT_PAGE_WIDTH - 2 * PAGE_MARGIN - PARAGRAPH_INDENT
        w = (first_line - WORD_SPACING) // 2
        h = 30
        imgs = [_fake_word(w, h) for _ in range(3)]
        words = ["aaa", "bbb", "ccc"]
        pos = compute_word_positions(imgs, words)
        assert pos[2]["y"] == h + LINE_SPACING

    def test_many_words_wrap_multiple_lines(self):
        # 100px words, ~7 per line on 800px page
        imgs = [_fake_word(100, 30) for _ in range(20)]
        words = [f"w{i}" for i in range(20)]
        pos = compute_word_positions(imgs, words)
        lines = set(p["line"] for p in pos)
        assert len(lines) >= 3


@pytest.mark.quick
class TestComputeWordPositionsParagraphs:
    def test_paragraph_break_advances_y(self):
        imgs = [_fake_word(60, 30), None, _fake_word(60, 30)]
        words = ["before", None, "after"]
        pos = compute_word_positions(imgs, words)
        assert len(pos) == 2
        assert pos[0]["y"] == 0
        assert pos[1]["y"] == 30 + PARAGRAPH_SPACING

    def test_paragraph_break_adds_indent(self):
        imgs = [_fake_word(60, 30), None, _fake_word(60, 30)]
        words = ["before", None, "after"]
        pos = compute_word_positions(imgs, words)
        assert pos[1]["x"] == PAGE_MARGIN + PARAGRAPH_INDENT

    def test_multiple_paragraphs(self):
        imgs = [_fake_word(60, 30), None, _fake_word(60, 30), None, _fake_word(60, 30)]
        words = ["p1", None, "p2", None, "p3"]
        pos = compute_word_positions(imgs, words)
        assert len(pos) == 3
        # Each paragraph on a different line
        assert pos[0]["line"] != pos[1]["line"]
        assert pos[1]["line"] != pos[2]["line"]
        # All indented
        for p in pos:
            assert p["x"] == PAGE_MARGIN + PARAGRAPH_INDENT

    def test_empty_input(self):
        pos = compute_word_positions([], [])
        assert pos == []


@pytest.mark.quick
class TestComputePageWidth:
    def test_few_words_narrow_page(self):
        """3 short words should produce a narrow page."""
        pw = compute_page_width(word_count=3, avg_word_width=60, avg_word_height=30)
        assert pw <= DEFAULT_PAGE_WIDTH
        assert pw >= MIN_PAGE_WIDTH

    def test_many_words_wider_page(self):
        """43 words should produce a wider page, but in bounds."""
        pw = compute_page_width(word_count=43, avg_word_width=60, avg_word_height=30)
        assert MIN_PAGE_WIDTH <= pw <= MAX_PAGE_WIDTH

    def test_aspect_ratio_in_range(self):
        """Computed page width should target near-square output for typical text."""
        pw = compute_page_width(word_count=20, avg_word_width=60, avg_word_height=30)
        # Estimate the resulting aspect ratio
        total_w = 20 * 60 + 19 * WORD_SPACING
        margin_h = int(pw * 0.06)
        usable = pw - 2 * margin_h
        n_lines = max(1, int(np.ceil(total_w / usable)))
        est_h = n_lines * (30 + LINE_SPACING)
        ratio = pw / max(1, est_h)
        # Should be reasonably close to the target range
        assert 0.5 <= ratio <= 2.0

    def test_empty_input(self):
        """Zero words returns default."""
        pw = compute_page_width(word_count=0, avg_word_width=60, avg_word_height=30)
        assert pw == DEFAULT_PAGE_WIDTH


@pytest.mark.quick
class TestComputeMargins:
    def test_margins_in_range(self):
        """Margins should be proportional to dimensions."""
        mh, mv = compute_margins(800, 600)
        assert 800 * 0.05 <= mh <= 800 * 0.08
        assert 600 * 0.03 <= mv <= 600 * 0.05

    def test_small_page(self):
        mh, mv = compute_margins(300, 200)
        assert mh >= int(300 * 0.05)
        assert mv >= int(200 * 0.03)


@pytest.mark.quick
class TestDetectBaseline:
    def test_no_ink_returns_bottom(self):
        img = np.full((64, 256), 255, dtype=np.uint8)
        bl = detect_baseline(img)
        assert bl == 63

    def test_horizontal_bar_baseline_at_bar_bottom(self):
        img = np.full((64, 256), 255, dtype=np.uint8)
        # Ink in rows 10-30
        img[10:30, 20:200] = 40
        bl = detect_baseline(img)
        # Baseline should be near the bottom of the ink (around row 29)
        assert 25 <= bl <= 35

    def test_descender_baseline_above_tail(self):
        img = np.full((64, 256), 255, dtype=np.uint8)
        # Main body: rows 10-35, full width
        img[10:35, 20:200] = 40
        # Descender: rows 35-55, narrow column (thin tail)
        img[35:55, 90:100] = 40
        bl = detect_baseline(img)
        # Baseline should be near row 35 (above the descender), not at 55
        assert bl < 45
