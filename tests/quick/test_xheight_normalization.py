"""Quick tests for x-height body-zone equalization.

Verifies that equalize_body_zones() scales down words whose body zone
is disproportionately large (like "gray" with no ascenders) so they
look proportional next to words with ascenders (like "jumping").
"""

import numpy as np
import pytest

from reforge.quality.font_scale import equalize_body_zones, normalize_font_size
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


def _thin_ring_word(canvas_h=80, width=256, top=10, bottom=70, x0=60, x1=200):
    """Thin-stroke all-body short word filling the canvas (DiffusionPen's 'so').

    2px outline, no ascender or descender: the body-zone pass reads it as a
    huge x-height and shrinks it hardest.
    """
    img = np.full((canvas_h, width), 255, dtype=np.uint8)
    img[top:bottom, x0:x0 + 2] = 30
    img[top:bottom, x1 - 2:x1] = 30
    img[top:top + 2, x0:x1] = 30
    img[bottom - 2:bottom, x0:x1] = 30
    return img


@pytest.mark.quick
class TestSingleResampleSizing:
    """size_words folds the sizing passes into one resample (audit 2026-10-13)."""

    def _words(self):
        imgs = [_word_with_ascender(), _word_with_ascender(body_top=22, body_bottom=48),
                _word_with_ascender(body_top=18, body_bottom=44), _thin_ring_word(),
                _word_without_ascender()]
        words = ["jumping", "little", "those", "so", "gray"]
        return imgs, words

    def test_each_word_is_resampled_exactly_once(self):
        import cv2
        from reforge.quality.font_scale import plan_word_scales, size_words
        imgs, words = self._words()
        scales = plan_word_scales(imgs, words, policy="total_height")
        out = size_words(imgs, words, policy="total_height")
        for img, s, o in zip(imgs, scales, out):
            if abs(s - 1.0) < 1e-6:
                assert o is img
                continue
            new_w = max(1, int(round(img.shape[1] * s)))
            new_h = max(1, int(round(img.shape[0] * s)))
            interp = cv2.INTER_AREA if s < 1.0 else cv2.INTER_CUBIC
            np.testing.assert_array_equal(o, cv2.resize(img, (new_w, new_h), interpolation=interp))

    def test_planned_heights_land_inside_pass2_band(self):
        from reforge.config import (
            HEIGHT_OUTLIER_THRESHOLD_PASS2, HEIGHT_UNDERSIZE_THRESHOLD_PASS2,
        )
        from reforge.quality.font_scale import plan_word_scales
        from reforge.quality.ink_metrics import compute_ink_height
        imgs, words = self._words()
        scales = plan_word_scales(imgs, words, policy="total_height")
        h = np.array([compute_ink_height(i) for i in imgs]) * np.array(scales)
        med = np.median(h)
        assert np.all(h <= med * HEIGHT_OUTLIER_THRESHOLD_PASS2 + 1e-6)
        assert np.all(h >= med * HEIGHT_UNDERSIZE_THRESHOLD_PASS2 - 1e-6)

    def test_thin_short_word_keeps_its_ink(self):
        """The chained passes shrink a thin all-body word to a ~24px
        bottleneck and re-inflate it, losing nearly all dark pixels
        (168 -> 2 here); a single resample keeps them."""
        from reforge.quality.font_scale import size_words
        from reforge.quality.harmonize import harmonize_heights, harmonize_heights_pass2
        imgs, words = self._words()
        single = size_words(imgs, words, policy="total_height")[3]
        chained = [normalize_font_size(i, w) for i, w in zip(imgs, words)]
        chained = harmonize_heights_pass2(harmonize_heights(equalize_body_zones(chained)))[3]
        assert (chained < 128).sum() < 20
        assert (single < 128).sum() > 150


@pytest.mark.quick
class TestZoneSizing:
    """SIZING_POLICY="zone": x-heights match across letter classes."""

    def _canvas_word(self, asc_rows=0, body=30, overshoot=0, width=200):
        """DiffusionPen-like word filling a 64px canvas: dense body band,
        sparse ascender stems above it, and sparse round-letter overshoot
        rows above and below the body (what makes real ink/x-height 1.2 for
        all-body words)."""
        img = np.full((64, width), 255, dtype=np.uint8)
        top = 2
        if asc_rows:
            img[top:top + asc_rows, 20:24] = 30
        bt = top + asc_rows + overshoot
        img[bt - overshoot:bt, 40:60] = 30
        img[bt:bt + body, 20:width - 20] = 30
        img[bt + body:bt + body + overshoot, 40:60] = 30
        return img

    def test_zone_class(self):
        from reforge.quality.font_scale import zone_class
        assert zone_class("was") == (0, 0)
        assert zone_class("two,") == (1, 0)
        assert zone_class("the") == (2, 0)
        assert zone_class("gray") == (0, 1)
        assert zone_class("by") == (2, 1)
        assert zone_class("I") == (2, 0)
        assert zone_class("they'd") == (2, 1)

    def test_short_words_get_matching_x_heights(self):
        """An all-body 'was' and a strong-ascender 'the' both fill the 64px
        canvas; zone sizing must give them matching measured x-heights, where
        the total_height policy gives 'was' ~2x the x-height of 'the'."""
        import cv2
        from reforge.config import ZONE_X_HEIGHT_TARGET
        from reforge.quality.font_scale import size_words
        from reforge.quality.ink_metrics import compute_x_height
        was = self._canvas_word(body=50, overshoot=5)        # ink 60, x 50
        the = self._canvas_word(asc_rows=34, body=26)        # ink 60, x 26
        imgs, words = [was, the], ["was", "the"]
        z = [compute_x_height(i) for i in size_words(imgs, words, policy="zone")]
        assert abs(z[0] - z[1]) <= 1, z
        assert abs(z[0] - ZONE_X_HEIGHT_TARGET) <= 1.5, z
        t = [compute_x_height(i) for i in size_words(imgs, words, policy="total_height")]
        assert t[0] > 1.6 * t[1], t

    def test_unknown_policy_raises(self):
        from reforge.quality.font_scale import plan_word_scales
        with pytest.raises(ValueError):
            plan_word_scales([self._canvas_word(body=40)], ["so"], policy="bogus")


@pytest.mark.quick
class TestXHeightConsistencyMetric:
    """evaluate.visual.check_x_height_consistency (gating metric, 2026-10-13)."""

    def _block(self, h, top, bottom, width=120):
        img = np.full((h, width), 255, dtype=np.uint8)
        img[top:bottom, 10:width - 10] = 30
        return img

    def test_matching_body_sizes_score_near_one(self):
        from reforge.evaluate.visual import check_x_height_consistency
        was = self._block(20, 2, 17)                 # all-body: ink 15 -> body 12.4
        foxes = self._block(40, 10, 22)              # dense band 12
        assert check_x_height_consistency([was, foxes], ["was", "foxes"]) > 0.95

    def test_shouted_short_word_scores_low(self):
        from reforge.evaluate.visual import check_x_height_consistency
        was = self._block(32, 2, 28)                 # ink 26 -> body 21.5
        foxes = self._block(40, 10, 22)
        assert check_x_height_consistency([was, foxes], ["was", "foxes"]) < 0.6

    def test_none_without_both_groups(self):
        from reforge.evaluate.visual import check_x_height_consistency
        assert check_x_height_consistency([self._block(40, 10, 22)], ["foxes"]) is None
        assert check_x_height_consistency([self._block(20, 2, 17)], ["was"]) is None
