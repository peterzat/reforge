"""Quick tests for the primary-metric regression gate.

Exercises reforge.evaluate.regression_gate with synthetic scores and baselines
so the gating logic is covered without requiring GPU inference. Satisfies
spec 2026-04-10 B4: the primary-metric gate must fire when a primary metric
is mutated downward, and diagnostic metrics must not fail the gate.
"""

import pytest

from reforge.config import PRIMARY_METRICS
from reforge.evaluate.regression_gate import (
    check_metric_regressions,
    check_ocr_min_gate,
)


TOLERANCE = 0.05


def _baseline():
    return {
        "height_outlier_score": 0.90,
        "baseline_alignment": 0.85,
        "composition_score": 0.40,
        "style_fidelity": 0.35,
        "ocr_accuracy": 0.90,
        "height_outlier_ratio": 1.0,
    }


def _passing_scores():
    return dict(_baseline())


@pytest.mark.quick
class TestPrimaryMetricsConfig:
    def test_primary_metrics_from_correlation_analysis(self):
        """PRIMARY_METRICS must be derived from the correlation analysis in
        docs/metric_correlation.md. The selection bar: positive rho, |rho| >= 0.2,
        p < 0.3 (scipy two-sided), at most 3 metrics. Changing this list should
        require a deliberate update to docs/metric_correlation.md.

        At N=16 only height_outlier_score cleared the bar. baseline_alignment
        was a near-miss (p = 0.307) and is a tracked diagnostic, not a primary
        gate. This test pins the selection so a code change cannot silently
        widen or narrow it without a corresponding spec decision.
        """
        assert isinstance(PRIMARY_METRICS, list)
        assert len(PRIMARY_METRICS) >= 1
        assert len(PRIMARY_METRICS) <= 3
        assert "height_outlier_score" in PRIMARY_METRICS
        # baseline_alignment is explicitly NOT in the list: p = 0.307 > 0.3.
        # If future data pushes it under the bar, update docs/metric_correlation.md
        # and this test together.
        assert "baseline_alignment" not in PRIMARY_METRICS


@pytest.mark.quick
class TestGateFiresOnPrimaryRegression:
    def test_primary_metric_mutated_down_fires_gate(self):
        """Dropping a primary metric below tolerance must produce a regression."""
        scores = _passing_scores()
        scores["height_outlier_score"] = 0.80  # was 0.90, drop of 0.10 > tolerance

        regressions, _, _ = check_metric_regressions(
            scores, _baseline(),
            metrics_higher=PRIMARY_METRICS,
            metrics_lower=[],
            tolerance=TOLERANCE,
        )
        assert len(regressions) == 1
        assert "height_outlier_score" in regressions[0]

    def test_diagnostic_only_regression_does_not_fire_primary_gate(self):
        """baseline_alignment is a near-miss diagnostic, not a primary metric.
        Mutating it downward must NOT fire the primary-metric gate, even if
        the drop is large. A separate diagnostic pass would log it."""
        scores = _passing_scores()
        scores["baseline_alignment"] = 0.50  # big drop on a non-primary metric

        regressions, _, _ = check_metric_regressions(
            scores, _baseline(),
            metrics_higher=PRIMARY_METRICS,
            metrics_lower=[],
            tolerance=TOLERANCE,
        )
        assert regressions == []

    def test_within_tolerance_does_not_fire(self):
        """A regression smaller than tolerance is not a gate failure."""
        scores = _passing_scores()
        scores["height_outlier_score"] = 0.87  # delta 0.03, within tolerance

        regressions, _, _ = check_metric_regressions(
            scores, _baseline(),
            metrics_higher=PRIMARY_METRICS,
            metrics_lower=[],
            tolerance=TOLERANCE,
        )
        assert regressions == []

    def test_all_primary_passing_is_clean(self):
        regressions, improvements, _ = check_metric_regressions(
            _passing_scores(), _baseline(),
            metrics_higher=PRIMARY_METRICS,
            metrics_lower=[],
            tolerance=TOLERANCE,
        )
        assert regressions == []
        # No change -> no improvements
        assert improvements == []


@pytest.mark.quick
class TestDiagnosticsDoNotGate:
    def test_diagnostic_regression_does_not_fire_primary_gate(self):
        """A diagnostic metric regressing does not produce a primary-gate failure."""
        scores = _passing_scores()
        scores["composition_score"] = 0.10  # huge drop in diagnostic

        primary_regs, _, _ = check_metric_regressions(
            scores, _baseline(),
            metrics_higher=PRIMARY_METRICS,
            metrics_lower=[],
            tolerance=TOLERANCE,
        )
        # Diagnostic regression alone must not appear in the primary-gate list
        assert primary_regs == []

        # Sanity: the same metric IS a regression when we include it
        diag_regs, _, _ = check_metric_regressions(
            scores, _baseline(),
            metrics_higher=["composition_score"],
            metrics_lower=[],
            tolerance=TOLERANCE,
        )
        assert len(diag_regs) == 1
        assert "composition_score" in diag_regs[0]


@pytest.mark.quick
class TestInvertedMetric:
    def test_higher_value_on_inverted_metric_is_regression(self):
        """height_outlier_ratio: lower is better, so increasing it past tolerance
        is a regression."""
        scores = _passing_scores()
        scores["height_outlier_ratio"] = 1.20  # was 1.0, delta +0.20

        regressions, _, _ = check_metric_regressions(
            scores, _baseline(),
            metrics_higher=[],
            metrics_lower=["height_outlier_ratio"],
            tolerance=TOLERANCE,
        )
        assert len(regressions) == 1
        assert "height_outlier_ratio" in regressions[0]

    def test_lower_value_on_inverted_metric_is_improvement(self):
        scores = _passing_scores()
        scores["height_outlier_ratio"] = 0.85

        regressions, improvements, _ = check_metric_regressions(
            scores, _baseline(),
            metrics_higher=[],
            metrics_lower=["height_outlier_ratio"],
            tolerance=TOLERANCE,
        )
        assert regressions == []
        assert len(improvements) == 1


@pytest.mark.quick
class TestOcrMinGate:
    def test_ocr_min_below_floor_fails(self):
        ok, val = check_ocr_min_gate({"ocr_min": 0.25}, floor=0.3)
        assert ok is False
        assert val == 0.25

    def test_ocr_min_at_floor_passes(self):
        ok, val = check_ocr_min_gate({"ocr_min": 0.3}, floor=0.3)
        assert ok is True
        assert val == 0.3

    def test_ocr_min_missing_passes(self):
        ok, val = check_ocr_min_gate({}, floor=0.3)
        assert ok is True
        assert val is None
