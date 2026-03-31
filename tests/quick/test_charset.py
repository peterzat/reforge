"""Quick tests for charset validation."""

import pytest


@pytest.mark.quick
class TestCharset:
    def test_valid_text(self):
        """Valid text passes validation."""
        from reforge.validation import validate_charset
        validate_charset("Hello world 123")
        validate_charset("Quick Brown Foxes Jump High")
        validate_charset('Special: !#&*+,-./:;?"\'()')

    def test_invalid_chars_rejected(self):
        """Characters outside charset raise ValueError."""
        from reforge.validation import validate_charset
        with pytest.raises(ValueError):
            validate_charset("Hello\tworld")  # tab
        with pytest.raises(ValueError):
            validate_charset("cafe\u0301")  # accent

    def test_newlines_allowed(self):
        """Newlines are allowed as paragraph separators."""
        from reforge.validation import validate_charset
        validate_charset("First paragraph\nSecond paragraph")

    def test_charset_size(self):
        """Charset has exactly 80 characters."""
        from reforge.config import CHARSET
        assert len(CHARSET) == 80

    def test_split_paragraphs(self):
        """split_paragraphs correctly splits text."""
        from reforge.validation import split_paragraphs
        result = split_paragraphs("Hello world\nSecond line")
        assert len(result) == 2
        assert result[0] == ["Hello", "world"]
        assert result[1] == ["Second", "line"]

    def test_split_words(self):
        """split_words flattens paragraphs."""
        from reforge.validation import split_words
        result = split_words("Hello world\nFoo bar")
        assert result == ["Hello", "world", "Foo", "bar"]
