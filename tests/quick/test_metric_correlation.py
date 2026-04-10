"""Unit tests for scripts/metric_correlation.py.

Exercises the correlation logic against a tiny synthetic dataset. Asserts that
constant metrics are flagged (not crashed, not returned as NaN) and that
variable metrics produce a defined rho.
"""

import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts import metric_correlation as mc


def _make_review(rating, metrics, cand_pick=None, cand_agree=None):
    review = {
        "version": 1,
        "evaluations": {
            "composition": {"skipped": False, "rating": rating, "defects": [], "notes": ""},
        },
        "cv_metrics": metrics,
    }
    if cand_pick is not None:
        review["evaluations"]["candidate"] = {
            "skipped": False,
            "pick": cand_pick,
            "agrees_with_metric": cand_agree,
            "notes": "",
        }
    return review


@pytest.mark.quick
class TestCorrelation:
    def test_constant_metric_is_flagged(self):
        reviews = [
            ("a.json", _make_review(2, {"const_metric": 1.0, "varying": 0.2})),
            ("b.json", _make_review(3, {"const_metric": 1.0, "varying": 0.5})),
            ("c.json", _make_review(4, {"const_metric": 1.0, "varying": 0.8})),
        ]
        records = mc.compute_correlations(reviews)
        by_name = {r["metric"]: r for r in records}

        assert by_name["const_metric"]["constant"] is True
        assert by_name["const_metric"]["rho"] is None
        assert by_name["const_metric"]["n"] == 3
        assert by_name["const_metric"]["constant_value"] == 1.0

        assert by_name["varying"]["constant"] is False
        assert by_name["varying"]["rho"] is not None
        # Monotone increasing with rating -> rho ~ +1
        assert by_name["varying"]["rho"] > 0.99

    def test_reviews_without_rating_are_skipped(self):
        reviews = [
            ("a.json", _make_review(2, {"m": 0.1})),
            ("b.json", {
                "evaluations": {"composition": {"skipped": True}},
                "cv_metrics": {"m": 0.5},
            }),
            ("c.json", {
                "evaluations": {"composition": {"skipped": False, "rating": None}},
                "cv_metrics": {"m": 0.9},
            }),
            ("d.json", _make_review(4, {"m": 0.4})),
        ]
        records = mc.compute_correlations(reviews)
        by_name = {r["metric"]: r for r in records}
        assert by_name["m"]["n"] == 2

    def test_non_numeric_metrics_are_ignored(self):
        """ocr_per_word (list), gates_passed (bool), gate_details (dict) must be skipped."""
        reviews = [
            ("a.json", _make_review(2, {
                "numeric": 0.3,
                "ocr_per_word": [0.1, 0.2, 0.3],
                "gates_passed": True,
                "gate_details": {"gray_boxes": True},
            })),
            ("b.json", _make_review(4, {
                "numeric": 0.7,
                "ocr_per_word": [0.9, 0.9, 0.9],
                "gates_passed": False,
                "gate_details": {"gray_boxes": False},
            })),
        ]
        records = mc.compute_correlations(reviews)
        names = {r["metric"] for r in records}
        assert "numeric" in names
        assert "ocr_per_word" not in names
        assert "gates_passed" not in names
        assert "gate_details" not in names

    def test_candidate_agreement_insufficient_data(self):
        """Below CANDIDATE_MIN_N, agreement rate is None and insufficient flag set."""
        reviews = [
            ("a.json", _make_review(3, {"m": 0.5}, cand_pick="A", cand_agree=True)),
            ("b.json", _make_review(4, {"m": 0.6}, cand_pick="B", cand_agree=False)),
        ]
        result = mc.candidate_agreement(reviews)
        assert result["insufficient"] is True
        assert result["n"] == 2
        assert result["rate"] is None

    def test_candidate_agreement_sufficient(self):
        reviews = []
        for i in range(mc.CANDIDATE_MIN_N):
            agree = i % 2 == 0  # 5 agree out of 10
            reviews.append((
                f"r{i}.json",
                _make_review(3, {"m": 0.5}, cand_pick="A", cand_agree=agree),
            ))
        result = mc.candidate_agreement(reviews)
        assert result["insufficient"] is False
        assert result["n"] == mc.CANDIDATE_MIN_N
        assert result["agree"] == mc.CANDIDATE_MIN_N // 2
        assert result["rate"] == pytest.approx(0.5)

    def test_format_table_reports_constants_separately(self):
        reviews = [
            ("a.json", _make_review(2, {"const_m": 1.0, "var_m": 0.1})),
            ("b.json", _make_review(4, {"const_m": 1.0, "var_m": 0.9})),
        ]
        records = mc.compute_correlations(reviews)
        text = mc.format_correlation_table(records)
        assert "var_m" in text
        assert "const_m" in text
        assert "Constant metrics" in text
        assert "constant = 1.0000" in text

    def test_spearman_monotone(self):
        # Perfect increasing relationship
        assert mc.spearman([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == pytest.approx(1.0)
        # Perfect decreasing relationship
        assert mc.spearman([1, 2, 3, 4, 5], [50, 40, 30, 20, 10]) == pytest.approx(-1.0)

    def test_spearman_constant_input_returns_none(self):
        assert mc.spearman([1, 1, 1], [2, 3, 4]) is None
        assert mc.spearman([1, 2, 3], [5, 5, 5]) is None

    def test_spearman_handles_ties(self):
        # Ties should not crash and should produce a defined number
        rho = mc.spearman([1, 2, 2, 3, 4], [1, 2, 2, 3, 4])
        assert rho is not None
        assert rho == pytest.approx(1.0)

    def test_loads_real_review_files_if_present(self, tmp_path):
        """Integration-style: synthesize three reviews on disk and load them."""
        for i, (rating, val) in enumerate([(2, 0.2), (3, 0.5), (5, 0.9)]):
            review = _make_review(rating, {"m": val, "const_m": 1.0})
            with open(tmp_path / f"r{i}.json", "w") as f:
                json.dump(review, f)
        reviews = mc.load_reviews(str(tmp_path))
        assert len(reviews) == 3
        records = mc.compute_correlations(reviews)
        by_name = {r["metric"]: r for r in records}
        assert by_name["const_m"]["constant"] is True
        assert by_name["m"]["rho"] is not None
        assert by_name["m"]["rho"] > 0.99

    def test_scipy_wrapper_matches_pure_python_rho(self):
        """spearman_with_pvalue must return the same rho as the pure-python
        spearman() helper. This lets the unit tests stay dep-free while
        anchoring the scipy path to the tested behavior."""
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [0.1, 0.3, 0.2, 0.9, 0.7]
        mine = mc.spearman(xs, ys)
        rho, p = mc.spearman_with_pvalue(xs, ys)
        assert rho is not None
        assert p is not None
        assert rho == pytest.approx(mine, abs=1e-9)
        assert 0.0 <= p <= 1.0

    def test_scipy_wrapper_constant_input_returns_none(self):
        rho, p = mc.spearman_with_pvalue([1, 1, 1], [1, 2, 3])
        assert rho is None
        assert p is None


@pytest.mark.quick
class TestPrimarySelection:
    def _record(self, name, rho, p, n=16, constant=False):
        return {
            "metric": name, "rho": rho, "p": p, "n": n,
            "constant": constant, "constant_value": None,
        }

    def test_selection_bar_requires_positive_rho(self):
        """Negative rho metrics cannot be selected even if p < 0.3."""
        records = [
            self._record("good", 0.4, 0.1),
            self._record("negative", -0.5, 0.05),
        ]
        selected, near_misses, overflow, _ = mc.select_primary_metrics(records)
        assert [r["metric"] for r in selected] == ["good"]
        assert near_misses == []
        assert overflow == []

    def test_selection_bar_requires_rho_above_threshold(self):
        records = [
            self._record("above", 0.25, 0.15),
            self._record("below", 0.15, 0.05),  # rho below 0.2
        ]
        selected, _, _, _ = mc.select_primary_metrics(records)
        assert [r["metric"] for r in selected] == ["above"]

    def test_selection_bar_requires_p_below_threshold(self):
        records = [
            self._record("significant", 0.3, 0.25),
            self._record("near_miss", 0.3, 0.31),
        ]
        selected, near_misses, _, _ = mc.select_primary_metrics(records)
        assert [r["metric"] for r in selected] == ["significant"]
        assert [r["metric"] for r in near_misses] == ["near_miss"]

    def test_selection_caps_at_max_primary(self):
        """Even if more than B1_MAX_PRIMARY clear the bar, only the top N are selected."""
        records = [
            self._record("m1", 0.50, 0.05),
            self._record("m2", 0.45, 0.05),
            self._record("m3", 0.40, 0.05),
            self._record("m4", 0.35, 0.05),
            self._record("m5", 0.30, 0.05),
        ]
        selected, _, overflow, _ = mc.select_primary_metrics(records)
        assert len(selected) == mc.B1_MAX_PRIMARY
        assert len(overflow) == len(records) - mc.B1_MAX_PRIMARY
        # Selection is ranked by rho descending
        assert [r["metric"] for r in selected] == ["m1", "m2", "m3"][:mc.B1_MAX_PRIMARY]

    def test_constants_are_rejected(self):
        records = [
            self._record("const", None, None, constant=True),
            self._record("good", 0.4, 0.1),
        ]
        selected, near_misses, _, rejected = mc.select_primary_metrics(records)
        assert [r["metric"] for r in selected] == ["good"]
        assert "const" in [r["metric"] for r in rejected]

    def test_none_selected_is_empty_not_error(self):
        """When no metric clears the bar, select returns empty without crashing."""
        records = [
            self._record("weak1", 0.1, 0.5),
            self._record("weak2", -0.1, 0.5),
        ]
        selected, _, _, _ = mc.select_primary_metrics(records)
        assert selected == []

    def test_markdown_reports_no_selection(self):
        """When nothing clears the bar, the markdown must not crash and must
        explicitly say so (so a future reader sees the diagnosis)."""
        records = [
            self._record("weak", 0.1, 0.5),
        ]
        agreement = {"n": 0, "agree": 0, "rate": None, "insufficient": True}
        md = mc.render_markdown(records, agreement, "reviews/human", dataset_size=5)
        assert "No metrics cleared the bar" in md
