"""Quick tests for contraction detection, splitting, and two-part stitching.

Spec 2026-04-18 Option W: split_contraction keeps the apostrophe on the
right part (e.g. "can't" -> ("can", "'t")), so both parts render as normal
words and stitch_contraction is a two-part baseline-aligned concatenation
with no synthetic apostrophe insertion.
"""

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
        assert not is_contraction("'twas")

    def test_apostrophe_at_end(self):
        from reforge.model.generator import is_contraction
        assert not is_contraction("dogs'")

    def test_no_letters_around_apostrophe(self):
        from reforge.model.generator import is_contraction
        assert not is_contraction("'")
        assert not is_contraction("''")


@pytest.mark.quick
class TestSplitContraction:
    def test_standard_splits_keep_apostrophe_on_right(self):
        from reforge.model.generator import split_contraction
        assert split_contraction("can't") == ("can", "'t")
        assert split_contraction("don't") == ("don", "'t")
        assert split_contraction("it's") == ("it", "'s")
        assert split_contraction("they'd") == ("they", "'d")

    def test_possessive(self):
        from reforge.model.generator import split_contraction
        assert split_contraction("Katherine's") == ("Katherine", "'s")

    def test_multichar_suffix(self):
        from reforge.model.generator import split_contraction
        assert split_contraction("they've") == ("they", "'ve")
        assert split_contraction("you're") == ("you", "'re")

    def test_multiple_apostrophes_splits_at_first(self):
        """With multiple apostrophes, split happens at the first one
        and everything from that apostrophe onward is the right part."""
        from reforge.model.generator import split_contraction
        left, right = split_contraction("o'clock's")
        assert left == "o"
        assert right == "'clock's"

    def test_concatenation_reconstructs_original(self):
        """Left + right must equal the original word (no characters lost)."""
        from reforge.model.generator import split_contraction
        for word in ("can't", "don't", "it's", "they'd", "they've", "Katherine's"):
            left, right = split_contraction(word)
            assert left + right == word, f"{word} -> {left!r} + {right!r}"


@pytest.mark.quick
class TestStitchContraction:
    def _ink_rect(self, h, w, top, bottom, left, right, ink=60):
        img = np.full((h, w), 255, dtype=np.uint8)
        img[top:bottom, left:right] = ink
        return img

    def test_stitches_two_parts(self):
        from reforge.model.generator import stitch_contraction
        left = self._ink_rect(30, 40, 5, 25, 5, 35)
        right = self._ink_rect(30, 20, 5, 25, 3, 17)

        result = stitch_contraction(left, right)
        assert isinstance(result, np.ndarray)
        assert result.ndim == 2
        # Width should be roughly left + right (after tight crop + 1px gap).
        assert result.shape[1] > 20
        # The new signature is two-part only.
        assert np.any(result < 180)

    def test_baseline_alignment_across_differing_heights(self):
        """Left and right parts with different ink bottoms align by baseline."""
        from reforge.model.generator import stitch_contraction
        left = self._ink_rect(30, 40, 5, 25, 5, 35)     # ink bottom at row 24
        right = self._ink_rect(30, 20, 10, 28, 3, 17)   # ink bottom at row 27
        result = stitch_contraction(left, right)
        assert result.shape[0] >= 30
        assert np.any(result < 180)

    def test_signature_is_two_part_only(self):
        """stitch_contraction no longer accepts an apostrophe image parameter."""
        import inspect
        from reforge.model.generator import stitch_contraction
        params = list(inspect.signature(stitch_contraction).parameters)
        assert params == ["left_img", "right_img"], params


@pytest.mark.quick
def test_make_synthetic_apostrophe_is_gone():
    """make_synthetic_apostrophe was removed in spec 2026-04-18 Option W."""
    from reforge.model import generator
    assert not hasattr(generator, "make_synthetic_apostrophe")
