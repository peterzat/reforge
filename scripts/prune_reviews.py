"""Move stale human review JSON files out of the active review set.

A review is stale when any tracked pipeline file has changed since the
review was created (detected via SHA256 checksums stored in the review).

Reviews are ground truth and are never deleted: --apply moves them to
reviews/human/stale/ (tracked in git). Note that nearly every pipeline change
makes every review stale by this definition, and scripts that read
reviews/human/*.json (metric_correlation.py, findings_sweep.py) do not look in
stale/, so --apply also removes reviews from those analyses.

Usage:
    python scripts/prune_reviews.py          # dry-run (default)
    python scripts/prune_reviews.py --apply  # move to reviews/human/stale/
"""

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REVIEW_DIR = "reviews/human"
FINDINGS_PATH = os.path.join(REVIEW_DIR, "FINDINGS.md")


def main():
    parser = argparse.ArgumentParser(description="Prune stale human reviews")
    parser.add_argument(
        "--apply", action="store_true",
        help="Move stale reviews to reviews/human/stale/ (default is dry-run)",
    )
    args = parser.parse_args()

    from scripts.human_eval import compute_pipeline_checksums

    current_checksums = compute_pipeline_checksums()

    # Find review JSON files
    if not os.path.isdir(REVIEW_DIR):
        print("No reviews directory found.")
        return

    reviews = sorted([
        f for f in os.listdir(REVIEW_DIR)
        if f.endswith(".json") and not f.startswith(".")
    ])

    if not reviews:
        print("No reviews found.")
        return

    # Load FINDINGS.md for unextracted check
    findings_text = ""
    if os.path.exists(FINDINGS_PATH):
        with open(FINDINGS_PATH) as f:
            findings_text = f.read()

    stale = []
    for filename in reviews:
        path = os.path.join(REVIEW_DIR, filename)
        try:
            with open(path) as f:
                review = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: cannot read {filename}: {e}")
            continue

        saved = review.get("pipeline_checksums", {})
        changed = [p for p, h in current_checksums.items() if saved.get(p) != h]

        if changed:
            stale.append((path, filename, review, changed))

    if not stale:
        print("No stale reviews found.")
        return

    for path, filename, review, changed in stale:
        # Check if review has unextracted findings
        commit = review.get("commit", "")
        referenced = filename in findings_text or (commit and commit in findings_text)
        warn = ""
        if not referenced:
            warn = "  WARNING: may contain unextracted findings"

        n_changed = len(changed)
        if args.apply:
            stale_dir = os.path.join(REVIEW_DIR, "stale")
            os.makedirs(stale_dir, exist_ok=True)
            os.replace(path, os.path.join(stale_dir, filename))
            print(f"Moved to stale/: {filename} ({n_changed} file(s) changed){warn}")
        else:
            print(f"Would move to stale/: {filename} ({n_changed} file(s) changed){warn}")

    if not args.apply:
        print(f"\nDry run. Use --apply to move {len(stale)} stale review(s) to stale/.")
    else:
        print(f"\nMoved {len(stale)} stale review(s) to {REVIEW_DIR}/stale/.")


if __name__ == "__main__":
    main()
