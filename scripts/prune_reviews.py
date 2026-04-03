"""Prune stale human review JSON files.

A review is stale when any tracked pipeline file has changed since the
review was created (detected via SHA256 checksums stored in the review).

Usage:
    python scripts/prune_reviews.py          # dry-run (default)
    python scripts/prune_reviews.py --apply  # actually delete
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
        help="Actually delete stale reviews (default is dry-run)",
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
            os.remove(path)
            print(f"Deleted: {filename} ({n_changed} file(s) changed){warn}")
        else:
            print(f"Would delete: {filename} ({n_changed} file(s) changed){warn}")

    if not args.apply:
        print(f"\nDry run. Use --apply to delete {len(stale)} stale review(s).")
    else:
        print(f"\nDeleted {len(stale)} stale review(s).")


if __name__ == "__main__":
    main()
