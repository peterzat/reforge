"""Medium tests: generation-level quality checks with real models.

Tests single-word, short-word, long-word, and multi-word generation scenarios.
Requires GPU. Skips without CUDA. Models loaded once per session via conftest.py.
"""

import numpy as np
import pytest
import torch

pytestmark = [pytest.mark.medium, pytest.mark.gpu]

SKIP_REASON = "Requires CUDA GPU"


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestSingleWordGeneration:
    """Basic single-word generation through the real model."""

    def test_generates_valid_image(
        self, unet, vae, tokenizer, style_features, uncond_context, device
    ):
        from reforge.model.generator import generate_word

        img = generate_word(
            "Hello", unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=20, guidance_scale=3.0, num_candidates=1, device=device,
        )
        assert isinstance(img, np.ndarray)
        assert img.dtype == np.uint8
        assert img.ndim == 2
        assert img.shape[0] > 0 and img.shape[1] > 0


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestShortWordGeneration:
    """Very short words (1-2 chars) are most susceptible to gray boxes and size issues."""

    def test_single_char_no_gray_boxes(
        self, unet, vae, tokenizer, style_features, uncond_context, device
    ):
        from reforge.evaluate.visual import check_gray_boxes
        from reforge.model.generator import generate_word

        for word in ["a", "I"]:
            img = generate_word(
                word, unet, vae, tokenizer, style_features,
                uncond_context=uncond_context,
                num_steps=20, guidance_scale=3.0, num_candidates=2, device=device,
            )
            assert not check_gray_boxes(img), f"Gray boxes in short word '{word}'"

    def test_two_char_word_has_ink(
        self, unet, vae, tokenizer, style_features, uncond_context, device
    ):
        from reforge.evaluate.visual import check_ink_contrast
        from reforge.model.generator import generate_word

        img = generate_word(
            "an", unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=20, guidance_scale=3.0, num_candidates=2, device=device,
        )
        contrast = check_ink_contrast(img)
        assert contrast > 0.1, f"Two-char word 'an' has too little ink contrast ({contrast:.3f})"


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestLongWordGeneration:
    """Words >10 chars are split into chunks, generated separately, and stitched."""

    def test_long_word_produces_valid_image(
        self, unet, vae, tokenizer, style_features, uncond_context, device
    ):
        from reforge.model.generator import generate_word

        img = generate_word(
            "extraordinary", unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=20, guidance_scale=3.0, num_candidates=1, device=device,
        )
        assert isinstance(img, np.ndarray)
        assert img.dtype == np.uint8
        # Stitched image should be wider than a single chunk
        assert img.shape[1] > 200

    def test_long_word_no_gray_boxes(
        self, unet, vae, tokenizer, style_features, uncond_context, device
    ):
        from reforge.evaluate.visual import check_gray_boxes
        from reforge.model.generator import generate_word

        img = generate_word(
            "communication", unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=20, guidance_scale=3.0, num_candidates=1, device=device,
        )
        assert not check_gray_boxes(img), "Gray boxes in stitched long word"

    def test_long_word_has_reasonable_contrast(
        self, unet, vae, tokenizer, style_features, uncond_context, device
    ):
        from reforge.evaluate.visual import check_ink_contrast
        from reforge.model.generator import generate_word

        img = generate_word(
            "understanding", unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=20, guidance_scale=3.0, num_candidates=1, device=device,
        )
        contrast = check_ink_contrast(img)
        assert contrast > 0.2, f"Long word contrast ({contrast:.3f}) too low after stitching"


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestMultiWordLineComposition:
    """Generate enough words to force line wrapping and check composed output quality."""

    def test_multi_word_line_wrap(
        self, unet, vae, tokenizer, style_features, uncond_context, device
    ):
        from reforge.compose.layout import compute_word_positions
        from reforge.compose.render import compose_words
        from reforge.evaluate.visual import (
            check_background_cleanliness,
            check_gray_boxes,
        )
        from reforge.model.generator import generate_word
        from reforge.quality.font_scale import normalize_font_size
        from reforge.quality.harmonize import harmonize_words

        words = ["The", "quick", "brown", "fox", "jumps", "over", "the", "lazy"]
        imgs = []
        for w in words:
            img = generate_word(
                w, unet, vae, tokenizer, style_features,
                uncond_context=uncond_context,
                num_steps=20, guidance_scale=3.0, num_candidates=1, device=device,
            )
            imgs.append(normalize_font_size(img, w))

        imgs = harmonize_words(imgs)

        # Should wrap to multiple lines on default page width
        positions = compute_word_positions(imgs, words)
        lines = set(p["line"] for p in positions)
        assert len(lines) >= 2, (
            f"8 words should wrap to at least 2 lines, got {len(lines)}"
        )

        # Compose and check quality
        output = compose_words(imgs, words, upscale_factor=1)
        arr = np.array(output)
        assert not check_gray_boxes(arr), "Gray boxes in multi-word composed output"
        assert check_background_cleanliness(arr) > 0.3, "Background too noisy"
