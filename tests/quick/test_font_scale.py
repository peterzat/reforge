"""Quick tests for case-aware font normalization."""

import numpy as np
import pytest

from reforge.quality.font_scale import normalize_font_size, _is_all_caps
from reforge.quality.ink_metrics import compute_ink_height


def _word_img(ink_height=60, canvas_height=80, width=256):
    """Create a synthetic word image with specified ink height."""
    img = np.full((canvas_height, width), 255, dtype=np.uint8)
    top = (canvas_height - ink_height) // 2
    img[top:top + ink_height, 10:width - 10] = 60
    return img


@pytest.mark.quick
class TestIsAllCaps:
    def test_single_capital(self):
        assert _is_all_caps("I") is True

    def test_all_caps_word(self):
        assert _is_all_caps("THE") is True

    def test_mixed_case(self):
        assert _is_all_caps("She") is False

    def test_lowercase(self):
        assert _is_all_caps("quick") is False

    def test_caps_with_punctuation(self):
        assert _is_all_caps("OK!") is True

    def test_single_lowercase(self):
        assert _is_all_caps("a") is False


@pytest.mark.quick
class TestCaseAwareSizing:
    def test_capital_I_shorter_than_lowercase_word(self):
        """Capital 'I' should normalize shorter than a lowercase word."""
        img = _word_img()
        i_normed = normalize_font_size(img, "I")
        quick_normed = normalize_font_size(img, "quick")
        i_h = compute_ink_height(i_normed)
        q_h = compute_ink_height(quick_normed)
        assert i_h < q_h, f"'I' ({i_h}px) should be shorter than 'quick' ({q_h}px)"

    def test_all_caps_shorter_than_mixed(self):
        """All-caps 'THE' should normalize shorter than mixed-case 'She'."""
        img = _word_img()
        the_normed = normalize_font_size(img, "THE")
        she_normed = normalize_font_size(img, "She")
        the_h = compute_ink_height(the_normed)
        she_h = compute_ink_height(she_normed)
        assert the_h < she_h

    def test_cap_height_ratio(self):
        """Capital height should be roughly 70-75% of standard target."""
        img = _word_img()
        i_normed = normalize_font_size(img, "I")
        quick_normed = normalize_font_size(img, "quick")
        ratio = compute_ink_height(i_normed) / compute_ink_height(quick_normed)
        assert 0.60 <= ratio <= 0.80, f"Cap/body ratio {ratio:.2f} outside 0.60-0.80"

    def test_lowercase_words_same_height(self):
        """Lowercase words of different lengths should get the same target."""
        img = _word_img()
        h_quick = compute_ink_height(normalize_font_size(img, "quick"))
        h_something = compute_ink_height(normalize_font_size(img, "something"))
        assert h_quick == h_something
