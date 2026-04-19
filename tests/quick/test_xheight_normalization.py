"""Quick tests for x-height body-zone equalization.

Verifies that equalize_body_zones() scales down words whose body zone
is disproportionately large (like "gray" with no ascenders) so they
look proportional next to words with ascenders (like "jumping").
"""

import numpy as np
import pytest

from reforge.quality.font_scale import (
    equalize_body_zones,
    equalize_body_zones_pass2,
    normalize_font_size,
)
from reforge.quality.ink_metrics import compute_x_height


def _word_with_ascender(canvas_h=64, width=256, body_top=20, body_bottom=45,
                        dot_row=5):
    """Synthetic word image with a body zone and an ascender dot (like 'i', 'j').

    The dot inflates total ink height but not x-height.
    """
    img = np.full((canvas_h, width), 255, dtype=np.uint8)
    # Body zone: dense ink
    img[body_top:body_bottom, 20:width - 20] = 60
    # Ascender dot: small isolated ink above body
    img[dot_row:dot_row + 3, 50:56] = 60
    return img


def _word_without_ascender(canvas_h=64, width=256, body_top=20, body_bottom=45):
    """Synthetic word image with body zone only (like 'gray', 'brown')."""
    img = np.full((canvas_h, width), 255, dtype=np.uint8)
    img[body_top:body_bottom, 20:width - 20] = 60
    return img


@pytest.mark.quick
class TestEqualizeBodyZones:
    def test_scales_down_oversized_body_zone(self):
        """After equalization, words with ascender dots and words without
        should have x-heights within 20% of each other."""
        # Simulate: after ink-height normalization, all have same total height
        # but "gray" (no ascender) has larger body zone
        jumping = _word_with_ascender(dot_row=5)
        quiet = _word_with_ascender(dot_row=3)
        gray = _word_without_ascender()
        brown = _word_without_ascender()

        # Normalize by ink height first (as the real pipeline does)
        imgs = [
            normalize_font_size(jumping, "jumping"),
            normalize_font_size(quiet, "quiet"),
            normalize_font_size(gray, "gray"),
            normalize_font_size(brown, "brown"),
        ]

        # Equalize body zones
        equalized = equalize_body_zones(imgs)

        heights = [compute_x_height(img) for img in equalized]
        max_h = max(heights)
        min_h = min(heights)
        assert min_h > 0, "All words should have detectable x-height"
        ratio = max_h / min_h
        assert ratio <= 1.2, (
            f"Max/min x-height ratio {ratio:.2f} exceeds 1.2 limit. "
            f"Heights: jumping={heights[0]}, quiet={heights[1]}, "
            f"gray={heights[2]}, brown={heights[3]}"
        )

    def test_does_not_scale_up(self):
        """equalize_body_zones should only scale DOWN, never up."""
        small_body = _word_with_ascender(body_top=25, body_bottom=40)  # 15px body
        big_body = _word_without_ascender(body_top=15, body_bottom=50)  # 35px body
        medium = _word_without_ascender(body_top=20, body_bottom=45)  # 25px body

        imgs = [small_body, big_body, medium]
        equalized = equalize_body_zones(imgs)

        # Small body should not have changed (only scale-down, never up)
        assert equalized[0].shape == small_body.shape

    def test_too_few_words_noop(self):
        """With fewer than 3 words, equalization is a no-op."""
        a = _word_without_ascender()
        b = _word_with_ascender()
        result = equalize_body_zones([a, b])
        assert result[0].shape == a.shape
        assert result[1].shape == b.shape


@pytest.mark.quick
class TestEqualizeBodyZonesPass2:
    """Pass2 runs post-harmonize to catch body-zone outliers that harmonize
    created by inflating short no-ascender words."""

    def test_scales_down_post_harmonize_outlier(self):
        """Words whose x-height is above 105% of median get scaled down."""
        oversized = _word_without_ascender(body_top=10, body_bottom=50)  # 40px body
        normal1 = _word_with_ascender(body_top=20, body_bottom=45)  # 25px body
        normal2 = _word_with_ascender(body_top=20, body_bottom=45)
        normal3 = _word_with_ascender(body_top=20, body_bottom=45)

        imgs = [oversized, normal1, normal2, normal3]
        result = equalize_body_zones_pass2(imgs)

        heights = [compute_x_height(img) for img in result]
        max_h = max(heights)
        min_h = min(heights)
        assert min_h > 0
        assert max_h / min_h <= 1.15, (
            f"Pass2 should have scaled the outlier closer to median. "
            f"Heights: {heights}"
        )

    def test_does_not_scale_up(self):
        """Pass2 is unidirectional: never inflates small bodies."""
        tiny_body = _word_with_ascender(body_top=30, body_bottom=40)  # 10px body
        normal1 = _word_without_ascender(body_top=20, body_bottom=45)  # 25px
        normal2 = _word_without_ascender(body_top=20, body_bottom=45)
        normal3 = _word_without_ascender(body_top=20, body_bottom=45)

        imgs = [tiny_body, normal1, normal2, normal3]
        result = equalize_body_zones_pass2(imgs)
        assert result[0].shape == tiny_body.shape

    def test_too_few_words_noop(self):
        a = _word_without_ascender()
        b = _word_with_ascender()
        result = equalize_body_zones_pass2([a, b])
        assert result[0].shape == a.shape
        assert result[1].shape == b.shape

    def test_single_pass_no_iteration(self):
        """Pass2 runs once. Extreme outliers are scaled in one step, not
        iteratively converged. This keeps the pass cheap and predictable."""
        extreme = _word_without_ascender(body_top=5, body_bottom=60)  # 55px body
        normal1 = _word_with_ascender(body_top=20, body_bottom=45)
        normal2 = _word_with_ascender(body_top=20, body_bottom=45)
        normal3 = _word_with_ascender(body_top=20, body_bottom=45)

        imgs = [extreme, normal1, normal2, normal3]
        result = equalize_body_zones_pass2(imgs)
        first_pass_height = compute_x_height(result[0])

        result2 = equalize_body_zones_pass2(result)
        second_pass_height = compute_x_height(result2[0])

        assert first_pass_height <= compute_x_height(extreme)
        assert second_pass_height <= first_pass_height * 1.1
