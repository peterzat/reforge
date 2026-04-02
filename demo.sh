#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

rm -f result.png

# Create and activate venv if needed
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install dependencies (quiet unless something changes)
pip install -q -r requirements.txt

# Generate handwritten note
python reforge.py \
    --style styles/hw-sample.png \
    --text "I can't remember exactly, but it was a Thursday; the bakery on Birchwood had croissants so perfect they'd disappear by noon.\nWe grabbed two, maybe three? Katherine laughed and said something wonderful about mornings being too beautiful for ordinary breakfast." \
    --output result.png \
    --preset quality

# Validate output exists
if [ ! -f "result.png" ]; then
    echo "ERROR: result.png not created" >&2
    exit 1
fi

# Print quality metrics, per-word OCR, and enforce quality gates
python3 -c "
import sys
import numpy as np
from PIL import Image
from reforge.evaluate.visual import overall_quality_score

img = Image.open('result.png')
size = __import__('os').path.getsize('result.png')

# Basic size checks
if img.width <= 100 or img.height <= 100:
    print('ERROR: Image too small', file=sys.stderr)
    sys.exit(1)
if size <= 10240:
    print('ERROR: File too small', file=sys.stderr)
    sys.exit(1)

arr = np.array(img.convert('L'))
scores = overall_quality_score(arr)

print()
print('Quality metrics:')
for k, v in scores.items():
    label = k.replace('_', ' ').title()
    if isinstance(v, float):
        print(f'  {label:30s} {v:.3f}')
    else:
        print(f'  {label:30s} {v}')
print()

# Quality gates
failed = []
if scores['overall'] <= 0.5:
    failed.append(f'overall quality {scores[\"overall\"]:.3f} <= 0.5')
if scores['gray_boxes'] < 1.0:
    failed.append('gray box artifacts detected')
if scores['ink_contrast'] <= 0.4:
    failed.append(f'ink contrast {scores[\"ink_contrast\"]:.3f} <= 0.4')
if 'ocr_accuracy' in scores and scores['ocr_accuracy'] < 0.6:
    failed.append(f'average OCR accuracy {scores[\"ocr_accuracy\"]:.3f} < 0.6')

if failed:
    print('QUALITY GATE FAILURES:', file=sys.stderr)
    for f in failed:
        print(f'  - {f}', file=sys.stderr)
    sys.exit(1)
print('All quality gates passed.')
"
