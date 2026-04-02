"""Structured quality ledger: append-only JSONL recording of quality evaluations.

Each entry records timestamp, git state, all metric scores, gate results,
and config snapshot. This enables trend analysis across runs.
"""

import json
import os
import subprocess
from datetime import datetime, timezone


def _git_sha() -> str:
    """Get current git SHA, or 'unknown' if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def append_entry(
    ledger_path: str,
    scores: dict,
    config: dict | None = None,
    context: str = "",
) -> dict:
    """Append a quality evaluation entry to the ledger.

    Returns the entry dict that was written.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "context": context,
        "scores": {
            k: round(v, 4) if isinstance(v, float) else v
            for k, v in scores.items()
            if k not in ("gate_details",)  # skip non-serializable nested dicts
        },
        "gates_passed": scores.get("gates_passed", True),
        "config": config or {},
    }

    # Serialize gate_details separately (it's a dict of metric->bool)
    if "gate_details" in scores:
        entry["gate_details"] = scores["gate_details"]

    os.makedirs(os.path.dirname(ledger_path) or ".", exist_ok=True)
    with open(ledger_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def recent_runs(ledger_path: str, n: int = 10) -> list[dict]:
    """Return the last n entries from the ledger."""
    if not os.path.exists(ledger_path):
        return []
    entries = []
    with open(ledger_path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries[-n:]


def metric_trend(ledger_path: str, metric: str, n: int = 20) -> list[tuple[str, float]]:
    """Return (timestamp, value) pairs for a metric over the last n runs."""
    runs = recent_runs(ledger_path, n)
    result = []
    for run in runs:
        value = run.get("scores", {}).get(metric)
        if value is not None and isinstance(value, (int, float)):
            result.append((run["timestamp"], float(value)))
    return result
