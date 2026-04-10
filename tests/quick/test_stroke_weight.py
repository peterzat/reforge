"""Quick tests for stroke weight harmonization."""

import numpy as np
import pytest


@pytest.mark.quick
class TestStrokeWeight:
    def test_harmonize_converges_medians(self):
        """After harmonization, ink medians are closer together."""
        from reforge.quality.harmonize import harmonize_stroke_weight, compute_ink_median

        # Two words with very different ink darkness
        dark = np.full((40, 100), 255, dtype=np.uint8)
        dark[10:30, 10:90] = 30  # very dark ink

        light = np.full((40, 100), 255, dtype=np.uint8)
        light[10:30, 10:90] = 120  # lighter ink

        before_spread = abs(compute_ink_median(dark) - compute_ink_median(light))

        result = harmonize_stroke_weight([dark, light])
        after_spread = abs(compute_ink_median(result[0]) - compute_ink_median(result[1]))

        assert after_spread < before_spread

    def test_consistent_words_unchanged(self):
        """Words with similar ink stay roughly unchanged."""
        from reforge.quality.harmonize import harmonize_stroke_weight

        word1 = np.full((40, 100), 255, dtype=np.uint8)
        word1[10:30, 10:90] = 60

        word2 = np.full((40, 100), 255, dtype=np.uint8)
        word2[10:30, 10:90] = 62

        result = harmonize_stroke_weight([word1, word2])
        # Should be nearly identical to input
        assert np.mean(np.abs(result[0].astype(int) - word1.astype(int))) < 5


@pytest.mark.quick
class TestStrokeWidthHarmonization:
    """Compliance tests for blended morphological stroke width normalization."""

    def test_no_global_gate(self):
        """Stroke width correction acts per-word, not gated on global variance."""
        from reforge.quality.harmonize import harmonize_stroke_width

        # One thick outlier among similar words: old global gate (std/mean < 15%)
        # would skip everything. New code should still adjust the outlier.
        normal1 = np.full((40, 100), 255, dtype=np.uint8)
        normal1[10:30, 10:90] = 60
        normal2 = np.full((40, 100), 255, dtype=np.uint8)
        normal2[10:30, 10:90] = 60

        # Make a thick-stroked word via dilation
        import cv2
        thick = np.full((40, 100), 255, dtype=np.uint8)
        thick[10:30, 10:90] = 60
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        ink_mask = (thick < 180).astype(np.uint8) * 255
        dilated = cv2.dilate(ink_mask, kernel, iterations=2)
        thick[dilated > 0] = 60

        result = harmonize_stroke_width([normal1, normal2, thick])

        # Thick word should be modified (blended toward eroded version)
        assert not np.array_equal(result[2], thick)
        # Normal words should be unchanged
        assert np.array_equal(result[0], normal1)

    def test_blended_not_destructive(self):
        """Blended erosion preserves most ink pixels, not hard removal."""
        from reforge.quality.harmonize import harmonize_stroke_width

        import cv2

        # Create a moderately thick word (just above threshold)
        normal = np.full((40, 100), 255, dtype=np.uint8)
        normal[10:30, 10:90] = 60

        thick = np.full((40, 100), 255, dtype=np.uint8)
        thick[10:30, 10:90] = 60
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        ink_mask = (thick < 180).astype(np.uint8) * 255
        dilated = cv2.dilate(ink_mask, kernel, iterations=1)
        thick[dilated > 0] = 60

        result = harmonize_stroke_width([normal, normal.copy(), thick])
        # Blended result should retain most ink (not erase entire edge layer)
        orig_ink = np.sum(thick < 180)
        result_ink = np.sum(result[2] < 180)
        # At least 90% of ink pixels preserved (blend, not hard removal)
        assert result_ink >= orig_ink * 0.90

    def test_near_median_unchanged(self):
        """Words within 15% of median stroke width are not modified."""
        from reforge.quality.harmonize import harmonize_stroke_width

        w1 = np.full((40, 100), 255, dtype=np.uint8)
        w1[10:30, 10:90] = 60
        w2 = np.full((40, 100), 255, dtype=np.uint8)
        w2[10:30, 12:88] = 60  # slightly narrower ink region

        result = harmonize_stroke_width([w1, w2])
        assert np.array_equal(result[0], w1)
        assert np.array_equal(result[1], w2)

    def test_thin_words_dilated(self):
        """Words significantly thinner than median get partially dilated."""
        from reforge.quality.harmonize import harmonize_stroke_width

        # Normal word: 3px-wide horizontal strokes
        normal = np.full((40, 100), 255, dtype=np.uint8)
        normal[14:17, 10:90] = 60  # 3px stroke
        normal[24:27, 10:90] = 60

        # Thin word: 1px-wide horizontal strokes
        thin = np.full((40, 100), 255, dtype=np.uint8)
        thin[15:16, 10:90] = 60  # 1px stroke
        thin[25:26, 10:90] = 60

        result = harmonize_stroke_width([normal, normal.copy(), thin])

        # Thin word should be modified (blended toward dilated version).
        # Blended dilation adds partially-dark pixels around thin strokes.
        assert not np.array_equal(result[2], thin)
        # Pixels adjacent to ink should now be darker than pure white
        assert np.mean(result[2]) < np.mean(thin)


@pytest.mark.quick
class TestHeightHarmonization:
    def test_outlier_scaled_down(self):
        """A word >120% median height gets scaled down."""
        from reforge.quality.harmonize import harmonize_heights

        normal1 = np.full((40, 100), 255, dtype=np.uint8)
        normal1[5:35, 10:90] = 60  # 30px ink height

        normal2 = np.full((40, 100), 255, dtype=np.uint8)
        normal2[5:35, 10:90] = 60

        tall = np.full((80, 100), 255, dtype=np.uint8)
        tall[5:75, 10:90] = 60  # 70px ink height, way over 120% of 30

        result = harmonize_heights([normal1, normal2, tall])
        # Tall word should be shorter now
        assert result[2].shape[0] < tall.shape[0]
        # Normal words unchanged
        assert result[0].shape[0] == normal1.shape[0]

    def test_scales_up_undersized_words(self):
        """Words below 80% of median height are scaled up."""
        from reforge.quality.harmonize import harmonize_heights

        big1 = np.full((60, 100), 255, dtype=np.uint8)
        big1[5:55, 10:90] = 60

        big2 = np.full((60, 100), 255, dtype=np.uint8)
        big2[5:55, 10:90] = 60

        small = np.full((30, 100), 255, dtype=np.uint8)
        small[5:25, 10:90] = 60

        result = harmonize_heights([big1, big2, small])
        # Small word (ink height 20, median ink height 50) should be scaled up
        assert result[2].shape[0] > small.shape[0]

    def test_near_median_words_unchanged(self):
        """Words within the harmonization band are not scaled."""
        from reforge.quality.harmonize import harmonize_heights

        # Two words with ink heights close to each other (both within 5% of median)
        w1 = np.full((50, 100), 255, dtype=np.uint8)
        w1[5:45, 10:90] = 60  # 40px ink height

        w2 = np.full((51, 100), 255, dtype=np.uint8)
        w2[5:46, 10:90] = 60  # 41px ink height

        result = harmonize_heights([w1, w2])
        # Both near median, neither should change
        assert result[0].shape[0] == w1.shape[0]
        assert result[1].shape[0] == w2.shape[0]
