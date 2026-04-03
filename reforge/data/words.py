"""Hard words watchlist: load, query, and manage difficult-to-generate words.

The watchlist lives in reforge/data/hard_words.json with two tiers:
- curated: manually verified hard words (the regression baseline)
- candidates: automatically collected from OCR failures and human eval

Usage as CLI:
    python -m reforge.data.words triage    # review and promote candidates
"""

import json
import os
import sys
import tempfile
from datetime import datetime

_DATA_DIR = os.path.dirname(__file__)
_HARD_WORDS_PATH = os.path.join(_DATA_DIR, "hard_words.json")


def _load_file() -> dict:
    """Load hard_words.json, returning empty structure on failure."""
    try:
        with open(_HARD_WORDS_PATH) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"schema_version": 1, "curated": [], "candidates": []}
        return data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: could not load {_HARD_WORDS_PATH}: {e}", file=sys.stderr)
        return {"schema_version": 1, "curated": [], "candidates": []}


def _save_file(data: dict) -> None:
    """Atomically write hard_words.json (write to temp, rename)."""
    fd, tmp_path = tempfile.mkstemp(
        dir=_DATA_DIR, prefix=".hard_words_", suffix=".json",
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, _HARD_WORDS_PATH)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_hard_words() -> list[str]:
    """Return curated hard words as a list of strings."""
    data = _load_file()
    return [entry["word"] for entry in data.get("curated", [])]


def load_candidates() -> list[dict]:
    """Return candidate entries (dicts with word, source, timestamp, ocr_accuracy)."""
    data = _load_file()
    return data.get("candidates", [])


def add_candidate(word: str, source: str, ocr_accuracy: float | None = None) -> bool:
    """Append a candidate to hard_words.json. Returns True if added, False if duplicate.

    Atomic file write prevents corruption from concurrent pipeline runs.
    Skips if word already exists in curated or candidates.
    """
    data = _load_file()

    # Check for duplicates
    curated_words = {e["word"].lower() for e in data.get("curated", [])}
    candidate_words = {e["word"].lower() for e in data.get("candidates", [])}
    if word.lower() in curated_words or word.lower() in candidate_words:
        return False

    entry = {
        "word": word,
        "source": source,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    if ocr_accuracy is not None:
        entry["ocr_accuracy"] = round(ocr_accuracy, 4)

    data.setdefault("candidates", []).append(entry)
    _save_file(data)
    return True


# ---------------------------------------------------------------------------
# Triage CLI (B3)
# ---------------------------------------------------------------------------

def _triage():
    """Interactive triage of candidate hard words."""
    data = _load_file()
    candidates = data.get("candidates", [])

    if not candidates:
        print("No candidates to triage.")
        return

    # Group by source
    by_source = {}
    for c in candidates:
        src = c.get("source", "unknown")
        by_source.setdefault(src, []).append(c)

    # Count nominations per word
    word_counts = {}
    for c in candidates:
        w = c["word"]
        word_counts[w] = word_counts.get(w, 0) + 1

    print(f"\n{len(candidates)} candidate(s) from {len(by_source)} source(s):\n")

    for source, entries in sorted(by_source.items()):
        print(f"  Source: {source} ({len(entries)} entries)")
        # Deduplicate for display
        seen = {}
        for e in entries:
            w = e["word"]
            if w not in seen:
                seen[w] = e
        for w, e in sorted(seen.items()):
            acc = e.get("ocr_accuracy")
            acc_str = f"  OCR: {acc:.3f}" if acc is not None else ""
            count = word_counts[w]
            count_str = f"  ({count}x)" if count > 1 else ""
            print(f"    {w:20s}{acc_str}{count_str}")
        print()

    print("For each candidate, enter: [p]romote, [d]ismiss, [s]kip")
    print("Promote adds to curated list. Dismiss removes. Skip leaves for later.\n")

    promoted = []
    dismissed = []
    unique_words = list(dict.fromkeys(c["word"] for c in candidates))

    for word in unique_words:
        while True:
            choice = input(f"  {word}? [p/d/s]: ").strip().lower()
            if choice in ("p", "d", "s"):
                break
            print("    Enter p, d, or s")

        if choice == "p":
            promoted.append(word)
        elif choice == "d":
            dismissed.append(word)

    # Apply changes
    if not promoted and not dismissed:
        print("\nNo changes.")
        return

    # Remove promoted and dismissed from candidates
    remove_words = set(w.lower() for w in promoted + dismissed)
    data["candidates"] = [
        c for c in data["candidates"]
        if c["word"].lower() not in remove_words
    ]

    # Add promoted to curated
    today = datetime.now().strftime("%Y-%m-%d")
    for word in promoted:
        # Find best OCR accuracy from candidates for the reason
        best_acc = None
        source = "triage"
        for c in candidates:
            if c["word"] == word:
                acc = c.get("ocr_accuracy")
                if acc is not None and (best_acc is None or acc < best_acc):
                    best_acc = acc
                source = c.get("source", "triage")

        reason = f"Promoted from candidates (source: {source}"
        if best_acc is not None:
            reason += f", best OCR: {best_acc:.3f}"
        reason += ")"

        data["curated"].append({
            "word": word,
            "category": "promoted",
            "reason": reason,
            "added": today,
        })

    _save_file(data)

    if promoted:
        print(f"\nPromoted {len(promoted)}: {', '.join(promoted)}")
    if dismissed:
        print(f"Dismissed {len(dismissed)}: {', '.join(dismissed)}")
    remaining = len(data["candidates"])
    print(f"Remaining candidates: {remaining}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m reforge.data.words triage")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "triage":
        _triage()
    else:
        print(f"Unknown command: {cmd}")
        print("Available: triage")
        sys.exit(1)


if __name__ == "__main__":
    main()
