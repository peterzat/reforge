"""Structured experiment logging.

Records parameter changes, their outcomes, and lessons learned in
docs/experiment-log.jsonl. Enables future agent sessions to query
what has been tried and why.
"""

import json
import os
from datetime import datetime, timezone


DEFAULT_LOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "docs", "experiment-log.jsonl",
)


def log_experiment(
    area: str,
    change: str,
    expected: str,
    metrics_before: dict,
    metrics_after: dict,
    verdict: str,
    lesson: str,
    log_path: str = DEFAULT_LOG_PATH,
    date: str | None = None,
) -> dict:
    """Append an experiment outcome to the log.

    Args:
        area: Domain (e.g. "harmonization", "generation", "postprocessing").
        change: What was tried.
        expected: What we expected to happen.
        metrics_before: Metric values before the change.
        metrics_after: Metric values after the change.
        verdict: "keep", "revert", or "modify".
        lesson: What was learned.
        log_path: Path to the JSONL log file.
        date: ISO date string. Defaults to today.

    Returns the entry dict that was written.
    """
    entry = {
        "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "area": area,
        "change": change,
        "expected": expected,
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "verdict": verdict,
        "lesson": lesson,
    }

    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"Experiment logged [{verdict}]: {area} -- {change[:60]}")
    return entry


def query_experiments(
    area: str | None = None,
    verdict: str | None = None,
    log_path: str = DEFAULT_LOG_PATH,
) -> list[dict]:
    """Filter the experiment log by area and/or verdict.

    Returns matching entries in chronological order.
    """
    if not os.path.exists(log_path):
        return []

    results = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if area is not None and entry.get("area") != area:
                continue
            if verdict is not None and entry.get("verdict") != verdict:
                continue
            results.append(entry)

    return results
