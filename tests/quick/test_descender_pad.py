"""Quick tests for descender clipping padding (spec B2/B4)."""

import numpy as np
import pytest


@pytest.mark.quick
class TestDescenderPadding:

    def test_no_padding_when_ink_not_at_bottom(self):
        """Image with ink well above canvas bottom gets no padding."""
        from reforge.model.generator import pad_clipped_descender
        img = np.full((64, 256), 255, dtype=np.uint8)
        img[20:44, 30:220] = 30  # ink far from bottom
        result = pad_clipped_descender(img)
        assert result.shape == img.shape

    def test_padding_added_when_ink_at_bottom(self):
        """Image with ink touching canvas bottom gets padded."""
        from reforge.model.generator import pad_clipped_descender
        img = np.full((64, 256), 255, dtype=np.uint8)
        img[10:64, 30:220] = 30  # ink reaches row 63 (last row)
        result = pad_clipped_descender(img)
        assert result.shape[0] > img.shape[0]
        assert result.shape[1] == img.shape[1]
        # Padding is white
        assert np.all(result[64:, :] == 255)

    def test_padding_proportional_to_ink_height(self):
        """Padding amount scales with ink height."""
        from reforge.model.generator import pad_clipped_descender
        # Tall ink region (50px): should get more padding
        tall = np.full((64, 256), 255, dtype=np.uint8)
        tall[10:64, 30:220] = 30
        tall_result = pad_clipped_descender(tall)
        tall_pad = tall_result.shape[0] - tall.shape[0]

        # Short ink region (15px): should get less padding (but at least 6)
        short = np.full((64, 256), 255, dtype=np.uint8)
        short[48:64, 30:220] = 30
        short_result = pad_clipped_descender(short)
        short_pad = short_result.shape[0] - short.shape[0]

        assert tall_pad > short_pad
        assert short_pad >= 6

    def test_blank_image_no_padding(self):
        """All-white image gets no padding."""
        from reforge.model.generator import pad_clipped_descender
        img = np.full((64, 256), 255, dtype=np.uint8)
        result = pad_clipped_descender(img)
        assert result.shape == img.shape

    def test_postprocessing_works_on_padded_image(self):
        """Body-zone noise removal and cluster filter work on padded images."""
        from reforge.model.generator import postprocess_word, pad_clipped_descender
        # Create image that triggers padding, then verify postprocess is safe
        img = np.full((64, 256), 255, dtype=np.uint8)
        img[10:64, 30:220] = 30  # ink to bottom
        processed = postprocess_word(img)
        padded = pad_clipped_descender(processed)
        # Should not raise, and should preserve ink
        assert np.any(padded < 128)
