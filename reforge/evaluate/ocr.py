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

    name = "microsoft/trocr-small-handwritten"
    # Cached copy first: from_pretrained otherwise asks the Hub for updates on
    # every load, and a throttled or slow Hub stalled the quick test tier
    # (2026-10-13). Download only when the model is not cached.
    try:
        processor = TrOCRProcessor.from_pretrained(name, local_files_only=True)
        model = VisionEncoderDecoderModel.from_pretrained(name, local_files_only=True)
    except OSError:
        processor = TrOCRProcessor.from_pretrained(name)
        model = VisionEncoderDecoderModel.from_pretrained(name)
    model.eval()
    return processor, model


def ocr_read(img: np.ndarray, backend: str | None = None) -> str:
    """Read text from a grayscale word image.

    TrOCR-small by default. ``REFORGE_OCR_BACKEND=vlm`` reads with the local
    vision-language model instead (reforge.evaluate.vlm; needs a running
    server). The env var applies to evaluation callers only: generation
    (best-of-N selection and the OCR retry loop) always passes
    ``backend="trocr"``. The VLM backend is for development and evaluation
    runs: it reads short words far more reliably than TrOCR, but it is not
    deterministic across model versions and needs the GPU server, so gates
    and tests keep the default.

    Args:
        img: Grayscale uint8 numpy array (single word image).
        backend: "trocr" or "vlm" to force a reader; None reads the
            ``REFORGE_OCR_BACKEND`` env var (default "trocr").

    Returns:
        Recognized text string.
    """
    import os

    if backend is None:
        backend = os.environ.get("REFORGE_OCR_BACKEND", "trocr")
    if backend == "vlm":
        from reforge.evaluate.vlm import read_word

        return read_word(img)

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


def ocr_accuracy(img: np.ndarray, target: str, backend: str | None = None) -> float:
    """Compute character-level accuracy between OCR output and target text.

    Args:
        img: Grayscale uint8 numpy array (single word image).
        target: Intended text for this word.
        backend: Reader override passed to ``ocr_read`` (None = env var).

    Returns:
        Accuracy score in [0, 1] where 1.0 means perfect character match.
        Uses case-insensitive comparison and edit-distance-based scoring.
    """
    recognized = ocr_read(img, backend=backend)
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
