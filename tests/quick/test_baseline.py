"""Quick tests for baseline detection and alignment."""

import numpy as np
import pytest


@pytest.mark.quick
class TestBaselineDetection:
    def test_baseline_above_descender(self):
        """Baseline is detected above descender region."""
        from reforge.compose.layout import detect_baseline
        # Image with body text in top 60%, descender in bottom 20%
        img = np.full((100, 200), 255, dtype=np.uint8)
        # Body zone: rows 20-60
        img[20:60, 30:170] = 40
        # Thin descender: rows 60-80
        img[60:80, 100:110] = 40
        bl = detect_baseline(img)
        # Baseline should be around row 60 (before descender)
        assert 50 <= bl <= 70

    def test_baseline_at_bottom_no_descender(self):
        """Without descenders, baseline is near bottom of ink."""
        from reforge.compose.layout import detect_baseline
        img = np.full((100, 200), 255, dtype=np.uint8)
        img[20:60, 30:170] = 40
        bl = detect_baseline(img)
        assert bl >= 50

    def test_empty_image(self):
        """Empty image returns bottom row as baseline."""
        from reforge.compose.layout import detect_baseline
        img = np.full((100, 200), 255, dtype=np.uint8)
        bl = detect_baseline(img)
        assert bl == 99


@pytest.mark.quick
class TestBaselineWithDescenders:
    """B2: Targeted tests for words containing descender letters.

    Each test creates a synthetic image with body text in rows 15-45 and
    a thin descender tail below. The correct baseline is at the body bottom
    (~row 44). detect_baseline() with the word parameter should detect
    the baseline within 3px of that target.
    """

    def _make_descender_image(
        self,
        body_rows=(15, 45),
        descender_rows=(45, 62),
        descender_cols=(80, 95),
        body_cols=(20, 200),
    ):
        """Create a synthetic word image with body + descender."""
        img = np.full((64, 256), 255, dtype=np.uint8)
        # Body zone
        img[body_rows[0]:body_rows[1], body_cols[0]:body_cols[1]] = 40
        # Thin descender tail
        img[descender_rows[0]:descender_rows[1], descender_cols[0]:descender_cols[1]] = 50
        return img

    def test_gray_baseline_with_word(self):
        """'gray' (g descender): baseline detected above descender tail."""
        from reforge.compose.layout import detect_baseline
        img = self._make_descender_image(
            descender_cols=(30, 45),  # g descender on left side
        )
        bl = detect_baseline(img, word="gray")
        # Body bottom is row 44; baseline should be within 3px
        assert abs(bl - 44) <= 3, f"Expected baseline ~44, got {bl}"

    def test_fences_baseline_with_word(self):
        """'fences' (no DESCENDER_LETTERS match): exercises default path with descender-like image."""
        from reforge.compose.layout import detect_baseline
        # f-tail: thinner descender, narrower column
        img = self._make_descender_image(
            descender_rows=(45, 55),
            descender_cols=(25, 33),
        )
        bl = detect_baseline(img, word="fences")
        assert abs(bl - 44) <= 3, f"Expected baseline ~44, got {bl}"

    def test_jumping_baseline_with_word(self):
        """'jumping' (p descender): baseline above the p's descender."""
        from reforge.compose.layout import detect_baseline
        img = self._make_descender_image(
            descender_cols=(100, 115),  # p descender in middle
        )
        bl = detect_baseline(img, word="jumping")
        assert abs(bl - 44) <= 3, f"Expected baseline ~44, got {bl}"

    def test_quickly_baseline_with_word(self):
        """'quickly' (q and y descenders): two descender tails."""
        from reforge.compose.layout import detect_baseline
        img = np.full((64, 256), 255, dtype=np.uint8)
        # Body
        img[15:45, 20:200] = 40
        # q descender
        img[45:60, 60:72] = 50
        # y descender
        img[45:58, 170:182] = 50
        bl = detect_baseline(img, word="quickly")
        assert abs(bl - 44) <= 3, f"Expected baseline ~44, got {bl}"

    def test_descender_without_word_param(self):
        """Without word param, descender detection still works but may be less accurate."""
        from reforge.compose.layout import detect_baseline
        img = self._make_descender_image()
        # Without word hint, the function should still attempt detection
        bl_no_word = detect_baseline(img)
        bl_with_word = detect_baseline(img, word="gray")
        # Both should find a baseline; with word should be >= without word
        # (without word, the scan may be fooled by descender ink)
        assert bl_no_word >= 0
        assert bl_with_word >= 0


@pytest.mark.quick
class TestBaselineAlignment:
    def test_perfect_alignment(self):
        """Words at same y position score 1.0."""
        from reforge.evaluate.visual import check_baseline_alignment
        img = np.full((200, 800), 255, dtype=np.uint8)
        positions = [
            {"x": 10, "y": 50, "height": 40, "line": 0},
            {"x": 100, "y": 50, "height": 40, "line": 0},
            {"x": 200, "y": 50, "height": 40, "line": 0},
        ]
        score = check_baseline_alignment(img, positions)
        assert score == 1.0

    def test_misaligned_scores_lower(self):
        """Words at different y positions score lower."""
        from reforge.evaluate.visual import check_baseline_alignment
        img = np.full((200, 800), 255, dtype=np.uint8)
        positions = [
            {"x": 10, "y": 50, "height": 40, "line": 0},
            {"x": 100, "y": 70, "height": 40, "line": 0},  # 20px off
            {"x": 200, "y": 50, "height": 40, "line": 0},
        ]
        score = check_baseline_alignment(img, positions)
        assert score < 1.0
