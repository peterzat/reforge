"""Quick tests validating Tier 1 (word-pair consistency) metric computation on synthetic images.

Each test corresponds to a Tier 1 acceptance criterion from the spec,
verifying harmonization and consistency metrics work correctly.
No GPU required.
"""

import numpy as np
import pytest


def _make_word(h=40, w=100, ink_val=60):
    """Create a synthetic word image."""
    img = np.full((h, w), 255, dtype=np.uint8)
    img[10 : h - 10, 10 : w - 10] = ink_val
    return img


@pytest.mark.quick
class TestStrokeWeightAfterHarmonization:
    """AC: Two adjacent words have stroke weight consistency > 0.7 after harmonization."""

    def test_inconsistent_pair_improved_above_threshold(self):
        from reforge.evaluate.visual import check_stroke_weight_consistency
        from reforge.quality.harmonize import harmonize_stroke_weight

        # Two words with different ink darkness
        word_a = _make_word(ink_val=40)
        word_b = _make_word(ink_val=100)

        before = check_stroke_weight_consistency([word_a, word_b])

        harmonized = harmonize_stroke_weight([word_a, word_b])
        after = check_stroke_weight_consistency(harmonized)

        assert after >= 0.7, (
            f"Stroke weight consistency after harmonization ({after:.3f}) "
            f"should be >= 0.7 (before: {before:.3f})"
        )

    def test_five_word_sequence_above_threshold(self):
        from reforge.evaluate.visual import check_stroke_weight_consistency
        from reforge.quality.harmonize import harmonize_stroke_weight

        words = [_make_word(ink_val=v) for v in [40, 55, 70, 85, 100]]
        harmonized = harmonize_stroke_weight(words)
        score = check_stroke_weight_consistency(harmonized)
        assert score > 0.7, f"Five-word stroke consistency ({score:.3f}) should be > 0.7"


@pytest.mark.quick
class TestHeightRatioAfterHarmonization:
    """AC: Two adjacent words have height ratio > 0.6 after font normalization
    and harmonization."""

    def test_varied_heights_improved_above_threshold(self):
        from reforge.evaluate.visual import check_word_height_ratio
        from reforge.quality.harmonize import harmonize_heights

        # Three words: harmonize_heights scales outliers >120% of median
        w1 = np.full((40, 100), 255, dtype=np.uint8)
        w1[5:35, 10:90] = 60  # 30px ink height

        w2 = np.full((45, 100), 255, dtype=np.uint8)
        w2[5:40, 10:90] = 60  # 35px ink height

        w3 = np.full((55, 100), 255, dtype=np.uint8)
        w3[5:50, 10:90] = 60  # 45px ink height (outlier)

        harmonized = harmonize_heights([w1, w2, w3])
        score = check_word_height_ratio(harmonized)
        assert score > 0.6, f"Height ratio after harmonization ({score:.3f}) should be > 0.6"

    def test_three_words_after_full_harmonization(self):
        """Words with moderate height variance score > 0.6 after harmonization."""
        from reforge.evaluate.visual import check_word_height_ratio
        from reforge.quality.harmonize import harmonize_words

        # Heights within a realistic range (25, 28, 34px ink)
        w1 = np.full((40, 100), 255, dtype=np.uint8)
        w1[8:33, 10:90] = 60  # 25px ink

        w2 = np.full((40, 100), 255, dtype=np.uint8)
        w2[6:34, 10:90] = 60  # 28px ink

        w3 = np.full((45, 100), 255, dtype=np.uint8)
        w3[5:39, 10:90] = 60  # 34px ink

        harmonized = harmonize_words([w1, w2, w3])
        score = check_word_height_ratio(harmonized)
        assert score > 0.6, f"Three-word height ratio ({score:.3f}) should be > 0.6"


@pytest.mark.quick
class TestInkDarknessVariation:
    """AC: Ink darkness varies by less than 25 brightness levels between any two
    words in a 5-word sequence after harmonization."""

    def test_darkness_within_25_levels_after_harmonization(self):
        from reforge.quality.harmonize import compute_ink_median, harmonize_stroke_weight

        # Five words with moderate ink darkness variation
        words = [_make_word(ink_val=v) for v in [50, 65, 80, 95, 110]]

        harmonized = harmonize_stroke_weight(words)
        medians = [compute_ink_median(w) for w in harmonized]

        max_diff = max(medians) - min(medians)
        assert max_diff < 25, (
            f"Max ink darkness difference ({max_diff:.1f}) should be < 25 "
            f"after harmonization (medians: {[f'{m:.1f}' for m in medians]})"
        )

    def test_already_consistent_stays_within_threshold(self):
        from reforge.quality.harmonize import compute_ink_median, harmonize_stroke_weight

        words = [_make_word(ink_val=v) for v in [58, 60, 62, 64, 66]]
        harmonized = harmonize_stroke_weight(words)
        medians = [compute_ink_median(w) for w in harmonized]
        max_diff = max(medians) - min(medians)
        assert max_diff < 25
