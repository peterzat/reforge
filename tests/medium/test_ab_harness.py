"""Medium tests: A/B harness tests that compare variants via CV evaluation.

Requires GPU. Skips without CUDA.
"""

import pytest
import torch

pytestmark = [pytest.mark.medium, pytest.mark.gpu]

SKIP_REASON = "Requires CUDA GPU"


@pytest.mark.skipif(not torch.cuda.is_available(), reason=SKIP_REASON)
class TestABHarness:
    def test_cfg_comparison(self):
        """Generate two variants with different CFG scales and compare via CV evaluation."""
        from reforge.evaluate.visual import overall_quality_score
        from reforge.model.generator import generate_word
        from reforge.model.weights import (
            download_style_encoder_weights,
            download_unet_weights,
            load_tokenizer,
            load_unet,
            load_vae,
        )
        from reforge.model.encoder import StyleEncoder
        from reforge.preprocess.segment import segment_sentence_image
        from reforge.preprocess.normalize import preprocess_words
        import cv2
        import numpy as np

        # Load models
        device = "cuda"
        style_ckpt = download_style_encoder_weights()
        encoder = StyleEncoder(checkpoint_path=style_ckpt).to(device)

        style_img = cv2.imread("styles/hw-sample.png", cv2.IMREAD_GRAYSCALE)
        words = segment_sentence_image(style_img)
        assert len(words) == 5
        style_tensors = preprocess_words(words)
        style_features = encoder.encode(style_tensors)

        unet_ckpt = download_unet_weights()
        unet = load_unet(unet_ckpt, device=device)
        vae = load_vae(device=device)
        tokenizer = load_tokenizer()

        # Generate with CFG=1.0 (no guidance) vs CFG=3.0
        word = "Hello"
        img_no_cfg = generate_word(
            word, unet, vae, tokenizer, style_features,
            num_steps=20, guidance_scale=1.0, num_candidates=1, device=device,
        )
        img_cfg = generate_word(
            word, unet, vae, tokenizer, style_features,
            num_steps=20, guidance_scale=3.0, num_candidates=1, device=device,
        )

        # Both should produce valid images
        assert img_no_cfg.shape[0] > 0
        assert img_cfg.shape[0] > 0

        # CV evaluation should produce scores for both
        score_no_cfg = overall_quality_score(img_no_cfg)
        score_cfg = overall_quality_score(img_cfg)
        assert "overall" in score_no_cfg
        assert "overall" in score_cfg
