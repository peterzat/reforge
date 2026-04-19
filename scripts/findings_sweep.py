"""Detect unprocessed human-review JSON files relative to FINDINGS.md.

Read-only utility. Prints a summary of any review JSONs that have not yet
been folded into ``reviews/human/FINDINGS.md``, followed by the current
FINDINGS.md contents. Exits 0 if everything is processed, 1 otherwise.

A review counts as unprocessed when its filename stem (e.g. ``2026-04-19_215858``)
sorts strictly *after* FINDINGS.md's ``FINDINGS_LAST_PROCESSED`` marker. The
marker is an HTML comment at the top of FINDINGS.md::

    <!-- FINDINGS_LAST_PROCESSED: 2026-04-19_215858 -->

Whoever processes a review into FINDINGS.md is responsible for bumping the
marker to that review's stem in the same edit. The stem is lexically sortable
because it uses ``YYYY-MM-DD_HHMMSS`` format.

If the marker is absent, every review is reported as unprocessed so the first
run surfaces everything and forces a bootstrap.

The script does not call any LLM, modify files, or launch qpeek. It is a data
dump intended for consumption by ``/spec`` (see the Findings workflow section
of ``CLAUDE.md``) or for ad-hoc preview via ``make findings-sweep``.

Usage::

    .venv/bin/python scripts/findings_sweep.py [--quiet-findings]

``--quiet-findings`` suppresses the final FINDINGS.md dump (useful when the
caller already has it loaded).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW_DIR = ROOT / "reviews" / "human"
FINDINGS_PATH = REVIEW_DIR / "FINDINGS.md"

TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")
MARKER_RE = re.compile(
    r"<!--\s*FINDINGS_LAST_PROCESSED:\s*(\d{4}-\d{2}-\d{2}_\d{6})\s*-->"
)


def _review_files() -> list[Path]:
    if not REVIEW_DIR.is_dir():
        return []
    return sorted(
        p for p in REVIEW_DIR.glob("*.json")
        if not p.name.startswith(".") and TIMESTAMP_RE.match(p.stem)
    )


def _last_processed(findings_text: str) -> str | None:
    m = MARKER_RE.search(findings_text)
    return m.group(1) if m else None


def _summarize(path: Path) -> str:
    with path.open() as f:
        data = json.load(f)

    lines: list[str] = []
    lines.append(f"  commit:    {data.get('commit', '?')}")
    lines.append(f"  timestamp: {data.get('timestamp', '?')}")
    evaluations = data.get("evaluations", {}) or {}
    if not evaluations:
        lines.append("  evaluations: (none)")
        return "\n".join(lines)

    for name, payload in evaluations.items():
        if not isinstance(payload, dict):
            continue
        if payload.get("skipped"):
            lines.append(f"  {name}: (skipped)")
            continue
        rating = payload.get("rating", "?")
        defects = payload.get("defects") or []
        head = f"  {name}: rating {rating}/5"
        if defects:
            head += f"  defects={list(defects)}"
        lines.append(head)
        notes = (payload.get("notes") or "").strip()
        if notes:
            for i, chunk in enumerate(_wrap(notes, 72)):
                prefix = "    notes: " if i == 0 else "           "
                lines.append(prefix + chunk)
    return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    out: list[str] = []
    for line in text.splitlines() or [text]:
        line = line.rstrip()
        while len(line) > width:
            cut = line.rfind(" ", 0, width)
            if cut <= 0:
                cut = width
            out.append(line[:cut])
            line = line[cut:].lstrip()
        out.append(line)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--quiet-findings", action="store_true",
        help="Suppress the FINDINGS.md dump at the end of output.",
    )
    args = parser.parse_args()

    if not FINDINGS_PATH.is_file():
        print(f"ERROR: FINDINGS.md not found at {FINDINGS_PATH}", file=sys.stderr)
        return 2

    findings_text = FINDINGS_PATH.read_text()
    marker = _last_processed(findings_text)
    reviews = _review_files()

    if marker is None:
        unprocessed = reviews
        marker_note = "no marker found (run first-time bootstrap)"
    else:
        unprocessed = [p for p in reviews if p.stem > marker]
        marker_note = f"last processed {marker}"

    print(f"FINDINGS.md: {FINDINGS_PATH.relative_to(ROOT)}")
    print(f"Reviews scanned: {len(reviews)}")
    print(f"Marker: {marker_note}")
    print(f"Unprocessed: {len(unprocessed)}")
    print()

    if not unprocessed:
        print("Nothing to process. FINDINGS.md is up to date.")
        return 0

    for p in unprocessed:
        rel = p.relative_to(ROOT)
        print(f"--- {rel} ---")
        try:
            print(_summarize(p))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  (unreadable: {exc})")
        print()

    if not args.quiet_findings:
        print("=" * 72)
        print("Current FINDINGS.md follows. Draft the update against its")
        print("structure, present the diff in the terminal for user ack, then")
        print("bump the FINDINGS_LAST_PROCESSED marker in the same edit.")
        print("=" * 72)
        print()
        print(findings_text)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
