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
# Uses mean absolute pixel difference; threshold of 1.0 (out of 255) catches
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

# Quality metrics: prefer the regression baseline (comprehensive, trustworthy)
# over re-scoring the composed image (which lacks word_imgs/words context).
BASELINE_FILE="tests/medium/quality_baseline.json"
METRICS="$(.venv/bin/python3 -c "
import json, os

baseline_path = '$BASELINE_FILE'
tracked = ('overall', 'composition_score', 'stroke_weight_consistency',
           'word_height_ratio', 'ocr_accuracy', 'style_fidelity',
           'ink_contrast', 'background_cleanliness')

if os.path.exists(baseline_path):
    with open(baseline_path) as f:
        data = json.load(f)
    # New format (spec 2026-04-10 C3): per-seed entries under 'seeds'.
    # Read the reference seed (42) with a fallback to the legacy flat
    # 'metrics' key for backward compatibility.
    metrics = (
        data.get('seeds', {}).get('42', {}).get('metrics')
        or data.get('metrics', {})
    )
    parts = []
    for k in tracked:
        if k in metrics:
            v = metrics[k]
            if isinstance(v, float):
                parts.append(f'{k}={v:.3f}')
            else:
                parts.append(f'{k}={v}')
    if parts:
        print(', '.join(parts))
    else:
        print('metrics unavailable (empty baseline)')
else:
    # Fall back to image-only scoring (no word_imgs context)
    import numpy as np
    from PIL import Image
    from reforge.evaluate.visual import overall_quality_score
    img = Image.open('$SOURCE')
    arr = np.array(img.convert('L'))
    scores = overall_quality_score(arr)
    parts = []
    for k in tracked:
        if k in scores:
            v = scores[k]
            if isinstance(v, float):
                parts.append(f'{k}={v:.3f}')
            else:
                parts.append(f'{k}={v}')
    print(', '.join(parts) + ' (image-only, no baseline)')
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
