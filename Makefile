.PHONY: test test-quick test-medium test-full test-regression test-ocr setup-hooks

test-quick:
	.venv/bin/python -m pytest tests/quick/ -x -q

test-medium:
	.venv/bin/python -m pytest tests/medium/ -x -q

test-full:
	.venv/bin/python -m pytest tests/full/ -x -s
	./demo.sh
	cp result.png docs/best-output.png
	./scripts/archive-output.sh || echo "Warning: output archive failed (non-fatal)"

test-regression:
	.venv/bin/python -m pytest tests/medium/test_quality_regression.py -x -s

test-ocr:
	.venv/bin/python -m pytest tests/medium/test_ocr_quality.py -x -s

test: test-medium

setup-hooks:
	./scripts/setup-hooks.sh
