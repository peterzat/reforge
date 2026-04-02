"""Quick tests for CV evaluation functions against synthetic images."""

import numpy as np
import pytest


@pytest.mark.quick
class TestInkContrast:
    def test_high_contrast(self):
        """Dark ink on white background scores high."""
        from reforge.evaluate.visual import check_ink_contrast
        img = np.full((64, 256), 255, dtype=np.uint8)
        img[20:44, 30:220] = 20
        score = check_ink_contrast(img)
        assert score > 0.8

    def test_low_contrast(self):
        """Gray ink on gray background scores low."""
        from reforge.evaluate.visual import check_ink_contrast
        img = np.full((64, 256), 210, dtype=np.uint8)
        img[20:44, 30:220] = 180
        score = check_ink_contrast(img)
        assert score < 0.3


@pytest.mark.quick
class TestStrokeWeightConsistency:
    def test_consistent_words(self):
        """Words with same ink darkness score high."""
        from reforge.evaluate.visual import check_stroke_weight_consistency
        words = []
        for _ in range(5):
            img = np.full((40, 100), 255, dtype=np.uint8)
            img[10:30, 10:90] = 60
            words.append(img)
        score = check_stroke_weight_consistency(words)
        assert score > 0.9

    def test_inconsistent_words(self):
        """Words with varying ink darkness score lower."""
        from reforge.evaluate.visual import check_stroke_weight_consistency
        words = []
        for val in [20, 60, 100, 140, 170]:
            img = np.full((40, 100), 255, dtype=np.uint8)
            img[10:30, 10:90] = val
            words.append(img)
        score = check_stroke_weight_consistency(words)
        assert score < 0.5


@pytest.mark.quick
class TestWordHeightRatio:
    def test_uniform_heights(self):
        """Words with same height score 1.0."""
        from reforge.evaluate.visual import check_word_height_ratio
        words = []
        for _ in range(5):
            img = np.full((40, 100), 255, dtype=np.uint8)
            img[10:30, 10:90] = 60
            words.append(img)
        score = check_word_height_ratio(words)
        assert score == 1.0

    def test_varied_heights(self):
        """Words with very different heights score lower."""
        from reforge.evaluate.visual import check_word_height_ratio
        small = np.full((20, 100), 255, dtype=np.uint8)
        small[5:15, 10:90] = 60  # 10px height
        big = np.full((80, 100), 255, dtype=np.uint8)
        big[5:75, 10:90] = 60  # 70px height
        score = check_word_height_ratio([small, big])
        assert score < 0.5


@pytest.mark.quick
class TestBackgroundCleanliness:
    def test_clean_background(self):
        """White background with dark ink is clean."""
        from reforge.evaluate.visual import check_background_cleanliness
        img = np.full((64, 256), 255, dtype=np.uint8)
        img[20:44, 30:220] = 30
        score = check_background_cleanliness(img)
        assert score > 0.5

    def test_noisy_background(self):
        """Gray background scores low."""
        from reforge.evaluate.visual import check_background_cleanliness
        img = np.full((64, 256), 180, dtype=np.uint8)
        score = check_background_cleanliness(img)
        assert score < 0.5


@pytest.mark.quick
class TestHeightOutlierRatio:
    def test_uniform_heights(self):
        """Uniform height words return 1.0."""
        from reforge.evaluate.visual import compute_height_outlier_ratio
        words = []
        for _ in range(5):
            img = np.full((40, 100), 255, dtype=np.uint8)
            img[10:30, 10:90] = 60
            words.append(img)
        assert compute_height_outlier_ratio(words) == 1.0

    def test_outlier_detected(self):
        """A 2x height outlier returns 2.0."""
        from reforge.evaluate.visual import compute_height_outlier_ratio
        normal = []
        for _ in range(4):
            img = np.full((40, 100), 255, dtype=np.uint8)
            img[10:30, 10:90] = 60  # 20px ink height
            normal.append(img)
        big = np.full((80, 100), 255, dtype=np.uint8)
        big[5:45, 10:90] = 60  # 40px ink height
        normal.append(big)
        ratio = compute_height_outlier_ratio(normal)
        assert ratio == pytest.approx(2.0, abs=0.1)

    def test_in_quality_score(self):
        """height_outlier_ratio appears in overall_quality_score when word_imgs given."""
        from reforge.evaluate.visual import overall_quality_score
        words = []
        for _ in range(3):
            img = np.full((40, 100), 255, dtype=np.uint8)
            img[10:30, 10:90] = 60
            words.append(img)
        page = np.full((100, 400), 255, dtype=np.uint8)
        page[20:60, 20:380] = 60
        result = overall_quality_score(page, word_imgs=words)
        assert "height_outlier_ratio" in result
        assert result["height_outlier_ratio"] == pytest.approx(1.0, abs=0.01)


@pytest.mark.quick
class TestCompositionScore:
    def test_square_image_scores_higher(self):
        """Near-square image with good margins scores well."""
        from reforge.evaluate.visual import check_composition_score
        img = np.full((400, 400), 255, dtype=np.uint8)
        positions = [
            {"x": 24, "y": 16, "width": 60, "height": 30, "line": 0, "is_paragraph_start": True},
            {"x": 100, "y": 16, "width": 60, "height": 30, "line": 0, "is_paragraph_start": False},
        ]
        score = check_composition_score(img, positions)
        assert score > 0.5

    def test_very_wide_image_scores_lower(self):
        """Very wide image (landscape) should score lower on aspect ratio."""
        from reforge.evaluate.visual import check_composition_score
        img = np.full((100, 1000), 255, dtype=np.uint8)
        positions = [
            {"x": 50, "y": 5, "width": 60, "height": 30, "line": 0, "is_paragraph_start": True},
        ]
        score = check_composition_score(img, positions)
        # Still produces a score, but aspect sub-score is lower
        assert score < 0.9

    def test_in_quality_score(self):
        """composition_score appears when word_positions given."""
        from reforge.evaluate.visual import overall_quality_score
        img = np.full((400, 400), 255, dtype=np.uint8)
        img[20:60, 20:380] = 60
        positions = [
            {"x": 24, "y": 20, "width": 60, "height": 30, "line": 0, "is_paragraph_start": True},
        ]
        result = overall_quality_score(img, word_positions=positions)
        assert "composition_score" in result


@pytest.mark.quick
class TestStyleSimilarity:
    def test_identical_images(self):
        """Identical images score near 1.0."""
        from reforge.evaluate.visual import compute_style_similarity
        img = np.full((40, 100), 255, dtype=np.uint8)
        img[10:30, 20:80] = 60
        score = compute_style_similarity(img, [img, img])
        assert score > 0.9

    def test_different_brightness(self):
        """Very different ink brightness scores lower."""
        from reforge.evaluate.visual import compute_style_similarity
        light = np.full((40, 100), 255, dtype=np.uint8)
        light[10:30, 20:80] = 150
        dark = np.full((40, 100), 255, dtype=np.uint8)
        dark[10:30, 20:80] = 20
        score = compute_style_similarity(light, [dark])
        assert score < 0.8

    def test_in_quality_score(self):
        """style_fidelity appears when style_reference_imgs given."""
        from reforge.evaluate.visual import overall_quality_score
        gen = np.full((40, 100), 255, dtype=np.uint8)
        gen[10:30, 20:80] = 60
        ref = np.full((40, 100), 255, dtype=np.uint8)
        ref[10:30, 20:80] = 60
        page = np.full((100, 400), 255, dtype=np.uint8)
        page[20:60, 20:380] = 60
        result = overall_quality_score(
            page, word_imgs=[gen], style_reference_imgs=[ref],
        )
        assert "style_fidelity" in result
        assert result["style_fidelity"] > 0.8


@pytest.mark.quick
class TestPresets:
    def test_presets_have_required_keys(self):
        """Each preset has steps, guidance_scale, candidates."""
        from reforge.config import PRESETS
        for name, preset in PRESETS.items():
            assert "steps" in preset, f"{name} missing steps"
            assert "guidance_scale" in preset, f"{name} missing guidance_scale"
            assert "candidates" in preset, f"{name} missing candidates"

    def test_preset_names(self):
        from reforge.config import PRESETS
        assert "draft" in PRESETS
        assert "fast" in PRESETS
        assert "quality" in PRESETS


@pytest.mark.quick
class TestOverallQuality:
    def test_returns_dict(self):
        """overall_quality_score returns dict with expected keys."""
        from reforge.evaluate.visual import overall_quality_score
        img = np.full((64, 256), 255, dtype=np.uint8)
        img[20:44, 30:220] = 30
        result = overall_quality_score(img)
        assert isinstance(result, dict)
        assert "overall" in result
        assert "gray_boxes" in result
        assert "ink_contrast" in result

    def test_gates_and_continuous_keys(self):
        """Result includes gate details and height_outlier_score."""
        from reforge.evaluate.visual import overall_quality_score
        img = np.full((100, 400), 255, dtype=np.uint8)
        img[20:60, 20:380] = 30
        words = [np.full((40, 100), 255, dtype=np.uint8) for _ in range(3)]
        for w in words:
            w[10:30, 10:90] = 60
        positions = [
            {"x": 20, "y": 20, "width": 100, "height": 40, "line": 0},
        ]
        result = overall_quality_score(img, word_imgs=words, word_positions=positions)
        assert "gates_passed" in result
        assert "gate_details" in result
        assert "height_outlier_score" in result
        assert isinstance(result["gate_details"], dict)

    def test_gate_failure_caps_overall(self):
        """Gray box detection (gate failure) caps overall at 0.30."""
        from reforge.evaluate.visual import overall_quality_score
        # Create image with a large gray box artifact
        img = np.full((200, 400), 255, dtype=np.uint8)
        img[20:60, 20:380] = 30   # ink
        img[80:180, 50:350] = 170  # large gray rectangle
        result = overall_quality_score(img)
        assert result["gray_boxes"] == 0.0
        assert not result["gates_passed"]
        assert result["overall"] <= 0.30

    def test_continuous_weights_sum_to_one(self):
        """Continuous metric weights sum to 1.0."""
        from reforge.config import QUALITY_CONTINUOUS_WEIGHTS
        total = sum(QUALITY_CONTINUOUS_WEIGHTS.values())
        assert total == pytest.approx(1.0, abs=0.001)

    def test_score_varies_with_stroke_consistency(self):
        """Overall score changes when stroke_weight_consistency changes."""
        from reforge.evaluate.visual import overall_quality_score
        img = np.full((100, 400), 255, dtype=np.uint8)
        img[20:60, 20:380] = 30

        # Consistent words
        good_words = []
        for _ in range(5):
            w = np.full((40, 100), 255, dtype=np.uint8)
            w[10:30, 10:90] = 60
            good_words.append(w)

        # Inconsistent words
        bad_words = []
        for val in [20, 60, 100, 140, 170]:
            w = np.full((40, 100), 255, dtype=np.uint8)
            w[10:30, 10:90] = val
            bad_words.append(w)

        positions = [
            {"x": 20, "y": 20, "width": 350, "height": 40, "line": 0},
        ]
        good_result = overall_quality_score(img, word_imgs=good_words, word_positions=positions)
        bad_result = overall_quality_score(img, word_imgs=bad_words, word_positions=positions)
        assert good_result["overall"] > bad_result["overall"]

    def test_composition_score_affects_overall(self):
        """composition_score is now a continuous metric, not observation-only."""
        from reforge.evaluate.visual import overall_quality_score
        img = np.full((100, 400), 255, dtype=np.uint8)
        img[20:60, 20:380] = 30
        words = [np.full((40, 100), 255, dtype=np.uint8) for _ in range(3)]
        for w in words:
            w[10:30, 10:90] = 60
        positions = [
            {"x": 24, "y": 16, "width": 60, "height": 30, "line": 0},
            {"x": 100, "y": 16, "width": 60, "height": 30, "line": 0},
        ]
        result = overall_quality_score(img, word_imgs=words, word_positions=positions)
        # composition_score should be in the continuous metrics, not excluded
        assert "composition_score" in result
        # Overall should not be near 1.0 (old behavior) when composition is ~0.69
        assert result["overall"] < 0.98

    def test_overall_not_near_saturated(self):
        """With all gates passing and typical values, overall is in ~0.80-0.95 range."""
        from reforge.evaluate.visual import overall_quality_score
        img = np.full((400, 400), 255, dtype=np.uint8)
        img[20:60, 20:380] = 30
        words = [np.full((40, 100), 255, dtype=np.uint8) for _ in range(5)]
        for w in words:
            w[10:30, 10:90] = 60
        positions = [
            {"x": 24, "y": 16, "width": 60, "height": 30, "line": 0},
            {"x": 100, "y": 16, "width": 60, "height": 30, "line": 0},
        ]
        result = overall_quality_score(img, word_imgs=words, word_positions=positions)
        # Should have headroom: not saturated at ~0.98+
        assert result["overall"] < 0.97


@pytest.mark.quick
class TestSSIM:
    def test_identical_images(self):
        """SSIM of identical images is 1.0."""
        from reforge.evaluate.reference import compute_ssim
        img = np.full((64, 256), 255, dtype=np.uint8)
        img[20:44, 30:220] = 30
        assert compute_ssim(img, img) == pytest.approx(1.0, abs=0.001)

    def test_very_different_images(self):
        """SSIM of very different images is low."""
        from reforge.evaluate.reference import compute_ssim
        white = np.full((64, 256), 255, dtype=np.uint8)
        black = np.full((64, 256), 0, dtype=np.uint8)
        ssim = compute_ssim(white, black)
        assert ssim < 0.1

    def test_similar_images(self):
        """SSIM of slightly different images is high but not 1.0."""
        from reforge.evaluate.reference import compute_ssim
        img_a = np.full((64, 256), 255, dtype=np.uint8)
        img_a[20:44, 30:220] = 30
        img_b = img_a.copy()
        img_b[20:44, 30:220] = 40  # slightly lighter ink
        ssim = compute_ssim(img_a, img_b)
        assert 0.7 < ssim < 1.0

    def test_different_sizes(self):
        """SSIM handles different-sized images by resizing."""
        from reforge.evaluate.reference import compute_ssim
        small = np.full((32, 128), 200, dtype=np.uint8)
        big = np.full((64, 256), 200, dtype=np.uint8)
        ssim = compute_ssim(small, big)
        assert ssim > 0.8  # similar content, different size

    def test_empty_image(self):
        """SSIM of empty image returns 0.0."""
        from reforge.evaluate.reference import compute_ssim
        empty = np.array([], dtype=np.uint8)
        normal = np.full((64, 256), 255, dtype=np.uint8)
        assert compute_ssim(empty, normal) == 0.0


@pytest.mark.quick
class TestLedger:
    def test_append_and_read(self, tmp_path):
        """Ledger append and recent_runs work correctly."""
        from reforge.evaluate.ledger import append_entry, recent_runs
        path = str(tmp_path / "test_ledger.jsonl")

        scores = {"overall": 0.85, "ink_contrast": 0.9, "gates_passed": True}
        entry = append_entry(path, scores, config={"seed": 42}, context="test")
        assert entry["scores"]["overall"] == 0.85
        assert entry["context"] == "test"

        runs = recent_runs(path)
        assert len(runs) == 1
        assert runs[0]["scores"]["overall"] == 0.85

    def test_metric_trend(self, tmp_path):
        """metric_trend returns (timestamp, value) pairs."""
        from reforge.evaluate.ledger import append_entry, metric_trend
        path = str(tmp_path / "test_ledger.jsonl")

        for val in [0.80, 0.85, 0.90]:
            append_entry(path, {"overall": val})

        trend = metric_trend(path, "overall")
        assert len(trend) == 3
        assert trend[0][1] == 0.80
        assert trend[2][1] == 0.90

    def test_recent_runs_limit(self, tmp_path):
        """recent_runs respects the n parameter."""
        from reforge.evaluate.ledger import append_entry, recent_runs
        path = str(tmp_path / "test_ledger.jsonl")

        for i in range(10):
            append_entry(path, {"overall": i * 0.1})

        runs = recent_runs(path, n=3)
        assert len(runs) == 3
        assert runs[0]["scores"]["overall"] == 0.7
