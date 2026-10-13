#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

rm -f result.png result.json

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
    --preset quality \
    --seed 42

# Validate output exists
if [ ! -f "result.png" ]; then
    echo "ERROR: result.png not created" >&2
    exit 1
fi

# Print quality metrics, per-word OCR, and enforce quality gates. Metrics come
# from the run manifest (result.json), which the pipeline computes with the
# word images and texts in hand; re-scoring the PNG alone cannot run OCR.
python3 -c "
import json, os, sys
from PIL import Image

img = Image.open('result.png')
size = os.path.getsize('result.png')

# Basic size checks
if img.width <= 100 or img.height <= 100:
    print('ERROR: Image too small', file=sys.stderr)
    sys.exit(1)
if size <= 10240:
    print('ERROR: File too small', file=sys.stderr)
    sys.exit(1)

with open('result.json') as f:
    manifest = json.load(f)
scores = manifest['quality']

print()
print(f\"Quality metrics (seed {manifest['seed']}, sizing {manifest['sizing_policy']}):\")
for k, v in scores.items():
    label = k.replace('_', ' ').title()
    if isinstance(v, float):
        print(f'  {label:30s} {v:.3f}')
    elif not isinstance(v, (list, dict)):
        print(f'  {label:30s} {v}')
low = [(w, a) for w, a in zip(manifest['words'], scores.get('ocr_per_word', [])) if a < 0.5]
if low:
    print('  Low-OCR words: ' + ', '.join(f'{w} ({a:.2f})' for w, a in low))
print()

# Quality gates
failed = []
if scores['overall'] <= 0.5:
    failed.append(f'overall quality {scores[\"overall\"]:.3f} <= 0.5')
if scores['gray_boxes'] < 1.0:
    failed.append('gray box artifacts detected')
if scores['ink_contrast'] <= 0.4:
    failed.append(f'ink contrast {scores[\"ink_contrast\"]:.3f} <= 0.4')
if 'ocr_accuracy' not in scores:
    failed.append('OCR accuracy unavailable')
elif scores['ocr_accuracy'] < 0.6:
    failed.append(f'average OCR accuracy {scores[\"ocr_accuracy\"]:.3f} < 0.6')

if failed:
    print('QUALITY GATE FAILURES:', file=sys.stderr)
    for f in failed:
        print(f'  - {f}', file=sys.stderr)
    sys.exit(1)
print('All quality gates passed.')
"
