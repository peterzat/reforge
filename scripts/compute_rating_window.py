"""Compute composition rating medians at several rolling-window sizes.

Reads every reviews/human/*.json file with a non-skipped composition rating,
sorts by review timestamp (ascending), and prints medians over the most-recent
{3, 5, 7, 10, all} reviews. Output is plain stdout and deterministic.

Used to decide whether the CLAUDE.md human-preference target window should
stay at last-5 or widen. See docs/rating_window_analysis.md.

Usage:
    python scripts/compute_rating_window.py
    python scripts/compute_rating_window.py --reviews-dir reviews/human
"""

import argparse
import glob
import json
import os
from statistics import median

WINDOWS = (3, 5, 7, 10)


def load_ratings(reviews_dir):
    files = sorted(glob.glob(os.path.join(reviews_dir, "*.json")))
    rows = []
    for path in files:
        try:
            with open(path) as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        comp = (data.get("evaluations") or {}).get("composition")
        if not comp or comp.get("skipped"):
            continue
        rating = comp.get("rating")
        if rating is None:
            continue
        timestamp = data.get("timestamp") or os.path.basename(path).rsplit(".", 1)[0]
        rows.append((timestamp, int(rating), os.path.basename(path)))
    rows.sort(key=lambda r: r[0])
    return rows


def compute_window_medians(ratings):
    out = []
    for n in WINDOWS:
        if len(ratings) < n:
            out.append((f"last-{n}", None, len(ratings)))
            continue
        window = ratings[-n:]
        out.append((f"last-{n}", median(window), n))
    out.append(("all", median(ratings) if ratings else None, len(ratings)))
    return out


def format_report(rows, windows):
    lines = []
    lines.append(f"Reviews with composition rating: {len(rows)}")
    lines.append("")
    lines.append("Per-review ratings (ascending by timestamp):")
    for ts, rating, fname in rows:
        lines.append(f"  {ts}  {rating}  {fname}")
    lines.append("")
    lines.append("Median by window:")
    lines.append(f"  {'window':<8} {'median':<8} {'n':<4}")
    for name, med, n in windows:
        med_s = "n/a" if med is None else f"{med:g}"
        lines.append(f"  {name:<8} {med_s:<8} {n:<4}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews-dir", default="reviews/human")
    args = parser.parse_args()

    rows = load_ratings(args.reviews_dir)
    ratings = [r[1] for r in rows]
    windows = compute_window_medians(ratings)
    print(format_report(rows, windows))


if __name__ == "__main__":
    main()
