"""Quality regression gate logic.

Pure-python helpers that check a set of scores against a baseline and return
structured lists of regressions, diagnostics, and improvements. Extracted from
tests/medium/test_quality_regression.py so the same logic can be unit-tested
against synthetic scores without requiring a GPU (spec 2026-04-10 B4).

Two classes of metric:
- Primary metrics (gating): a regression on any of these fails the build.
- Diagnostics: tracked in the ledger and printed on regression, but non-fatal.

Metrics are split into "higher is better" and "lower is better" (inverted).
"""

from typing import Iterable


def check_metric_regressions(
    scores: dict,
    baseline_metrics: dict,
    metrics_higher: Iterable[str],
    metrics_lower: Iterable[str],
    tolerance: float,
) -> tuple[list[str], list[str], list[str]]:
    """Compare scores to baseline and categorize by direction.

    Args:
        scores: Current scores dict (metric -> float).
        baseline_metrics: Baseline dict (metric -> float).
        metrics_higher: Names of metrics where higher is better.
        metrics_lower: Names of metrics where lower is better (inverted).
        tolerance: Delta tolerance. A metric is a regression only if it
            moves against its preferred direction by more than this.

    Returns:
        Tuple of (regressions, improvements, stable). Each is a list of
        formatted strings. regressions empty => non-regressing.
    """
    regressions: list[str] = []
    improvements: list[str] = []
    stable: list[str] = []

    for metric in metrics_higher:
        if metric not in scores or metric not in baseline_metrics:
            continue
        current = scores[metric]
        recorded = baseline_metrics[metric]
        if not isinstance(current, (int, float)) or not isinstance(recorded, (int, float)):
            continue
        delta = current - recorded
        if delta < -tolerance:
            regressions.append(
                f"{metric}: {current:.4f} < baseline {recorded:.4f} (delta {delta:+.4f})"
            )
        elif delta > tolerance:
            improvements.append(f"{metric}: {current:.4f} (was {recorded:.4f}, +{delta:.4f})")
        else:
            stable.append(metric)

    for metric in metrics_lower:
        if metric not in scores or metric not in baseline_metrics:
            continue
        current = scores[metric]
        recorded = baseline_metrics[metric]
        if not isinstance(current, (int, float)) or not isinstance(recorded, (int, float)):
            continue
        delta = current - recorded
        if delta > tolerance:
            regressions.append(
                f"{metric}: {current:.4f} > baseline {recorded:.4f} (delta {delta:+.4f})"
            )
        elif delta < -tolerance:
            improvements.append(f"{metric}: {current:.4f} (was {recorded:.4f}, {delta:+.4f})")
        else:
            stable.append(metric)

    return regressions, improvements, stable


def check_ocr_min_gate(scores: dict, floor: float = 0.3) -> tuple[bool, float | None]:
    """Return (passed, observed_min).

    Fails (False) when the worst-word OCR score is below the floor, which
    catches unreadable outputs that primary-metric deltas can miss.
    """
    ocr_min = scores.get("ocr_min")
    if ocr_min is None:
        return True, None
    return ocr_min >= floor, float(ocr_min)
