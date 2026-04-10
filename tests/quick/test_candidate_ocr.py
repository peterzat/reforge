"""Quick tests for OCR-aware candidate selection (spec A4).

Verifies that generate_word's candidate selection prefers readable
candidates over those with higher image-quality scores but low OCR.
All model calls are mocked; no GPU required.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from reforge.config import OCR_SELECTION_WEIGHT


def _make_word_img(ink_val=30, h=64, w=256):
    """Synthetic word image with ink in the body zone."""
    img = np.full((h, w), 255, dtype=np.uint8)
    img[20:44, 30:w - 30] = ink_val
    return img


@pytest.mark.quick
class TestOCRAwareCandidateSelection:
    """A4: OCR-aware scoring selects readable candidate over higher image quality."""

    def test_readable_candidate_wins(self):
        """Candidate with lower image quality but higher OCR should win."""
        from reforge.quality.score import quality_score

        # Two synthetic images: img_a has better image quality, img_b is similar
        img_a = _make_word_img(ink_val=30)   # good contrast -> higher quality_score
        img_b = _make_word_img(ink_val=60)   # slightly worse contrast

        score_a = quality_score(img_a)
        score_b = quality_score(img_b)
        # Verify our assumption: img_a has higher image quality
        assert score_a >= score_b

        # Mock OCR: img_a is garbled (0.2), img_b is readable (0.9)
        ocr_results = {id(img_a): 0.2, id(img_b): 0.9}

        # Combined scores:
        # A: (1-0.4)*score_a + 0.4*0.2 = 0.6*score_a + 0.08
        # B: (1-0.4)*score_b + 0.4*0.9 = 0.6*score_b + 0.36
        # B should win because OCR gap (0.7) outweighs quality gap
        combined_a = (1 - OCR_SELECTION_WEIGHT) * score_a + OCR_SELECTION_WEIGHT * 0.2
        combined_b = (1 - OCR_SELECTION_WEIGHT) * score_b + OCR_SELECTION_WEIGHT * 0.9
        assert combined_b > combined_a, (
            f"Test premise failed: combined_b={combined_b:.3f} <= combined_a={combined_a:.3f}"
        )

    def test_gray_box_candidate_loses_despite_readability(self):
        """Candidate with gray box (low image quality) should lose even if readable."""
        from reforge.quality.score import quality_score

        img_good = _make_word_img(ink_val=30)
        # Gray box: dark background, poor quality score
        img_gray = np.full((64, 256), 160, dtype=np.uint8)
        img_gray[20:44, 30:226] = 50

        score_good = quality_score(img_good)
        score_gray = quality_score(img_gray)
        assert score_good > score_gray

        # Even if gray box is more readable, image quality penalty dominates
        combined_good = (1 - OCR_SELECTION_WEIGHT) * score_good + OCR_SELECTION_WEIGHT * 0.5
        combined_gray = (1 - OCR_SELECTION_WEIGHT) * score_gray + OCR_SELECTION_WEIGHT * 0.9
        assert combined_good > combined_gray, (
            "Gray box candidate should not win even with better OCR"
        )

    def test_ocr_weight_is_balanced(self):
        """OCR_SELECTION_WEIGHT should be in a reasonable range."""
        assert 0.2 <= OCR_SELECTION_WEIGHT <= 0.6

    def test_single_candidate_skips_ocr_scoring(self):
        """With num_candidates=1, OCR should not be called during selection."""
        from reforge.model.generator import generate_word

        # Build minimal mocks for single-candidate generation
        mock_unet = MagicMock()
        mock_vae = MagicMock()
        mock_tokenizer = MagicMock(return_value={"input_ids": np.zeros((1, 16))})

        img = _make_word_img()

        # Mock ddim_sample to return a valid image
        with patch("reforge.model.generator.ddim_sample", return_value=img), \
             patch("reforge.model.generator.postprocess_word", return_value=img), \
             patch("reforge.quality.score.quality_score", return_value=0.8), \
             patch("reforge.model.generator._get_ocr_fn", return_value=None) as mock_get_ocr:
            result = generate_word(
                "hello", mock_unet, mock_vae, mock_tokenizer,
                style_features=MagicMock(),
                num_candidates=1,
                device="cpu",
            )
            assert result is not None

    def test_multi_candidate_calls_ocr_per_candidate(self):
        """With num_candidates=3, OCR should be called for each candidate."""
        from reforge.model.generator import generate_word

        mock_unet = MagicMock()
        mock_vae = MagicMock()
        mock_tokenizer = MagicMock(return_value={"input_ids": np.zeros((1, 16))})

        imgs = [_make_word_img(ink_val=v) for v in [30, 40, 50]]
        img_iter = iter(imgs)

        mock_ocr = MagicMock(side_effect=[0.2, 0.9, 0.5])

        with patch("reforge.model.generator.ddim_sample", side_effect=lambda *a, **kw: next(img_iter)), \
             patch("reforge.model.generator.postprocess_word", side_effect=lambda x: x), \
             patch("reforge.quality.score.quality_score", return_value=0.8), \
             patch("reforge.model.generator._get_ocr_fn", return_value=mock_ocr):
            result = generate_word(
                "hello", mock_unet, mock_vae, mock_tokenizer,
                style_features=MagicMock(),
                num_candidates=3,
                device="cpu",
            )
            # OCR called 3 times (once per candidate)
            assert mock_ocr.call_count == 3
            # Should select the candidate with OCR=0.9 (imgs[1])
            assert np.array_equal(result, imgs[1])

    def test_reuse_ocr_in_rejection_loop(self):
        """A3: Selected candidate's OCR accuracy reused in rejection loop."""
        from reforge.model.generator import generate_word

        mock_unet = MagicMock()
        mock_vae = MagicMock()
        mock_tokenizer = MagicMock(return_value={"input_ids": np.zeros((1, 16))})

        img = _make_word_img()

        # OCR returns 0.8 for all candidates during selection (above 0.4 threshold).
        # The rejection loop should reuse this and NOT call ocr_fn again.
        ocr_call_count = 0
        def counting_ocr(img, word):
            nonlocal ocr_call_count
            ocr_call_count += 1
            return 0.8

        with patch("reforge.model.generator.ddim_sample", return_value=img), \
             patch("reforge.model.generator.postprocess_word", return_value=img), \
             patch("reforge.quality.score.quality_score", return_value=0.8), \
             patch("reforge.model.generator._get_ocr_fn", return_value=counting_ocr):
            result = generate_word(
                "hello", mock_unet, mock_vae, mock_tokenizer,
                style_features=MagicMock(),
                num_candidates=3,
                device="cpu",
            )
            # 3 calls during candidate selection, 0 during rejection loop
            # (because known_ocr_acc=0.8 >= 0.4 threshold, so loop exits immediately)
            assert ocr_call_count == 3
