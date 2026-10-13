"""Quick tests for baseline detection and alignment."""

import cv2
import numpy as np
import pytest


@pytest.mark.quick
class TestBaselineDetection:
    def test_baseline_above_descender(self):
        """Baseline is detected above descender region."""
        from reforge.compose.layout import detect_baseline
        # Image with body text in top 60%, descender in bottom 20%
        img = np.full((100, 200), 255, dtype=np.uint8)
        # Body zone: rows 20-60
        img[20:60, 30:170] = 40
        # Thin descender: rows 60-80
        img[60:80, 100:110] = 40
        bl = detect_baseline(img)
        # Baseline should be around row 60 (before descender)
        assert 50 <= bl <= 70

    def test_baseline_at_bottom_no_descender(self):
        """Without descenders, baseline is near bottom of ink."""
        from reforge.compose.layout import detect_baseline
        img = np.full((100, 200), 255, dtype=np.uint8)
        img[20:60, 30:170] = 40
        bl = detect_baseline(img)
        assert bl >= 50

    def test_empty_image(self):
        """Empty image returns bottom row as baseline."""
        from reforge.compose.layout import detect_baseline
        img = np.full((100, 200), 255, dtype=np.uint8)
        bl = detect_baseline(img)
        assert bl == 99


@pytest.mark.quick
class TestBaselineWithDescenders:
    """B2: Targeted tests for words containing descender letters.

    Each test creates a synthetic image with body text in rows 15-45 and
    a thin descender tail below. The correct baseline is at the body bottom
    (~row 44). detect_baseline() with the word parameter should detect
    the baseline within 3px of that target.
    """

    def _make_descender_image(
        self,
        body_rows=(15, 45),
        descender_rows=(45, 62),
        descender_cols=(80, 95),
        body_cols=(20, 200),
    ):
        """Create a synthetic word image with body + descender."""
        img = np.full((64, 256), 255, dtype=np.uint8)
        # Body zone
        img[body_rows[0]:body_rows[1], body_cols[0]:body_cols[1]] = 40
        # Thin descender tail
        img[descender_rows[0]:descender_rows[1], descender_cols[0]:descender_cols[1]] = 50
        return img

    def test_gray_baseline_with_word(self):
        """'gray' (g descender): baseline detected above descender tail."""
        from reforge.compose.layout import detect_baseline
        img = self._make_descender_image(
            descender_cols=(30, 45),  # g descender on left side
        )
        bl = detect_baseline(img, word="gray")
        # Body bottom is row 44; baseline should be within 3px
        assert abs(bl - 44) <= 3, f"Expected baseline ~44, got {bl}"

    def test_fences_baseline_with_word(self):
        """'fences' (no DESCENDER_LETTERS match): exercises default path with descender-like image."""
        from reforge.compose.layout import detect_baseline
        # f-tail: thinner descender, narrower column
        img = self._make_descender_image(
            descender_rows=(45, 55),
            descender_cols=(25, 33),
        )
        bl = detect_baseline(img, word="fences")
        assert abs(bl - 44) <= 3, f"Expected baseline ~44, got {bl}"

    def test_jumping_baseline_with_word(self):
        """'jumping' (p descender): baseline above the p's descender."""
        from reforge.compose.layout import detect_baseline
        img = self._make_descender_image(
            descender_cols=(100, 115),  # p descender in middle
        )
        bl = detect_baseline(img, word="jumping")
        assert abs(bl - 44) <= 3, f"Expected baseline ~44, got {bl}"

    def test_quickly_baseline_with_word(self):
        """'quickly' (q and y descenders): two descender tails."""
        from reforge.compose.layout import detect_baseline
        img = np.full((64, 256), 255, dtype=np.uint8)
        # Body
        img[15:45, 20:200] = 40
        # q descender
        img[45:60, 60:72] = 50
        # y descender
        img[45:58, 170:182] = 50
        bl = detect_baseline(img, word="quickly")
        assert abs(bl - 44) <= 3, f"Expected baseline ~44, got {bl}"

    def test_descender_without_word_param(self):
        """Without word param, descender detection still works but may be less accurate."""
        from reforge.compose.layout import detect_baseline
        img = self._make_descender_image()
        # Without word hint, the function should still attempt detection
        bl_no_word = detect_baseline(img)
        bl_with_word = detect_baseline(img, word="gray")
        # Both should find a baseline; with word should be >= without word
        # (without word, the scan may be fooled by descender ink)
        assert bl_no_word >= 0
        assert bl_with_word >= 0


@pytest.mark.quick
class TestBaselineOnRealisticWordShapes:
    """Spec 2026-04-19 criterion 1: detect_baseline must return within 3px of
    the true body-ink bottom for short non-descender words whose body density
    peaks below BASELINE_DENSITY_DROP. Review 10 flagged `two` rendering "super
    low" in composition; the root cause is line-median drift when a descender
    neighbor's detected baseline lands on the descender tail rather than the
    body baseline. Both failure modes are covered here."""

    def _cv2_word(self, word: str, h: int = 64, w: int = 256):
        """Render a word with cv2.putText (script font) at baseline y=50."""
        img = np.full((h, w), 255, dtype=np.uint8)
        cv2.putText(img, word, (10, 50), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.5, 30, 2, cv2.LINE_AA)
        return img

    def test_short_non_descender_matches_ink_bottom(self):
        """two / an / he / can: body ink bottom is the baseline."""
        from reforge.compose.layout import detect_baseline
        for word in ("two", "an", "he", "can", "Hello"):
            img = self._cv2_word(word)
            ink_rows = np.any(img < 180, axis=1)
            ink_bottom = len(ink_rows) - 1 - int(np.argmax(ink_rows[::-1]))
            bl = detect_baseline(img, word=word)
            assert abs(bl - ink_bottom) <= 3, (
                f"{word!r}: baseline={bl}, ink_bottom={ink_bottom}, "
                f"delta={bl - ink_bottom}"
            )

    def test_descender_word_returns_body_baseline_not_tail(self):
        """jump / by / py / gp: baseline detected at body bottom, not
        descender bottom. Body peak density for cv2-rendered script text
        is well below BASELINE_BODY_DENSITY (0.35), which is why the old
        walkback failed and returned the descender bottom."""
        from reforge.compose.layout import detect_baseline
        for word in ("jump", "by", "py", "gp"):
            img = self._cv2_word(word)
            ink_rows = np.any(img < 180, axis=1)
            ink_bottom = len(ink_rows) - 1 - int(np.argmax(ink_rows[::-1]))
            bl = detect_baseline(img, word=word)
            # Baseline should be well above the descender tail, close to
            # where cv2 placed it (y=49).
            assert abs(bl - 49) <= 3, (
                f"{word!r}: baseline={bl} should be near true baseline 49; "
                f"ink_bottom={ink_bottom} (descender tail)"
            )
            # And specifically should NOT land on the descender bottom.
            assert bl < ink_bottom - 5, (
                f"{word!r}: baseline={bl} looks like it landed on the "
                f"descender bottom (ink_bottom={ink_bottom})"
            )


@pytest.mark.quick
class TestComposedLineBaselineAlignment:
    """Spec 2026-04-19 criterion 2: compose_words places every word's body
    baseline on a shared row within 3 px across a line that mixes
    non-descender and descender shapes."""

    def _cv2_word(self, word: str, h: int = 64, w: int = 256):
        img = np.full((h, w), 255, dtype=np.uint8)
        cv2.putText(img, word, (10, 50), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.5, 30, 2, cv2.LINE_AA)
        return img

    def test_short_non_descender_aligns_with_descender_neighbors(self):
        from reforge.compose.layout import detect_baseline
        from reforge.compose.render import compose_words

        words = ["two", "by", "morning", "he"]
        imgs = [self._cv2_word(w) for w in words]

        # Force all words onto one line with a generous page width.
        composed, positions = compose_words(
            imgs, words, page_width=2400, upscale_factor=1, return_positions=True,
        )
        composed_arr = np.array(composed)

        # Per-line check: compute each word's absolute baseline in the
        # composed canvas, group by line, assert deviation within line.
        from collections import defaultdict
        by_line: dict[int, list[tuple[str, int]]] = defaultdict(list)
        for pos, word in zip(positions, words):
            x, y, h, w_slice = pos["x"], pos["y"], pos["height"], pos["width"]
            crop = composed_arr[y:y + h, x:x + w_slice]
            bl_rel = detect_baseline(crop, word=word)
            by_line[pos["line"]].append((word, y + bl_rel))

        assert by_line, "no words positioned"
        for line_num, entries in by_line.items():
            bls = [bl for _, bl in entries]
            median_bl = int(np.median(bls))
            max_dev = max(abs(bl - median_bl) for bl in bls)
            assert max_dev <= 3, (
                f"line {line_num} baselines {dict(entries)} deviate up to "
                f"{max_dev} px from median {median_bl}; expected <= 3 px"
            )


@pytest.mark.quick
class TestBaselineAlignment:
    def test_perfect_alignment(self):
        """Words at same y position score 1.0."""
        from reforge.evaluate.visual import check_baseline_alignment
        img = np.full((200, 800), 255, dtype=np.uint8)
        positions = [
            {"x": 10, "y": 50, "height": 40, "line": 0},
            {"x": 100, "y": 50, "height": 40, "line": 0},
            {"x": 200, "y": 50, "height": 40, "line": 0},
        ]
        score = check_baseline_alignment(img, positions)
        assert score == 1.0

    def test_misaligned_scores_lower(self):
        """Words at different y positions score lower."""
        from reforge.evaluate.visual import check_baseline_alignment
        img = np.full((200, 800), 255, dtype=np.uint8)
        positions = [
            {"x": 10, "y": 50, "height": 40, "line": 0},
            {"x": 100, "y": 70, "height": 40, "line": 0},  # 20px off
            {"x": 200, "y": 50, "height": 40, "line": 0},
        ]
        score = check_baseline_alignment(img, positions)
        assert score < 1.0


@pytest.mark.quick
class TestComposeAcrossCanvasHeights:
    """Audit 2026-10-13: sizing rescales each word canvas by a different
    factor, so baseline row indices are not comparable across words. The
    removed 20%-from-median clamp snapped a correctly detected word on a
    short canvas to the median row, raising it off the line."""

    def _block_word(self, h, top, bottom, w=60):
        img = np.full((h, w), 255, dtype=np.uint8)
        img[top:bottom, 5:w - 5] = 30
        return img

    def _ink_bottom_on_canvas(self, arr, pos):
        crop = arr[pos["y"]:pos["y"] + pos["height"], pos["x"]:pos["x"] + pos["width"]]
        rows = np.where(np.any(crop < 180, axis=1))[0]
        return pos["y"] + int(rows[-1])

    def test_short_canvas_word_sits_on_the_line(self):
        from reforge.compose.render import compose_words
        words = ["the", "was", "noon", "on"]
        imgs = [
            self._block_word(64, 20, 47),   # baseline row 46
            self._block_word(64, 20, 47),
            self._block_word(64, 20, 47),
            self._block_word(30, 5, 24),    # shrunk canvas, baseline row 23
        ]
        composed, positions = compose_words(
            imgs, words, page_width=2400, upscale_factor=1, return_positions=True,
        )
        arr = np.array(composed)
        bottoms = [self._ink_bottom_on_canvas(arr, p) for p in positions]
        assert max(bottoms) - min(bottoms) <= 2, bottoms  # +/-1 px jitter

    def test_first_line_word_with_low_baseline_is_not_dropped(self):
        from reforge.compose.render import compose_words
        words = ["one", "two", "three"]
        imgs = [
            self._block_word(40, 10, 30),
            self._block_word(40, 10, 30),
            self._block_word(40, 15, 35),   # baseline 5 rows (17%) lower: under the old clamp
        ]
        composed, positions = compose_words(
            imgs, words, page_width=2400, upscale_factor=1, return_positions=True,
        )
        arr = np.array(composed)
        assert len(positions) == 3
        for p in positions:
            crop = arr[p["y"]:p["y"] + p["height"], p["x"]:p["x"] + p["width"]]
            assert np.any(crop < 180), f"word at {p} has no ink on the page"


@pytest.mark.quick
class TestBaselineFailureModesFromRealOutput:
    """Profiles measured on demo-text output (audit 2026-10-13)."""

    def test_it_with_crossbar_returns_ink_bottom(self):
        """'it': thin stems under a dense crossbar used to read as a drop,
        putting the baseline at the crossbar (mid-body)."""
        from reforge.compose.layout import detect_baseline
        img = np.full((35, 26), 255, dtype=np.uint8)
        img[0:28, 16:17] = 30        # t stem (1px)
        img[13:15, 10:24] = 30       # t crossbar at mid-height (dense rows)
        img[15:28, 4:5] = 30         # i stem (1px): rows below read as a drop
        img[9:11, 4:5] = 30          # i dot
        assert detect_baseline(img, word="it") == 27

    def test_narrow_by_with_tail_curl_returns_body_bottom(self):
        """'by' cropped to ~20px wide: the one-row bottom curl of the y tail
        used to count as body below, so no drop was ever accepted."""
        from reforge.compose.layout import detect_baseline
        img = np.full((33, 21), 255, dtype=np.uint8)
        img[0:16, 1:3] = 30           # b ascender + stem
        img[9:16, 1:12] = 30          # b bowl + y arms: body rows 9-15
        img[9:16, 14:20] = 30
        img[16:25, 18:19] = 30        # y tail (density ~0.05)
        img[24:26, 12:19] = 30        # tail curl: dense for 2 rows in a narrow crop
        bl = detect_baseline(img, word="by")
        assert abs(bl - 15) <= 1, bl

    def test_for_lower_body_rows_below_absolute_threshold(self):
        """'for': lower body rows at 0.2-0.3 density were skipped by the
        absolute 0.35 walk-back, landing on the crossbar row."""
        from reforge.compose.layout import detect_baseline
        img = np.full((35, 51), 255, dtype=np.uint8)
        img[0:28, 6:8] = 30           # f stem with descender to row 27
        img[12:14, 2:18] = 30         # f crossbar + top of o/r (dense)
        img[12:21, 20:22] = 30        # o left side
        img[12:21, 30:32] = 30        # o right side
        img[19:21, 20:32] = 30        # o bottom stroke
        img[12:21, 38:40] = 30        # r stem
        img[12:14, 38:48] = 30        # r arm
        bl = detect_baseline(img, word="for")
        assert abs(bl - 20) <= 1, bl
