"""Quick tests for quality scoring."""

import numpy as np
import pytest


@pytest.mark.quick
class TestQualityScore:
    def test_score_range(self):
        """Quality score is in [0, 1]."""
        from reforge.quality.score import quality_score
        # Clean word-like image
        img = np.full((64, 256), 255, dtype=np.uint8)
        img[20:44, 30:220] = 40  # dark ink
        score = quality_score(img)
        assert 0.0 <= score <= 1.0

    def test_good_image_scores_higher(self):
        """A clean image with good contrast scores higher than a noisy one."""
        from reforge.quality.score import quality_score

        # Good: clean background, clear ink
        good = np.full((64, 256), 255, dtype=np.uint8)
        good[20:44, 30:220] = 30

        # Bad: gray everything
        bad = np.full((64, 256), 160, dtype=np.uint8)

        assert quality_score(good) > quality_score(bad)

    def test_empty_image(self):
        """All-white image gets a low score."""
        from reforge.quality.score import quality_score
        white = np.full((64, 256), 255, dtype=np.uint8)
        score = quality_score(white)
        assert score < 0.5
