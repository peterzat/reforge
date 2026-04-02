"""Quick tests for the ruled-line vertical positioning model (F1/F2/F3/F5)."""

import numpy as np
import pytest

pytestmark = pytest.mark.quick


def _make_word_image(height=40, width=80, ink_top=5, ink_bottom=35, descender_bottom=None):
    """Create a synthetic word image with ink in specified rows.

    If descender_bottom is set, add thin ink below the main body to simulate
    a descender (e.g., 'g', 'y'). Descender is narrow (< 15% of width)
    so baseline detection identifies it correctly.
    """
    img = np.full((height, width), 255, dtype=np.uint8)
    # Main body ink
    img[ink_top:ink_bottom, 10:70] = 60
    # Descender ink (narrow: < 15% of width so density drops below threshold)
    if descender_bottom is not None:
        img[ink_bottom:descender_bottom, 35:43] = 80
    return img


def test_descender_detection():
    """F2: _has_descender correctly identifies descending vs non-descending words."""
    from reforge.compose.render import _has_descender

    # Non-descending word: ink ends at baseline
    no_desc = _make_word_image(ink_top=5, ink_bottom=35)
    baseline = 34  # last ink row
    assert not _has_descender(no_desc, baseline)

    # Descending word: ink extends well below baseline
    with_desc = _make_word_image(ink_top=5, ink_bottom=30, descender_bottom=40)
    baseline_desc = 29  # body ends at row 29
    assert _has_descender(with_desc, baseline_desc)


def test_ruled_line_non_descending_words_same_y():
    """F5: Non-descending words on the same line land at the same y-coordinate."""
    from reforge.compose.render import compose_words

    # Three words, all non-descending, slightly different heights
    w1 = _make_word_image(height=40, ink_top=5, ink_bottom=35)
    w2 = _make_word_image(height=38, ink_top=3, ink_bottom=33)
    w3 = _make_word_image(height=42, ink_top=7, ink_bottom=37)

    imgs = [w1, w2, w3]
    words = ["test", "word", "here"]
    _, positions = compose_words(imgs, words, page_width=600, upscale_factor=1, return_positions=True)

    # All three should be on line 0
    assert all(p["line"] == 0 for p in positions)

    # Bottom y-coordinates should be within 2px of each other (jitter is +/- 1px)
    bottoms = [p["y"] + p["height"] for p in positions]
    spread = max(bottoms) - min(bottoms)
    assert spread <= 6, f"Bottom spread {spread}px exceeds 6px tolerance"


def test_ruled_line_descending_word_extends_below():
    """F5: A descending word's body aligns with non-descending words,
    with the descender extending below the ruled line."""
    from reforge.compose.render import compose_words

    # Non-descending word
    w1 = _make_word_image(height=40, ink_top=5, ink_bottom=35)
    # Descending word (ink extends below body)
    w2 = _make_word_image(height=50, ink_top=5, ink_bottom=35, descender_bottom=48)

    imgs = [w1, w2]
    words = ["test", "gypy"]
    _, positions = compose_words(imgs, words, page_width=600, upscale_factor=1, return_positions=True)

    # Both on line 0
    assert all(p["line"] == 0 for p in positions)

    # The descending word's total extent should be taller (descender below)
    p1, p2 = positions[0], positions[1]
    bottom1 = p1["y"] + p1["height"]
    bottom2 = p2["y"] + p2["height"]
    # Descending word should extend further down
    assert bottom2 > bottom1, "Descending word should extend below non-descending word"
