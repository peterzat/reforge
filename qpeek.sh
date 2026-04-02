#!/usr/bin/env bash
# Quick-peek wrapper: view a file in the browser from this headless box.
# Usage: ./qpeek.sh result.png
#        ./qpeek.sh result.png --ask "How does it look?" --choices "good,bad,meh"
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/.venv/bin/python" -m qpeek "$@"
