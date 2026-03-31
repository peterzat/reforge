"""Quick tests for CV evaluation functions against synthetic images."""

import numpy as np
import pytest


@pytest.mark.quick
class TestInkContrast:
    def test_high_contrast(self):
        """Dark ink on white background scores high."""
        from reforge.evaluate.visual import check_ink_contrast
        img = np.full((64, 256), 255, dtype=np.uint8)
        img[20:44, 30:220] = 20
        score = check_ink_contrast(img)
        assert score > 0.8

    def test_low_contrast(self):
        """Gray ink on gray background scores low."""
        from reforge.evaluate.visual import check_ink_contrast
        img = np.full((64, 256), 210, dtype=np.uint8)
        img[20:44, 30:220] = 180
        score = check_ink_contrast(img)
        assert score < 0.3


@pytest.mark.quick
class TestStrokeWeightConsistency:
    def test_consistent_words(self):
        """Words with same ink darkness score high."""
        from reforge.evaluate.visual import check_stroke_weight_consistency
        words = []
        for _ in range(5):
            img = np.full((40, 100), 255, dtype=np.uint8)
            img[10:30, 10:90] = 60
            words.append(img)
        score = check_stroke_weight_consistency(words)
        assert score > 0.9

    def test_inconsistent_words(self):
        """Words with varying ink darkness score lower."""
        from reforge.evaluate.visual import check_stroke_weight_consistency
        words = []
        for val in [20, 60, 100, 140, 170]:
            img = np.full((40, 100), 255, dtype=np.uint8)
            img[10:30, 10:90] = val
            words.append(img)
        score = check_stroke_weight_consistency(words)
        assert score < 0.5


@pytest.mark.quick
class TestWordHeightRatio:
    def test_uniform_heights(self):
        """Words with same height score 1.0."""
        from reforge.evaluate.visual import check_word_height_ratio
        words = []
        for _ in range(5):
            img = np.full((40, 100), 255, dtype=np.uint8)
            img[10:30, 10:90] = 60
            words.append(img)
        score = check_word_height_ratio(words)
        assert score == 1.0

    def test_varied_heights(self):
        """Words with very different heights score lower."""
        from reforge.evaluate.visual import check_word_height_ratio
        small = np.full((20, 100), 255, dtype=np.uint8)
        small[5:15, 10:90] = 60  # 10px height
        big = np.full((80, 100), 255, dtype=np.uint8)
        big[5:75, 10:90] = 60  # 70px height
        score = check_word_height_ratio([small, big])
        assert score < 0.5


@pytest.mark.quick
class TestBackgroundCleanliness:
    def test_clean_background(self):
        """White background with dark ink is clean."""
        from reforge.evaluate.visual import check_background_cleanliness
        img = np.full((64, 256), 255, dtype=np.uint8)
        img[20:44, 30:220] = 30
        score = check_background_cleanliness(img)
        assert score > 0.5

    def test_noisy_background(self):
        """Gray background scores low."""
        from reforge.evaluate.visual import check_background_cleanliness
        img = np.full((64, 256), 180, dtype=np.uint8)
        score = check_background_cleanliness(img)
        assert score < 0.5


@pytest.mark.quick
class TestOverallQuality:
    def test_returns_dict(self):
        """overall_quality_score returns dict with expected keys."""
        from reforge.evaluate.visual import overall_quality_score
        img = np.full((64, 256), 255, dtype=np.uint8)
        img[20:44, 30:220] = 30
        result = overall_quality_score(img)
        assert isinstance(result, dict)
        assert "overall" in result
        assert "gray_boxes" in result
        assert "ink_contrast" in result
