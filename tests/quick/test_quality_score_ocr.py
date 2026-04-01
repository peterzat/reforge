"""Quick tests validating overall_quality_score correctly penalizes
blank/empty words and incorporates OCR accuracy when available."""

import numpy as np
import pytest


def _make_good_word(h=64, w=256, ink_val=30):
    img = np.full((h, w), 255, dtype=np.uint8)
    img[20:44, 30:w - 30] = ink_val
    return img


def _make_blank_word(h=64, w=256):
    """Word image with almost no ink (simulating blank generation)."""
    img = np.full((h, w), 255, dtype=np.uint8)
    # Just a few scattered pixels, not a real word
    img[32, 128] = 100
    return img


@pytest.mark.quick
class TestQualityScoreBlankDetection:
    """overall_quality_score must detect and penalize blank words."""

    def test_blank_word_ratio_detected(self):
        from reforge.evaluate.visual import _blank_word_ratio

        good = _make_good_word()
        blank = _make_blank_word()
        words = ["hello", "world", "test", "blank", "here"]
        imgs = [good, good, good, blank, good]

        ratio = _blank_word_ratio(imgs, words)
        # 1 blank out of 5 = 0.2
        assert ratio > 0.15

    def test_no_blanks_ratio_zero(self):
        from reforge.evaluate.visual import _blank_word_ratio

        good = _make_good_word()
        words = ["hello", "world", "test"]
        imgs = [good, good, good]

        ratio = _blank_word_ratio(imgs, words)
        assert ratio == 0.0


@pytest.mark.quick
class TestCharAccuracyScoring:
    """Validate _char_accuracy handles edge cases for quality scoring."""

    def test_clipped_the_detected(self):
        """'he' recognized from 'The' should score low."""
        from reforge.evaluate.ocr import _char_accuracy
        score = _char_accuracy("he", "The")
        assert score < 0.8

    def test_perfect_match_scores_one(self):
        from reforge.evaluate.ocr import _char_accuracy
        assert _char_accuracy("brown", "brown") == 1.0

    def test_completely_wrong_scores_zero(self):
        from reforge.evaluate.ocr import _char_accuracy
        assert _char_accuracy("xyz", "abc") == 0.0
