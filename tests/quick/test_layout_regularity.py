"""Quick tests for layout regularity metric (D4)."""

import numpy as np
import pytest

pytestmark = pytest.mark.quick


def test_uniform_layout_scores_low():
    """D4: Perfectly uniform layout should score low (grid-like)."""
    from reforge.evaluate.visual import check_layout_regularity

    # 4 lines, 3 words each, perfectly uniform spacing and right edges
    positions = []
    for line in range(4):
        for col in range(3):
            positions.append({
                "x": 50 + col * 100,
                "y": line * 50,
                "width": 80,
                "height": 30,
                "line": line,
            })

    score = check_layout_regularity(positions)
    assert score < 0.5, f"Uniform layout should score < 0.5, got {score:.3f}"


def test_varied_layout_scores_higher():
    """D4: Layout with natural variation should score higher."""
    from reforge.evaluate.visual import check_layout_regularity

    rng = np.random.RandomState(42)
    positions = []
    for line in range(4):
        x = 50 + rng.randint(-3, 4)
        n_words = rng.choice([2, 3, 4])
        for col in range(n_words):
            w = 60 + rng.randint(-10, 20)
            positions.append({
                "x": x,
                "y": line * 50,
                "width": w,
                "height": 30,
                "line": line,
            })
            x += w + 16 + rng.randint(-4, 5)

    score = check_layout_regularity(positions)
    assert score > 0.3, f"Varied layout should score > 0.3, got {score:.3f}"
