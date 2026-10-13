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
    strict: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    """Compare scores to baseline and categorize by direction.

    Args:
        scores: Current scores dict (metric -> float).
        baseline_metrics: Baseline dict (metric -> float).
        metrics_higher: Names of metrics where higher is better.
        metrics_lower: Names of metrics where lower is better (inverted).
        tolerance: Delta tolerance. A metric is a regression only if it
            moves against its preferred direction by more than this.
        strict: Treat a metric missing from scores or baseline as a
            regression. Use for gating metrics: otherwise a renamed metric or
            a stale baseline file silently gates on nothing.

    Returns:
        Tuple of (regressions, improvements, stable). Each is a list of
        formatted strings. regressions empty => non-regressing.
    """
    regressions: list[str] = []
    improvements: list[str] = []
    stable: list[str] = []

    def _missing(metric):
        where = [n for n, d in (("scores", scores), ("baseline", baseline_metrics))
                 if not isinstance(d.get(metric), (int, float))]
        if where and strict:
            regressions.append(f"{metric}: missing from {' and '.join(where)}")
        return bool(where)

    for metric in metrics_higher:
        if _missing(metric):
            continue
        current = scores[metric]
        recorded = baseline_metrics[metric]
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
        if _missing(metric):
            continue
        current = scores[metric]
        recorded = baseline_metrics[metric]
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


# TrOCR's language model hallucinates on 1-2 letter inputs ("by" read as
# "by being", a clear "a" scored 0.0), so the floor only counts words with
# at least this many letters when the word list is known.
OCR_FLOOR_MIN_LETTERS = 3


def check_ocr_min_gate(
    scores: dict, floor: float = 0.3, words: list[str] | None = None,
) -> tuple[bool, float | None]:
    """Return (passed, observed_min).

    Fails (False) when the worst-word OCR score is below the floor, which
    catches unreadable outputs that primary-metric deltas can miss. With
    ``words`` (aligned to ``scores["ocr_per_word"]``), words shorter than
    OCR_FLOOR_MIN_LETTERS letters are excluded.
    """
    per_word = scores.get("ocr_per_word")
    if words is not None and per_word is not None:
        kept = [
            a for a, w in zip(per_word, words)
            if len(w.strip(".,;:!?\"'")) >= OCR_FLOOR_MIN_LETTERS
        ]
        if not kept:
            return True, None
        ocr_min = min(kept)
        return ocr_min >= floor, float(ocr_min)
    ocr_min = scores.get("ocr_min")
    if ocr_min is None:
        return True, None
    return ocr_min >= floor, float(ocr_min)
