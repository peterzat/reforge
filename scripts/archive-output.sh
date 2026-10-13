#!/usr/bin/env bash
# Archive the current demo output with metadata for historical tracking.
# Called by Makefile after updating docs/best-output.png.
#
# Creates:
#   docs/output-history/<timestamp>.png   -- copy of the output image
#   Appends an entry to docs/OUTPUT_HISTORY.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

HISTORY_DIR="docs/output-history"
HISTORY_MD="docs/OUTPUT_HISTORY.md"
SOURCE="docs/best-output.png"

if [ ! -f "$SOURCE" ]; then
    echo "ERROR: $SOURCE not found" >&2
    exit 1
fi

mkdir -p "$HISTORY_DIR"

# Find the most recent archived image (lexicographic sort = chronological for YYYYMMDD-HHMMSS)
LATEST_ARCHIVE="$(ls "$HISTORY_DIR"/*.png 2>/dev/null | sort | tail -1 || true)"

# Skip if the new image is nearly identical to the latest archive.
# Uses mean absolute pixel difference; threshold of 3.0 (out of 255) catches
# visually identical images even if PNG compression differs.
if [ -n "$LATEST_ARCHIVE" ]; then
    IS_DUPLICATE="$(.venv/bin/python3 -c "
import numpy as np
from PIL import Image

new = Image.open('$SOURCE').convert('L')
old = Image.open('$LATEST_ARCHIVE').convert('L')

# Resize both to a common size for comparison (handles different dimensions
# from threshold tuning iterations that produce near-identical output)
common_size = (400, 400)
new_arr = np.array(new.resize(common_size), dtype=np.float32)
old_arr = np.array(old.resize(common_size), dtype=np.float32)

mad = np.mean(np.abs(new_arr - old_arr))
print('yes' if mad < 3.0 else 'no')
" 2>/dev/null || echo 'no')"

    if [ "$IS_DUPLICATE" = "yes" ]; then
        echo "Output unchanged from latest archive ($(basename "$LATEST_ARCHIVE")), skipping."
        exit 0
    fi
fi

# Skip if HEAD commit hasn't changed since the last archive. Stochastic
# generation means pixel-dedup won't catch re-runs of demo.sh at the same
# code state. Extract the commit from the most recent OUTPUT_HISTORY.md entry.
if [ -f "$HISTORY_MD" ]; then
    COMMIT_SHORT="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
    LAST_ARCHIVED_COMMIT="$(grep -m1 '| Git state |' "$HISTORY_MD" \
        | grep -oP '`\K[a-f0-9]+' || true)"
    if [ "$COMMIT_SHORT" = "$LAST_ARCHIVED_COMMIT" ]; then
        echo "HEAD ($COMMIT_SHORT) matches latest archive, skipping. Use --force to override."
        if [ "${1:-}" != "--force" ]; then
            exit 0
        fi
    fi
fi

# Timestamp for the filename
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE_NAME="${TIMESTAMP}.png"
cp "$SOURCE" "$HISTORY_DIR/$ARCHIVE_NAME"

# Git state: closest commit + dirty flag
COMMIT_SHORT="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
COMMIT_MSG="$(git log -1 --format='%s' 2>/dev/null || echo '')"
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    GIT_STATE="${COMMIT_SHORT} (uncommitted changes)"
else
    GIT_STATE="${COMMIT_SHORT}"
fi

# Style input used (default hw-sample.png, note for future multi-style support)
STYLE_INPUT="styles/hw-sample.png"

# Quality metrics come from the run manifest demo.sh writes next to
# result.png (seed, sizing policy, metrics computed with word images and
# texts). Before 2026-10-13 this block copied the frozen regression baseline
# for "Quick brown foxes jump high", so every entry listed the same numbers.
MANIFEST="result.json"
METRICS="$(.venv/bin/python3 -c "
import json, os
tracked = ('overall', 'height_outlier_score', 'baseline_alignment',
           'stroke_weight_consistency', 'ocr_accuracy', 'ocr_min',
           'word_readability_rate', 'style_fidelity')
if not os.path.exists('$MANIFEST'):
    print('metrics unavailable (no run manifest)')
else:
    m = json.load(open('$MANIFEST'))
    q = m.get('quality', {})
    parts = [f'{k}={q[k]:.3f}' for k in tracked if isinstance(q.get(k), (int, float))]
    head = f\"seed={m.get('seed')}, sizing={m.get('sizing_policy')}\"
    print(head + (', ' + ', '.join(parts) if parts else ''))
" 2>/dev/null || echo 'metrics unavailable')"

# Initialize history file if it doesn't exist
if [ ! -f "$HISTORY_MD" ]; then
    cat > "$HISTORY_MD" << 'HEADER'
# Output History

Historical record of demo output quality over time. Each entry captures the
generated image, git state, quality metrics, and style input used. Newest first.

See [README](../README.md) for current output and project overview.

---

HEADER
fi

# Build the new entry
ENTRY="## ${TIMESTAMP}

![output](output-history/${ARCHIVE_NAME})

| Field | Value |
|-------|-------|
| Git state | \`${GIT_STATE}\` |
| Commit message | ${COMMIT_MSG} |
| Style input | \`${STYLE_INPUT}\` |
| Metrics | ${METRICS} |

---

"

# Insert the new entry after the header separator (first "---" line after the preamble).
# The header ends at the first "---" on its own line. We insert after that.
# Use python for reliable multi-line insertion.
.venv/bin/python3 -c "
import sys

entry = sys.stdin.read()
with open('$HISTORY_MD', 'r') as f:
    content = f.read()

# Find the end of the header block (first '---' line after non-empty content)
lines = content.split('\n')
insert_idx = None
found_content = False
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped and not stripped.startswith('#'):
        found_content = True
    if found_content and stripped == '---':
        insert_idx = i + 1
        break

if insert_idx is None:
    # No header separator found, append to end
    content = content.rstrip() + '\n\n' + entry.rstrip() + '\n'
else:
    # Insert after header separator, before existing entries
    before = '\n'.join(lines[:insert_idx])
    after = '\n'.join(lines[insert_idx:]).lstrip('\n')
    content = before + '\n\n' + entry.rstrip() + '\n\n' + after
    content = content.rstrip() + '\n'

with open('$HISTORY_MD', 'w') as f:
    f.write(content)
" <<< "$ENTRY"

echo "Archived output: $HISTORY_DIR/$ARCHIVE_NAME"
