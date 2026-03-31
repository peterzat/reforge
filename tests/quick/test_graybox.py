"""Quick tests for gray-box detection on synthetic images."""

import numpy as np
import pytest


@pytest.mark.quick
class TestGrayBoxDetection:
    def test_clean_image_no_graybox(self):
        """Clean image with white background and dark ink has no gray boxes."""
        from reforge.evaluate.visual import check_gray_boxes
        img = np.full((64, 256), 255, dtype=np.uint8)
        img[20:44, 30:220] = 30  # dark ink
        assert check_gray_boxes(img) is False

    def test_graybox_detected(self):
        """Image with a large gray rectangle is detected."""
        from reforge.evaluate.visual import check_gray_boxes
        img = np.full((64, 256), 255, dtype=np.uint8)
        # Add a gray box artifact
        img[5:60, 10:250] = 170
        # Add some ink on top
        img[20:44, 30:220] = 30
        assert check_gray_boxes(img) is True

    def test_all_white_no_graybox(self):
        """All-white image has no gray boxes."""
        from reforge.evaluate.visual import check_gray_boxes
        img = np.full((64, 256), 255, dtype=np.uint8)
        assert check_gray_boxes(img) is False
