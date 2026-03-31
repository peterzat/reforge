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
