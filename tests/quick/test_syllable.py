"""Quick tests for syllable splitting."""

import pytest


@pytest.mark.quick
class TestSyllableSplitting:
    def test_short_word_no_split(self):
        """Words <= 10 chars are not split."""
        from reforge.model.generator import split_long_word
        assert split_long_word("hello") == ["hello"]
        assert split_long_word("abcdefghij") == ["abcdefghij"]  # 10 chars

    def test_handwriting_split(self):
        """'handwriting' (11 chars) splits into valid chunks."""
        from reforge.model.generator import split_long_word
        chunks = split_long_word("handwriting")
        assert len(chunks) >= 2
        # Each chunk >= 4 chars
        for chunk in chunks:
            assert len(chunk) >= 4, f"Chunk '{chunk}' is < 4 chars"
        # Chunks rejoin to original
        assert "".join(chunks) == "handwriting"

    def test_very_long_word(self):
        """Very long words split recursively."""
        from reforge.model.generator import split_long_word
        word = "abcdefghijklmnopqrstu"  # 21 chars
        chunks = split_long_word(word)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) >= 4
        assert "".join(chunks) == word

    def test_minimum_chunk_size(self):
        """No chunk is smaller than MIN_CHUNK_CHARS."""
        from reforge.model.generator import split_long_word
        from reforge.config import MIN_CHUNK_CHARS
        for word in ["extraordinary", "communication", "understanding"]:
            chunks = split_long_word(word)
            for chunk in chunks:
                assert len(chunk) >= MIN_CHUNK_CHARS
