"""Medium tests: A/B quality comparisons via CV evaluation.

Requires GPU. Skips without CUDA. Models are loaded once per session
via fixtures in conftest.py.
"""

import pytest
import torch

pytestmark = [pytest.mark.medium, pytest.mark.gpu]

SKIP_REASON = "Requires CUDA GPU"


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestCFGQuality:
    """CFG (classifier-free guidance) should improve ink quality over no guidance."""

    def test_cfg_improves_ink_contrast(
        self, unet, vae, tokenizer, style_features, uncond_context, device
    ):
        from reforge.evaluate.visual import check_ink_contrast
        from reforge.model.generator import generate_word

        word = "Hello"
        img_no_cfg = generate_word(
            word, unet, vae, tokenizer, style_features,
            num_steps=20, guidance_scale=1.0, num_candidates=1, device=device,
        )
        img_cfg = generate_word(
            word, unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=20, guidance_scale=3.0, num_candidates=1, device=device,
        )

        contrast_no_cfg = check_ink_contrast(img_no_cfg)
        contrast_cfg = check_ink_contrast(img_cfg)

        # CFG=3.0 should produce better ink contrast than no guidance
        assert contrast_cfg > contrast_no_cfg, (
            f"CFG=3.0 contrast ({contrast_cfg:.3f}) should exceed "
            f"CFG=1.0 contrast ({contrast_no_cfg:.3f})"
        )

    def test_cfg_produces_clean_background(
        self, unet, vae, tokenizer, style_features, uncond_context, device
    ):
        from reforge.evaluate.visual import check_background_cleanliness
        from reforge.model.generator import generate_word

        img = generate_word(
            "World", unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=20, guidance_scale=3.0, num_candidates=1, device=device,
        )
        cleanliness = check_background_cleanliness(img)

        # Generated words with CFG should have reasonably clean backgrounds
        assert cleanliness > 0.3, (
            f"Background cleanliness ({cleanliness:.3f}) too low for CFG=3.0"
        )


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestPostprocessingEffectiveness:
    """Postprocessing defense layers should improve image quality."""

    def test_postprocess_improves_background(
        self, unet, vae, tokenizer, style_features, uncond_context, device
    ):
        from reforge.evaluate.visual import check_background_cleanliness
        from reforge.model.generator import ddim_sample, postprocess_word

        text_ctx = tokenizer("Quick", return_tensors="pt", padding="max_length", max_length=16)

        raw = ddim_sample(
            unet, vae, text_ctx, style_features,
            uncond_context=uncond_context,
            num_steps=20, guidance_scale=3.0, device=device,
        )
        cleaned = postprocess_word(raw)

        raw_score = check_background_cleanliness(raw)
        cleaned_score = check_background_cleanliness(cleaned)

        assert cleaned_score >= raw_score, (
            f"Postprocessed cleanliness ({cleaned_score:.3f}) should not be worse "
            f"than raw ({raw_score:.3f})"
        )

    def test_postprocess_no_gray_boxes(
        self, unet, vae, tokenizer, style_features, uncond_context, device
    ):
        from reforge.evaluate.visual import check_gray_boxes
        from reforge.model.generator import generate_word

        # Test with a short word (most susceptible to gray boxes)
        img = generate_word(
            "I", unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=20, guidance_scale=3.0, num_candidates=2, device=device,
        )
        assert not check_gray_boxes(img), "Gray box artifacts detected after postprocessing"


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestHarmonizationEffectiveness:
    """Cross-word harmonization should improve consistency across multiple generated words."""

    def test_harmonization_improves_stroke_consistency(
        self, unet, vae, tokenizer, style_features, uncond_context, device
    ):
        from reforge.evaluate.visual import check_stroke_weight_consistency
        from reforge.model.generator import generate_word
        from reforge.quality.harmonize import harmonize_words

        words = ["Quick", "Brown", "Foxes"]
        imgs = []
        for w in words:
            img = generate_word(
                w, unet, vae, tokenizer, style_features,
                uncond_context=uncond_context,
                num_steps=20, guidance_scale=3.0, num_candidates=1, device=device,
            )
            imgs.append(img)

        score_before = check_stroke_weight_consistency(imgs)
        harmonized = harmonize_words(imgs)
        score_after = check_stroke_weight_consistency(harmonized)

        assert score_after >= score_before, (
            f"Harmonized consistency ({score_after:.3f}) should not be worse "
            f"than raw ({score_before:.3f})"
        )

    def test_multi_word_height_ratio(
        self, unet, vae, tokenizer, style_features, uncond_context, device
    ):
        from reforge.evaluate.visual import check_word_height_ratio
        from reforge.model.generator import generate_word
        from reforge.quality.harmonize import harmonize_words

        words = ["Jump", "High", "Over"]
        imgs = []
        for w in words:
            img = generate_word(
                w, unet, vae, tokenizer, style_features,
                uncond_context=uncond_context,
                num_steps=20, guidance_scale=3.0, num_candidates=1, device=device,
            )
            imgs.append(img)

        harmonized = harmonize_words(imgs)
        height_score = check_word_height_ratio(harmonized)

        # After harmonization, height ratio should be reasonable
        assert height_score > 0.3, (
            f"Word height ratio ({height_score:.3f}) too inconsistent after harmonization"
        )
