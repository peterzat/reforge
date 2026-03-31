#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

rm -f result.png

echo "=== reforge demo ==="

# Create and activate venv if needed
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Generate handwritten note
echo "Generating handwritten note..."
python reforge.py \
    --style styles/hw-sample.png \
    --text "The morning sun cast long shadows across the quiet garden. Birds sang their familiar songs while dew drops sparkled on fresh green leaves.\nShe sat near the old stone wall, reading her favorite book. The pages felt warm and soft under her fingers." \
    --output result.png \
    --steps 50 \
    --guidance-scale 3.0 \
    --candidates 3

# Validate output
echo "Validating output..."

if [ ! -f "result.png" ]; then
    echo "ERROR: result.png not created"
    exit 1
fi

# Check dimensions and file size
python3 -c "
from PIL import Image
import os
import sys

img = Image.open('result.png')
size = os.path.getsize('result.png')

print(f'Dimensions: {img.width}x{img.height}')
print(f'File size: {size} bytes')
print(f'Mode: {img.mode}')

if img.width <= 100 or img.height <= 100:
    print('ERROR: Image too small')
    sys.exit(1)
if size <= 10240:
    print('ERROR: File too small')
    sys.exit(1)

print('Validation passed.')
"

# Print quality metrics
echo "Quality metrics:"
python3 -c "
import numpy as np
from PIL import Image
from reforge.evaluate.visual import overall_quality_score

img = np.array(Image.open('result.png'))
scores = overall_quality_score(img)
for k, v in scores.items():
    print(f'  {k}: {v:.3f}')
"

echo "=== Demo complete. Output: result.png ==="
