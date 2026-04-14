"""Candidate scoring preference analysis.

Reads all review JSON files from reviews/human/, extracts candidate eval data
(human pick vs. metric pick, agreement), and reports:
- Agreement rate
- Per-candidate pick distribution
- Recommendations for improving candidate scoring

D1/D2 acceptance criteria for spec 2026-04-14.
"""

import json
import glob
import sys
from collections import Counter
from pathlib import Path


def load_candidate_evals(review_dir: str = "reviews/human") -> list[dict]:
    """Load candidate evaluation data from all review JSON files."""
    files = sorted(glob.glob(f"{review_dir}/*.json"))
    evals = []
    for f in files:
        try:
            data = json.load(open(f))
        except (json.JSONDecodeError, FileNotFoundError):
            continue

        evaluations = data.get("evaluations", {})
        if not isinstance(evaluations, dict):
            continue

        candidate = evaluations.get("candidate")
        if candidate is None or candidate.get("skipped", True):
            continue

        evals.append({
            "file": Path(f).name,
            "timestamp": data.get("timestamp", ""),
            "pick": candidate.get("pick"),
            "agrees_with_metric": candidate.get("agrees_with_metric", False),
            "notes": candidate.get("notes", ""),
            "cv_metrics": data.get("cv_metrics", {}),
        })

    return evals


def analyze(evals: list[dict]) -> dict:
    """Analyze candidate evaluation data."""
    n = len(evals)
    if n == 0:
        return {"error": "No candidate evaluations found."}

    agreements = sum(1 for e in evals if e["agrees_with_metric"])
    disagreements = n - agreements

    picks = Counter(e["pick"] for e in evals if e["pick"])

    # Check for per-candidate score data (sub-scores per candidate)
    has_per_candidate_scores = False
    for e in evals:
        candidate_data = e.get("candidate_scores")
        if candidate_data and isinstance(candidate_data, dict):
            has_per_candidate_scores = True
            break

    return {
        "n_reviews": n,
        "agreements": agreements,
        "disagreements": disagreements,
        "agreement_rate": agreements / n if n > 0 else 0,
        "pick_distribution": dict(picks.most_common()),
        "has_per_candidate_scores": has_per_candidate_scores,
    }


def format_report(analysis: dict) -> str:
    """Format the analysis as a human-readable report."""
    lines = []
    lines.append("# Candidate Scoring Preference Analysis")
    lines.append("")

    if "error" in analysis:
        lines.append(f"Error: {analysis['error']}")
        return "\n".join(lines)

    n = analysis["n_reviews"]
    agreements = analysis["agreements"]
    rate = analysis["agreement_rate"]

    lines.append(f"## Summary")
    lines.append("")
    lines.append(f"- Total candidate reviews: {n}")
    lines.append(f"- Human-metric agreements: {agreements}/{n} ({rate:.0%})")
    lines.append(f"- Human-metric disagreements: {analysis['disagreements']}/{n} ({1-rate:.0%})")
    lines.append("")

    lines.append(f"## Human Pick Distribution")
    lines.append("")
    for pick, count in sorted(analysis["pick_distribution"].items()):
        lines.append(f"- Candidate {pick}: {count} time(s)")
    lines.append("")

    lines.append("## Per-Candidate Score Data")
    lines.append("")
    if analysis["has_per_candidate_scores"]:
        lines.append("Per-candidate scores are available. Logistic regression or")
        lines.append("score reweighting can be attempted.")
    else:
        lines.append("**No per-candidate score breakdowns are recorded in the review data.**")
        lines.append("")
        lines.append("The current review system records only:")
        lines.append("- Which candidate the human picked (A-E)")
        lines.append("- Whether the human agreed with the metric's pick (boolean)")
        lines.append("")
        lines.append("To perform sub-score correlation analysis (D2), the review")
        lines.append("system would need to record, for each candidate:")
        lines.append("- Individual sub-scores (background, ink_density, edge_sharpness,")
        lines.append("  height_consistency, contrast, OCR accuracy)")
        lines.append("- The metric's combined score and rank")
        lines.append("- The style similarity tiebreak score (if applicable)")
    lines.append("")

    lines.append("## Assessment")
    lines.append("")

    if rate < 0.3:
        lines.append(f"Agreement rate is {rate:.0%}, well below chance (20% for 5 candidates).")
        lines.append("This suggests the current scoring features are measuring something")
        lines.append("orthogonal or inversely related to human preference. Simple reweighting")
        lines.append("of the existing features is unlikely to fix this.")
        lines.append("")
        lines.append("**Recommendation:** The existing quality_score features (background,")
        lines.append("ink_density, edge_sharpness, height_consistency, contrast) may be")
        lines.append("measuring 'image cleanliness' rather than 'handwriting quality.'")
        lines.append("Before attempting reweighting:")
        lines.append("")
        lines.append("1. Add per-candidate score logging to the review system so each")
        lines.append("   candidate's sub-scores are recorded alongside the human pick.")
        lines.append("2. Collect at least 15 reviews with per-candidate scores.")
        lines.append("3. Then run sub-score correlation analysis to identify which")
        lines.append("   features (if any) predict human preference.")
        lines.append("4. If no existing features correlate positively, consider VGG-based")
        lines.append("   perceptual features (HWD) as described in the research survey.")
    elif rate < 0.5:
        lines.append(f"Agreement rate is {rate:.0%}, near chance level.")
        lines.append("The metric is not reliably predicting human preference but is not")
        lines.append("systematically wrong either. Reweighting may help.")
    else:
        lines.append(f"Agreement rate is {rate:.0%}, above chance.")
        lines.append("The metric has some predictive value. Reweighting may improve it further.")

    lines.append("")
    lines.append("## Data Requirements for D2 (Score Reweighting)")
    lines.append("")
    min_n_for_logistic = 50
    min_n_for_simple = 15
    lines.append(f"- Simple reweighting (rank features by agreement): N >= {min_n_for_simple}")
    lines.append(f"  Current N = {n}. {'Sufficient.' if n >= min_n_for_simple else f'Need {min_n_for_simple - n} more reviews.'}")
    lines.append(f"- Logistic regression (5 features): N >= {min_n_for_logistic}")
    lines.append(f"  Current N = {n}. {'Sufficient.' if n >= min_n_for_logistic else f'Need {min_n_for_logistic - n} more reviews.'}")
    lines.append("")
    lines.append("**Critical prerequisite:** Per-candidate sub-scores must be logged")
    lines.append("in the review JSON. Without them, no reweighting is possible")
    lines.append("regardless of N.")

    return "\n".join(lines)


def main():
    review_dir = "reviews/human"
    if len(sys.argv) > 1:
        review_dir = sys.argv[1]

    evals = load_candidate_evals(review_dir)
    analysis = analyze(evals)
    report = format_report(analysis)
    print(report)

    # Also write to a file for reference
    output_path = Path("docs/candidate_scoring_analysis.md")
    output_path.write_text(report + "\n")
    print(f"\nReport written to {output_path}")


if __name__ == "__main__":
    main()
