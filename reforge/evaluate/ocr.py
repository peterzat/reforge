"""OCR-based accuracy evaluation using TrOCR.

Measures per-word readability by comparing OCR output against intended text.
Runs on CPU to avoid competing with GPU inference for model generation.
"""

import functools

import numpy as np
from PIL import Image


@functools.lru_cache(maxsize=1)
def _load_trocr():
    """Load TrOCR model and processor (cached, loaded once)."""
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel

    processor = TrOCRProcessor.from_pretrained("microsoft/trocr-small-handwritten")
    model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-small-handwritten")
    model.eval()
    return processor, model


def ocr_read(img: np.ndarray) -> str:
    """Read text from a grayscale word image using TrOCR.

    Args:
        img: Grayscale uint8 numpy array (single word image).

    Returns:
        Recognized text string.
    """
    import torch

    processor, model = _load_trocr()

    # TrOCR expects RGB PIL image
    if img.ndim == 2:
        pil_img = Image.fromarray(img, mode="L").convert("RGB")
    else:
        pil_img = Image.fromarray(img).convert("RGB")

    pixel_values = processor(images=pil_img, return_tensors="pt").pixel_values

    with torch.no_grad():
        generated_ids = model.generate(pixel_values)
    text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return text.strip()


def ocr_accuracy(img: np.ndarray, target: str) -> float:
    """Compute character-level accuracy between OCR output and target text.

    Args:
        img: Grayscale uint8 numpy array (single word image).
        target: Intended text for this word.

    Returns:
        Accuracy score in [0, 1] where 1.0 means perfect character match.
        Uses case-insensitive comparison and edit-distance-based scoring.
    """
    recognized = ocr_read(img)
    return _char_accuracy(recognized, target)


def _char_accuracy(recognized: str, target: str) -> float:
    """Compute character-level accuracy between two strings.

    Uses Levenshtein-distance-based scoring: 1 - (edit_distance / max_len).
    Case-insensitive comparison. Strips whitespace and punctuation from both.
    """
    # Normalize: lowercase, strip whitespace and trailing punctuation
    r = recognized.lower().strip().rstrip(".,;:!?")
    t = target.lower().strip().rstrip(".,;:!?")

    if not t:
        return 1.0 if not r else 0.0
    if not r:
        return 0.0

    # Levenshtein distance
    dist = _levenshtein(r, t)
    max_len = max(len(r), len(t))
    return max(0.0, 1.0 - dist / max_len)


def _levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]
