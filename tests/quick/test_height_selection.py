"""Quick tests for height-aware candidate selection scoring."""

import numpy as np
import pytest

from reforge.config import SHORT_WORD_HEIGHT_TARGET


def _word_img(ink_height, canvas_height=80, width=256):
    """Synthetic word image with specified ink height centered on canvas."""
    img = np.full((canvas_height, width), 255, dtype=np.uint8)
    top = (canvas_height - ink_height) // 2
    img[top:top + ink_height, 10:width - 10] = 60
    return img


@pytest.mark.quick
class TestHeightConsistencyScore:
    def test_target_height_scores_highest(self):
        """A candidate at the target height scores higher than one at full canvas."""
        from reforge.quality.score import _height_consistency_score

        target = int(SHORT_WORD_HEIGHT_TARGET * 1.08)  # 28px for 5-char word
        at_target = _word_img(target)
        at_canvas = _word_img(64)  # full canvas fill

        score_target = _height_consistency_score(at_target, word_len=5)
        score_canvas = _height_consistency_score(at_canvas, word_len=5)
        assert score_target > score_canvas

    def test_canvas_fill_penalized_heavily(self):
        """A word filling the full canvas (60+ px) should score low."""
        from reforge.quality.score import _height_consistency_score

        full = _word_img(60)
        score = _height_consistency_score(full, word_len=5)
        # 60px vs 28px target = 114% deviation, should score very low
        assert score < 0.2

    def test_near_target_scores_high(self):
        """A word within 20% of target should score well."""
        from reforge.quality.score import _height_consistency_score

        target = int(SHORT_WORD_HEIGHT_TARGET * 1.08)
        near = _word_img(target + 3)  # ~10% over target
        score = _height_consistency_score(near, word_len=5)
        assert score > 0.8

    def test_short_word_uses_lower_target(self):
        """1-2 char words use SHORT_WORD_HEIGHT_TARGET (26px)."""
        from reforge.quality.score import _height_consistency_score

        at_26 = _word_img(SHORT_WORD_HEIGHT_TARGET)
        score = _height_consistency_score(at_26, word_len=1)
        assert score > 0.9

    def test_word_len_zero_uses_legacy(self):
        """word_len=0 uses canvas coverage ratio (legacy behavior)."""
        from reforge.quality.score import _height_consistency_score

        # Canvas coverage 50% = within 0.3-0.8 range = score 1.0
        img = _word_img(40, canvas_height=80)
        score = _height_consistency_score(img, word_len=0)
        assert score == 1.0


@pytest.mark.quick
class TestHeightAwareSelection:
    def test_prefers_moderate_height_over_canvas_fill(self):
        """quality_score with word_len prefers moderate height candidate."""
        from reforge.quality.score import quality_score

        moderate = _word_img(30)  # near 28px target
        full = _word_img(60)     # canvas fill

        # Both have same background, contrast, etc.; height is the differentiator
        score_mod = quality_score(moderate, word_len=5)
        score_full = quality_score(full, word_len=5)
        assert score_mod > score_full

    def test_no_word_len_no_height_preference(self):
        """Without word_len, height scoring uses legacy canvas coverage."""
        from reforge.quality.score import quality_score

        moderate = _word_img(30)
        full = _word_img(60)

        # Legacy scoring: both within 0.3-0.8 range, should score similarly
        score_mod = quality_score(moderate, word_len=0)
        score_full = quality_score(full, word_len=0)
        # Height_consistency might differ slightly but shouldn't dominate
        assert abs(score_mod - score_full) < 0.15
