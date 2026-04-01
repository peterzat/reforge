"""Quick tests for OCR evaluation functions.

Tests the character accuracy computation against known inputs.
The actual TrOCR model test uses a synthetic image and is marked
with a separate marker since it requires model download.
"""

import numpy as np
import pytest


@pytest.mark.quick
class TestCharAccuracy:
    """Test the _char_accuracy helper without requiring TrOCR model."""

    def test_exact_match(self):
        from reforge.evaluate.ocr import _char_accuracy
        assert _char_accuracy("Hello", "Hello") == 1.0

    def test_case_insensitive(self):
        from reforge.evaluate.ocr import _char_accuracy
        assert _char_accuracy("hello", "Hello") == 1.0

    def test_partial_match(self):
        from reforge.evaluate.ocr import _char_accuracy
        # "helo" vs "hello": 1 deletion, max_len=5, accuracy=0.8
        score = _char_accuracy("helo", "hello")
        assert 0.7 < score < 0.9

    def test_no_match(self):
        from reforge.evaluate.ocr import _char_accuracy
        score = _char_accuracy("xyz", "abc")
        assert score == 0.0

    def test_empty_recognized(self):
        from reforge.evaluate.ocr import _char_accuracy
        assert _char_accuracy("", "hello") == 0.0

    def test_empty_target(self):
        from reforge.evaluate.ocr import _char_accuracy
        assert _char_accuracy("", "") == 1.0

    def test_clipped_word(self):
        """Simulates the 'The' -> 'he' clipping bug."""
        from reforge.evaluate.ocr import _char_accuracy
        score = _char_accuracy("he", "The")
        # 'he' vs 'the' (case insensitive): edit distance 1 (missing 't'), max_len=3
        assert score < 0.8  # Should detect the clipping as a quality drop

    def test_punctuation_stripped(self):
        from reforge.evaluate.ocr import _char_accuracy
        assert _char_accuracy("hello.", "hello") == 1.0
        assert _char_accuracy("hello", "hello.") == 1.0


@pytest.mark.quick
class TestLevenshtein:
    def test_identical(self):
        from reforge.evaluate.ocr import _levenshtein
        assert _levenshtein("abc", "abc") == 0

    def test_insertion(self):
        from reforge.evaluate.ocr import _levenshtein
        assert _levenshtein("abc", "abcd") == 1

    def test_deletion(self):
        from reforge.evaluate.ocr import _levenshtein
        assert _levenshtein("abcd", "abc") == 1

    def test_substitution(self):
        from reforge.evaluate.ocr import _levenshtein
        assert _levenshtein("abc", "axc") == 1

    def test_empty(self):
        from reforge.evaluate.ocr import _levenshtein
        assert _levenshtein("", "abc") == 3
        assert _levenshtein("abc", "") == 3
