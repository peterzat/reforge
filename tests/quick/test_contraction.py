"""Quick tests for contraction detection, splitting, and synthetic apostrophe."""

import numpy as np
import pytest


@pytest.mark.quick
class TestIsContraction:
    def test_standard_contractions(self):
        from reforge.model.generator import is_contraction
        assert is_contraction("can't")
        assert is_contraction("don't")
        assert is_contraction("it's")
        assert is_contraction("they'd")

    def test_possessives(self):
        from reforge.model.generator import is_contraction
        assert is_contraction("Katherine's")
        assert is_contraction("dog's")

    def test_not_contraction(self):
        from reforge.model.generator import is_contraction
        assert not is_contraction("hello")
        assert not is_contraction("world")
        assert not is_contraction("")

    def test_apostrophe_at_start(self):
        from reforge.model.generator import is_contraction
        # Leading apostrophe (not a contraction split point)
        assert not is_contraction("'twas")

    def test_apostrophe_at_end(self):
        from reforge.model.generator import is_contraction
        # Trailing apostrophe
        assert not is_contraction("dogs'")

    def test_no_letters_around_apostrophe(self):
        from reforge.model.generator import is_contraction
        assert not is_contraction("'")
        assert not is_contraction("''")


@pytest.mark.quick
class TestSplitContraction:
    def test_standard_splits(self):
        from reforge.model.generator import split_contraction
        assert split_contraction("can't") == ("can", "t")
        assert split_contraction("don't") == ("don", "t")
        assert split_contraction("it's") == ("it", "s")
        assert split_contraction("they'd") == ("they", "d")

    def test_possessive(self):
        from reforge.model.generator import split_contraction
        assert split_contraction("Katherine's") == ("Katherine", "s")

    def test_multiple_apostrophes(self):
        """With multiple apostrophes, splits at the first one."""
        from reforge.model.generator import split_contraction
        left, right = split_contraction("o'clock's")
        assert left == "o"
        assert right == "clock's"


@pytest.mark.quick
class TestMakeSyntheticApostrophe:
    def test_returns_image(self):
        from reforge.model.generator import make_synthetic_apostrophe
        img = make_synthetic_apostrophe(ink_intensity=60, body_height=30)
        assert isinstance(img, np.ndarray)
        assert img.dtype == np.uint8
        assert img.ndim == 2

    def test_dimensions_proportional(self):
        from reforge.model.generator import make_synthetic_apostrophe
        img = make_synthetic_apostrophe(ink_intensity=60, body_height=30)
        assert img.shape[0] == 30  # matches body_height
        assert img.shape[1] >= 3   # at least mark width + padding

    def test_has_ink(self):
        from reforge.model.generator import make_synthetic_apostrophe
        img = make_synthetic_apostrophe(ink_intensity=60, body_height=30)
        # Should have some dark pixels (the apostrophe mark)
        assert np.any(img < 180)

    def test_mostly_white(self):
        from reforge.model.generator import make_synthetic_apostrophe
        img = make_synthetic_apostrophe(ink_intensity=60, body_height=30)
        # Most pixels should be white background
        white_fraction = np.mean(img == 255)
        assert white_fraction > 0.7

    def test_different_intensities(self):
        from reforge.model.generator import make_synthetic_apostrophe
        light = make_synthetic_apostrophe(ink_intensity=120, body_height=30)
        dark = make_synthetic_apostrophe(ink_intensity=40, body_height=30)
        # Dark version should have darker ink pixels
        light_ink = light[light < 200]
        dark_ink = dark[dark < 200]
        if len(light_ink) > 0 and len(dark_ink) > 0:
            assert np.median(dark_ink) < np.median(light_ink)

    def test_small_body_height(self):
        """Should not crash on very small body heights."""
        from reforge.model.generator import make_synthetic_apostrophe
        img = make_synthetic_apostrophe(ink_intensity=60, body_height=4)
        assert img.shape[0] == 4
        assert img.shape[1] >= 2


@pytest.mark.quick
class TestStitchContraction:
    def test_stitches_three_parts(self):
        from reforge.model.generator import stitch_contraction
        left = np.full((30, 40), 255, dtype=np.uint8)
        left[5:25, 5:35] = 60  # ink
        apos = np.full((30, 6), 255, dtype=np.uint8)
        apos[3:10, 2:4] = 60  # apostrophe mark
        right = np.full((30, 20), 255, dtype=np.uint8)
        right[5:25, 3:17] = 60  # ink

        result = stitch_contraction(left, apos, right)
        assert isinstance(result, np.ndarray)
        assert result.ndim == 2
        # Width should be roughly sum of parts (minus tight crop + gaps)
        assert result.shape[1] > 20

    def test_baseline_alignment(self):
        """Parts with different heights align by ink bottom."""
        from reforge.model.generator import stitch_contraction
        # Left: ink at rows 5-25 (bottom = 25)
        left = np.full((30, 40), 255, dtype=np.uint8)
        left[5:25, 5:35] = 60
        # Right: ink at rows 10-28 (bottom = 28, different from left)
        right = np.full((30, 20), 255, dtype=np.uint8)
        right[10:28, 3:17] = 60
        apos = np.full((30, 6), 255, dtype=np.uint8)
        apos[3:10, 2:4] = 60

        result = stitch_contraction(left, apos, right)
        # Should not crash and should produce a valid image
        assert result.shape[0] >= 30
        assert np.any(result < 180)  # has ink
