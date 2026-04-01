"""Medium test: per-word OCR accuracy on generated words.

Generates words of varying length (3-8 chars), asserts average OCR > 0.6
and no single word below 0.3. Spec criterion 6.
"""

import numpy as np
import pytest
import torch

pytestmark = [
    pytest.mark.medium,
    pytest.mark.gpu,
    pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required"),
]

TEST_WORDS = ["The", "quiet", "morning", "light", "shadows"]


def test_per_word_ocr_accuracy(unet, vae, tokenizer, style_features, uncond_context, device):
    """Generate 5 words of varying length, check OCR accuracy."""
    from reforge.evaluate.ocr import ocr_accuracy
    from reforge.model.generator import generate_word
    from reforge.quality.font_scale import normalize_font_size

    accuracies = []
    for word in TEST_WORDS:
        img = generate_word(
            word, unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=20, guidance_scale=3.0, num_candidates=1, device=device,
        )
        img = normalize_font_size(img, word)
        acc = ocr_accuracy(img, word)
        print(f"  {word}: OCR={acc:.2f}")
        accuracies.append(acc)

    avg = float(np.mean(accuracies))
    min_acc = float(np.min(accuracies))
    print(f"  Average OCR: {avg:.2f}, Min: {min_acc:.2f}")

    assert avg > 0.6, f"Average OCR accuracy {avg:.2f} below 0.6"
    assert min_acc > 0.3, f"Minimum OCR accuracy {min_acc:.2f} below 0.3"
