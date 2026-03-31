"""Text validation and splitting utilities."""

from reforge.config import CHARSET


def validate_charset(text: str) -> None:
    """Raise ValueError if text contains characters outside the supported charset.

    Newlines are allowed as paragraph separators.
    """
    allowed = set(CHARSET) | {"\n"}
    invalid = set(text) - allowed
    if invalid:
        raise ValueError(
            f"Unsupported characters: {invalid!r}. "
            f"Allowed: {CHARSET!r} plus newline for paragraph breaks."
        )


def split_paragraphs(text: str) -> list[list[str]]:
    """Split text into paragraphs, each paragraph into words.

    Returns a list of paragraphs, where each paragraph is a list of words.
    Empty paragraphs (double newlines) create paragraph breaks.
    """
    validate_charset(text)
    paragraphs = []
    for block in text.split("\n"):
        block = block.strip()
        if not block:
            continue
        words = block.split()
        if words:
            paragraphs.append(words)
    return paragraphs


def split_words(text: str) -> list[str]:
    """Split text into a flat list of words, ignoring paragraph structure."""
    paragraphs = split_paragraphs(text)
    return [word for para in paragraphs for word in para]
