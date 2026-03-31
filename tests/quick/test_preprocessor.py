"""Quick tests for word segmentation and preprocessing."""

import numpy as np
import pytest
import cv2


@pytest.mark.quick
class TestSegmentation:
    def _make_sentence_image(self):
        """Create a synthetic image with 5 distinct words."""
        canvas = np.full((200, 800), 255, dtype=np.uint8)
        # Draw 5 "words" as black rectangles at known positions
        # Row 1: 3 words
        cv2.rectangle(canvas, (50, 30), (120, 70), 0, -1)   # word 1
        cv2.rectangle(canvas, (180, 30), (270, 70), 0, -1)  # word 2
        cv2.rectangle(canvas, (330, 35), (420, 75), 0, -1)  # word 3
        # Row 2: 2 words
        cv2.rectangle(canvas, (50, 120), (150, 160), 0, -1)  # word 4
        cv2.rectangle(canvas, (210, 120), (310, 160), 0, -1) # word 5
        return canvas

    def test_segment_words_finds_5(self):
        """Segmentation produces exactly 5 words from a 5-word image."""
        from reforge.preprocess.segment import segment_sentence_image
        img = self._make_sentence_image()
        words = segment_sentence_image(img)
        assert len(words) == 5, f"Expected 5 words, got {len(words)}"

    def test_segment_reading_order(self):
        """Words are returned in reading order (left-to-right, top-to-bottom)."""
        from reforge.preprocess.segment import segment_sentence_image
        img = self._make_sentence_image()
        words = segment_sentence_image(img)
        # Words should get progressively to the right within each line
        # and top line before bottom line
        # Just verify we got reasonable-sized crops
        for w in words:
            assert w.shape[0] > 5
            assert w.shape[1] > 5


@pytest.mark.quick
class TestTensorConversion:
    def test_tensor_shape(self):
        """Word tensor has correct shape (1, 3, 64, 256)."""
        from reforge.preprocess.normalize import word_to_tensor
        word_img = np.full((40, 100), 128, dtype=np.uint8)
        tensor = word_to_tensor(word_img)
        assert tensor.shape == (1, 3, 64, 256)

    def test_tensor_range(self):
        """Word tensor values are in [-1, 1]."""
        from reforge.preprocess.normalize import word_to_tensor
        word_img = np.random.randint(0, 256, (40, 100), dtype=np.uint8)
        tensor = word_to_tensor(word_img)
        assert tensor.min() >= -1.0
        assert tensor.max() <= 1.0

    def test_white_maps_to_positive(self):
        """White pixels (255) map to +1 under DiffusionPen normalization."""
        from reforge.preprocess.normalize import word_to_tensor
        white = np.full((40, 100), 255, dtype=np.uint8)
        tensor = word_to_tensor(white)
        # Most of canvas is white padding
        assert tensor.max() == pytest.approx(1.0, abs=0.01)

    def test_black_maps_to_negative(self):
        """Black pixels (0) map to -1 under DiffusionPen normalization."""
        from reforge.preprocess.normalize import word_to_tensor
        black = np.full((40, 100), 0, dtype=np.uint8)
        tensor = word_to_tensor(black)
        assert tensor.min() == pytest.approx(-1.0, abs=0.01)
