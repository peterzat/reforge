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
    --text "The morning sun cast long shadows across the quiet garden. Birds sang their familiar songs while dew drops sparkled on fresh green leaves.\nShe sat near the old stone wall, reading her favorite book. The pages felt warm and soft under her fingers." \
    --output result.png \
    --steps 50 \
    --guidance-scale 3.0 \
    --candidates 3

# Print quality metrics
python3 -c "
import numpy as np
from PIL import Image
from reforge.evaluate.visual import overall_quality_score

img = np.array(Image.open('result.png').convert('L'))
scores = overall_quality_score(img)
print()
print('Quality metrics:')
for k, v in scores.items():
    label = k.replace('_', ' ').title()
    if isinstance(v, float):
        print(f'  {label:30s} {v:.3f}')
    else:
        print(f'  {label:30s} {v}')
print()
"

# Validate output
if [ ! -f "result.png" ]; then
    echo "ERROR: result.png not created" >&2
    exit 1
fi

python3 -c "
from PIL import Image
import os, sys
img = Image.open('result.png')
size = os.path.getsize('result.png')
if img.width <= 100 or img.height <= 100:
    print('ERROR: Image too small', file=sys.stderr)
    sys.exit(1)
if size <= 10240:
    print('ERROR: File too small', file=sys.stderr)
    sys.exit(1)
"
