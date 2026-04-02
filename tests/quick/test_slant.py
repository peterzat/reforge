"""Quick tests for slant consistency metric (C4)."""

import numpy as np
import pytest

pytestmark = pytest.mark.quick


def _make_slanted_word(height=50, width=80, slant_px=0):
    """Create a synthetic word image with a vertical ink column.

    slant_px: horizontal offset of ink centroid from top to bottom.
    Positive = rightward lean, negative = leftward.
    """
    img = np.full((height, width), 255, dtype=np.uint8)
    center_x = width // 2
    for row in range(10, 40):
        # Linear interpolation of x offset across rows
        frac = (row - 10) / 30.0
        offset = int(slant_px * frac)
        col_start = max(0, center_x + offset - 3)
        col_end = min(width, center_x + offset + 3)
        img[row, col_start:col_end] = 60
    return img


def test_slant_consistency_uniform():
    """C4: Words with identical slant should score near 1.0."""
    from reforge.evaluate.visual import check_slant_consistency

    words = [_make_slanted_word(slant_px=-5) for _ in range(5)]
    score = check_slant_consistency(words)
    assert score >= 0.95, f"Uniform slant should score >= 0.95, got {score:.3f}"


def test_slant_consistency_mixed():
    """C4: Words with varied slant should score lower."""
    from reforge.evaluate.visual import check_slant_consistency

    words = [
        _make_slanted_word(slant_px=-10),
        _make_slanted_word(slant_px=10),
        _make_slanted_word(slant_px=-5),
        _make_slanted_word(slant_px=8),
        _make_slanted_word(slant_px=0),
    ]
    score = check_slant_consistency(words)
    assert score < 0.85, f"Mixed slant should score < 0.85, got {score:.3f}"


def test_slant_consistency_single_word():
    """C4: Single word should return 1.0."""
    from reforge.evaluate.visual import check_slant_consistency

    score = check_slant_consistency([_make_slanted_word()])
    assert score == 1.0
