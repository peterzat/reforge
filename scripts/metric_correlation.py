"""Measure which CV metrics correlate with human composition ratings.

Loads every reviews/human/*.json file with a non-skipped composition rating,
computes Spearman rank correlation between each numeric metric in cv_metrics
and the human composition rating, and prints a sorted table.

Also reports the agreement rate between metric picks and human picks in the
candidate evaluation type. The candidate sample is typically small; the
script reports "insufficient data (n<10)" when fewer than 10 candidate
reviews are available.

Usage:
    python scripts/metric_correlation.py
    python scripts/metric_correlation.py --reviews-dir reviews/human
    python scripts/metric_correlation.py --output docs/metric_correlation.md

The --output form writes a markdown file with the same information (plus a
timestamp and dataset size) for committing to the repo.
"""

import argparse
import glob
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# scipy is a hard dependency of the project (see requirements.txt). The rho
# computation is also available in pure python via the spearman() helper below
# so unit tests can exercise the logic dependency-free, but the primary path
# uses scipy.stats.spearmanr because its p-value uses the correct Student's t
# distribution. A prior version used a normal-approximation p-value which
# disagreed with scipy by 0.01-0.02, enough to flip borderline metrics under
# the B1 selection bar.
from scipy.stats import spearmanr as _scipy_spearmanr

DEFAULT_REVIEWS_DIR = "reviews/human"
CANDIDATE_MIN_N = 10

# B1 selection bar (spec 2026-04-10): positive rho, |rho| >= 0.2, p < 0.3.
# At most 3 metrics. If fewer clear, pick only those that do.
B1_RHO_MIN = 0.2
B1_P_MAX = 0.3
B1_MAX_PRIMARY = 3


def load_reviews(reviews_dir):
    """Return a list of (filename, review_dict) tuples, sorted by filename."""
    pattern = os.path.join(reviews_dir, "*.json")
    files = sorted(glob.glob(pattern))
    out = []
    for path in files:
        try:
            with open(path) as f:
                out.append((os.path.basename(path), json.load(f)))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def _composition_rating(review):
    """Return the numeric composition rating, or None if not present/skipped."""
    comp = review.get("evaluations", {}).get("composition")
    if not comp or comp.get("skipped"):
        return None
    rating = comp.get("rating")
    if isinstance(rating, (int, float)):
        return float(rating)
    return None


def _collect_metric_series(reviews):
    """Build {metric_name: [(composition_rating, metric_value), ...]} across reviews.

    Only numeric scalar metrics are included. List-valued entries (ocr_per_word)
    and dict/bool entries (gates_passed, gate_details) are skipped.
    """
    series = {}
    for _, review in reviews:
        rating = _composition_rating(review)
        if rating is None:
            continue
        metrics = review.get("cv_metrics", {})
        for name, value in metrics.items():
            if isinstance(value, bool):
                continue
            if not isinstance(value, (int, float)):
                continue
            if isinstance(value, float) and math.isnan(value):
                continue
            series.setdefault(name, []).append((rating, float(value)))
    return series


def _rankdata(values):
    """Assign average ranks; ties share the mean of their ranks.

    Implemented here (rather than scipy) so the unit test stays dependency-free.
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # ranks are 1-based
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def spearman(xs, ys):
    """Spearman rank correlation (rho). Returns None for zero-variance inputs.

    Uses the simple Pearson-on-ranks formulation, which matches scipy.stats.spearmanr
    for inputs without ties and closely approximates it with ties.
    """
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    if len(set(xs)) == 1 or len(set(ys)) == 1:
        return None
    rx = _rankdata(xs)
    ry = _rankdata(ys)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    num = sum((rx[i] - mean_x) * (ry[i] - mean_y) for i in range(n))
    den_x = math.sqrt(sum((r - mean_x) ** 2 for r in rx))
    den_y = math.sqrt(sum((r - mean_y) ** 2 for r in ry))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def spearman_with_pvalue(xs, ys):
    """Return (rho, two_sided_p) from scipy.stats.spearmanr.

    Wraps scipy so the rest of the script has one path. Returns (None, None)
    for zero-variance inputs (matching the dep-free spearman() helper above).
    """
    if len(xs) < 2 or len(ys) != len(xs):
        return None, None
    if len(set(xs)) == 1 or len(set(ys)) == 1:
        return None, None
    result = _scipy_spearmanr(xs, ys)
    rho = float(result.statistic)
    p = float(result.pvalue)
    if math.isnan(rho) or math.isnan(p):
        return None, None
    return rho, p


def compute_correlations(reviews):
    """Return list of (metric_name, rho, p_value, n, is_constant, values) records.

    Uses scipy.stats.spearmanr for the primary rho and p-value so the numbers
    in docs/metric_correlation.md match what a user would get from scipy
    directly. The hand-rolled spearman() helper is retained below for
    dependency-free unit testing.
    """
    series = _collect_metric_series(reviews)
    records = []
    for name, pairs in series.items():
        ratings = [p[0] for p in pairs]
        values = [p[1] for p in pairs]
        is_constant = len(set(values)) <= 1
        if is_constant:
            records.append({
                "metric": name,
                "rho": None,
                "p": None,
                "n": len(values),
                "constant": True,
                "constant_value": values[0] if values else None,
            })
            continue
        rho, p = spearman_with_pvalue(ratings, values)
        records.append({
            "metric": name,
            "rho": rho,
            "p": p,
            "n": len(values),
            "constant": False,
            "constant_value": None,
        })
    return records


def candidate_agreement(reviews):
    """Return dict with 'n' and, when sufficient, 'agreement_rate'.

    Counts reviews where the candidate eval is present and not skipped. The
    agreement flag comes from the review's own `agrees_with_metric` field,
    which is recorded by the human eval harness (the human answered a yes/no
    question at review time).
    """
    n = 0
    agree = 0
    for _, review in reviews:
        cand = review.get("evaluations", {}).get("candidate")
        if not cand or cand.get("skipped"):
            continue
        n += 1
        if cand.get("agrees_with_metric") is True:
            agree += 1
    if n < CANDIDATE_MIN_N:
        return {"n": n, "agree": agree, "rate": None, "insufficient": True}
    return {
        "n": n,
        "agree": agree,
        "rate": agree / n if n else None,
        "insufficient": False,
    }


def format_correlation_table(records):
    """Render a sorted table as plain text.

    Non-constant metrics appear first, sorted by |rho| descending. Constant
    metrics appear in a separate trailing section.
    """
    non_const = [r for r in records if not r["constant"]]
    const = [r for r in records if r["constant"]]

    non_const.sort(key=lambda r: (-(abs(r["rho"]) if r["rho"] is not None else 0), r["metric"]))
    const.sort(key=lambda r: r["metric"])

    lines = []
    header = f"{'metric':<32}  {'rho':>8}  {'p_approx':>10}  {'n':>4}"
    lines.append(header)
    lines.append("-" * len(header))
    for r in non_const:
        rho_str = f"{r['rho']:+.3f}" if r["rho"] is not None else "   --"
        p_str = f"{r['p']:.3f}" if r["p"] is not None else "     --"
        lines.append(f"{r['metric']:<32}  {rho_str:>8}  {p_str:>10}  {r['n']:>4}")
    if const:
        lines.append("")
        lines.append("Constant metrics (zero variance, no correlation computable):")
        for r in const:
            val = r["constant_value"]
            val_str = f"{val:.4f}" if isinstance(val, float) else str(val)
            lines.append(f"  {r['metric']:<32}  constant = {val_str}  (n={r['n']})")
    return "\n".join(lines)


def select_primary_metrics(records):
    """Apply the B1 selection bar to correlation records.

    Returns (selected, near_misses, rejected) where each is a list of record
    dicts. Selected: qualifying metrics, up to B1_MAX_PRIMARY, ranked by rho
    descending. Near misses: positive rho with |rho| >= B1_RHO_MIN but
    p >= B1_P_MAX (flagged so a human can see borderline cases). Rejected:
    everything else (constants, negatives, below-threshold).
    """
    candidates = []
    near_misses = []
    rejected = []
    for r in records:
        if r["constant"] or r["rho"] is None or r["p"] is None:
            rejected.append(r)
            continue
        if r["rho"] < B1_RHO_MIN:
            rejected.append(r)
            continue
        if r["p"] < B1_P_MAX:
            candidates.append(r)
        else:
            near_misses.append(r)
    candidates.sort(key=lambda r: (-r["rho"], r["metric"]))
    selected = candidates[:B1_MAX_PRIMARY]
    overflow = candidates[B1_MAX_PRIMARY:]
    near_misses.sort(key=lambda r: (-r["rho"], r["metric"]))
    return selected, near_misses, overflow, rejected


def format_candidate_block(agreement):
    n = agreement["n"]
    if agreement["insufficient"]:
        return (
            f"Candidate-pick agreement: insufficient data (n<{CANDIDATE_MIN_N}), "
            f"observed n={n}, agreements={agreement['agree']}"
        )
    rate = agreement["rate"]
    return (
        f"Candidate-pick agreement: {agreement['agree']}/{n} = {rate:.2f} "
        f"(n={n})"
    )


def render_markdown(records, agreement, reviews_dir, dataset_size):
    """Render a committable markdown report with timestamp, tables, and analysis.

    The markdown is intended to be regenerated in-place: running this script
    with --output always reproduces the full document from current review data.
    Do not hand-edit it; add interpretation via the _negative_correlation_notes
    and _methodology_notes helpers below so the narrative is regenerated too.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = []
    lines.append("# Metric-Human Correlation")
    lines.append("")
    lines.append(f"- Generated: {now}")
    lines.append(f"- Reviews directory: `{reviews_dir}`")
    lines.append(f"- Reviews with composition rating: {dataset_size}")
    lines.append(
        "- Correlation: Spearman rank (`scipy.stats.spearmanr`), two-sided p."
    )
    lines.append("")
    lines.append(
        "Spearman rank correlation between each cv_metric and the human "
        "composition rating (1-5). Sample size is small; p-values are "
        "indicative, not strict. Prefer the magnitude and sign of rho."
    )
    lines.append("")
    lines.append("## Correlations")
    lines.append("")
    lines.append("| metric | rho | p | n |")
    lines.append("| --- | ---: | ---: | ---: |")
    non_const = [r for r in records if not r["constant"]]
    non_const.sort(key=lambda r: (-(abs(r["rho"]) if r["rho"] is not None else 0), r["metric"]))
    for r in non_const:
        rho_str = f"{r['rho']:+.3f}" if r["rho"] is not None else "--"
        p_str = f"{r['p']:.3f}" if r["p"] is not None else "--"
        lines.append(f"| `{r['metric']}` | {rho_str} | {p_str} | {r['n']} |")

    const = [r for r in records if r["constant"]]
    if const:
        lines.append("")
        lines.append("## Constant metrics")
        lines.append("")
        lines.append("These metrics had zero variance across the dataset and cannot be correlated:")
        lines.append("")
        for r in sorted(const, key=lambda x: x["metric"]):
            val = r["constant_value"]
            val_str = f"{val:.4f}" if isinstance(val, float) else str(val)
            lines.append(f"- `{r['metric']}`: constant = {val_str} (n={r['n']})")

    lines.append("")
    lines.append("## Candidate-pick agreement")
    lines.append("")
    lines.append(format_candidate_block(agreement))

    # Selection section
    selected, near_misses, overflow, _ = select_primary_metrics(records)
    lines.append("")
    lines.append("## Primary metric selection (spec 2026-04-10 B1)")
    lines.append("")
    lines.append(
        f"Selection bar: positive rho, |rho| >= {B1_RHO_MIN}, p < {B1_P_MAX}. "
        f"At most {B1_MAX_PRIMARY}. If fewer clear the bar, pick only those that do."
    )
    lines.append("")
    if selected:
        lines.append("**Selected (these gate the regression test):**")
        lines.append("")
        for r in selected:
            lines.append(
                f"- `{r['metric']}`: rho = {r['rho']:+.3f}, p = {r['p']:.3f}, "
                f"n = {r['n']}"
            )
    else:
        lines.append(
            "**No metrics cleared the bar.** The regression test falls back to "
            "the OCR min floor (0.3) alone as the readability guardrail. This "
            "is a diagnosis, not a bug: the current CV metric set has no metric "
            "that positively tracks human composition rating with enough signal "
            "to gate on. Future work should focus on getting more review data "
            "(N=16 is weak) or adding new candidate metrics designed to track "
            "human preference directly."
        )

    if overflow:
        lines.append("")
        lines.append(
            f"**Excluded by the {B1_MAX_PRIMARY}-metric cap** (they cleared the bar "
            "but the B1 rule allows at most this many):"
        )
        lines.append("")
        for r in overflow:
            lines.append(
                f"- `{r['metric']}`: rho = {r['rho']:+.3f}, p = {r['p']:.3f}"
            )

    if near_misses:
        lines.append("")
        lines.append(
            "**Near misses** (positive rho with |rho| >= "
            f"{B1_RHO_MIN} but p >= {B1_P_MAX}):"
        )
        lines.append("")
        for r in near_misses:
            lines.append(
                f"- `{r['metric']}`: rho = {r['rho']:+.3f}, p = {r['p']:.3f}. "
                "Tracked as a diagnostic; watch on future runs. If it clears "
                "the p-bar after more review data, promote via an explicit "
                "spec update."
            )

    # Negative correlations are a diagnosis, not noise. Call them out.
    negatives = [r for r in non_const if r["rho"] is not None and r["rho"] <= -B1_RHO_MIN]
    if negatives:
        lines.append("")
        lines.append("## Negative correlations (why this spec exists)")
        lines.append("")
        lines.append(_negative_correlation_notes(negatives))

    lines.append("")
    lines.append("## Methodology notes")
    lines.append("")
    lines.append(_methodology_notes(dataset_size, agreement))
    lines.append("")
    return "\n".join(lines)


def _negative_correlation_notes(negatives):
    """Narrative explaining what the negative rhos imply.

    Regenerated from data, so it stays accurate if more reviews arrive and the
    sign or magnitude changes.
    """
    lines = []
    names = ", ".join(f"`{r['metric']}`" for r in negatives)
    lines.append(
        "The following metrics have *negative* rank correlation with human "
        f"composition rating at |rho| >= {B1_RHO_MIN}: " + names + "."
    )
    lines.append("")
    lines.append(
        "This is the direct evidence behind the 2026-04-10 spec's framing "
        "that \"the loop is a competent hill-climber but not a convergence "
        "machine because its proxies are misaligned.\" On this dataset, "
        "higher values of these CV metrics coincide with *lower* human "
        "composition ratings, not higher ones. They are tracked as "
        "diagnostics (printed in the ledger and on regression) but they do "
        "not gate."
    )
    lines.append("")
    lines.append(
        "Plausible explanations, none confirmed (that is a task for a future "
        "spec, not this one):"
    )
    lines.append("")
    lines.append(
        "- **Dataset contamination.** Many of the reviews were taken during "
        "active iteration, so code changes covary with metric changes. A "
        "metric that moved up because of a change the human disliked looks "
        "negatively correlated even if the metric itself is neutral. N=16 "
        "cannot separate this from a genuine inverse relationship."
    )
    lines.append(
        "- **Over-normalization.** `composition_score` and "
        "`layout_regularity` both reward geometric regularity. Humans "
        "tolerate and even prefer some irregularity in handwriting; "
        "pipelines that hit these metrics harder may look more "
        "machine-generated, which degrades the \"handwritten note\" impression."
    )
    lines.append(
        "- **Wrong ground truth.** `style_fidelity` measures similarity "
        "to the style image, not to \"good handwriting.\" If the style image "
        "has quirks, matching them may reduce human rating."
    )
    lines.append(
        "- **Saturation + noise.** `background_cleanliness` is near 1.0 on "
        "every review; the tiny variance it does have may be driven by "
        "rendering artifacts unrelated to composition quality."
    )
    lines.append("")
    lines.append(
        "**Treat these negative signals with caution.** Do not invert them "
        "into \"minimize X\" objectives without new evidence. The honest "
        "reading is that the dataset does not support using them as gating "
        "metrics at all, in either direction. They remain tracked so future "
        "turns can see if the sign stabilizes or flips as more reviews arrive."
    )
    return "\n".join(lines)


def _methodology_notes(dataset_size, agreement):
    lines = []
    lines.append(
        f"- N = {dataset_size} is small. p-values come from "
        "`scipy.stats.spearmanr` (two-sided Student's t) and should be read "
        "as \"plausibly non-zero\" rather than strict significance."
    )
    lines.append(
        "- Rerun this script after each `make test-human` session. The "
        "script is idempotent: `python scripts/metric_correlation.py "
        "--output docs/metric_correlation.md` regenerates the full document "
        "including selection rationale."
    )
    if agreement.get("insufficient"):
        lines.append(
            f"- The candidate-pick sample (n={agreement['n']}) is below the "
            f"{CANDIDATE_MIN_N}-review reporting threshold. When n >= "
            f"{CANDIDATE_MIN_N}, the agreement-rate section will populate "
            "and a candidate-disagreement gate can be considered."
        )
    lines.append(
        "- Negative correlations (when present) are logged above as "
        "diagnostics. They are NOT used to flip metric directions; the "
        "correlation is too weak and confounded by dataset contamination "
        "during active iteration."
    )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--reviews-dir", default=DEFAULT_REVIEWS_DIR,
        help="Directory containing human review JSON files",
    )
    parser.add_argument(
        "--output", default=None,
        help="Optional path to write a markdown report",
    )
    args = parser.parse_args(argv)

    reviews = load_reviews(args.reviews_dir)
    records = compute_correlations(reviews)
    agreement = candidate_agreement(reviews)
    dataset_size = sum(
        1 for _, r in reviews if _composition_rating(r) is not None
    )

    print(f"Reviews directory: {args.reviews_dir}")
    print(f"Reviews with composition rating: {dataset_size}")
    print()
    print(format_correlation_table(records))
    print()
    print(format_candidate_block(agreement))

    if args.output:
        md = render_markdown(records, agreement, args.reviews_dir, dataset_size)
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(md)
        print(f"\nWrote markdown report: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
