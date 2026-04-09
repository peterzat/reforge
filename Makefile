.PHONY: test test-quick test-medium test-full test-regression test-ocr test-hard test-human test-tuning setup-hooks review

test-quick:
	.venv/bin/python -m pytest tests/quick/ -x -q

test-medium:
	.venv/bin/python -m pytest tests/medium/ -x -q

test-full:
	.venv/bin/python -m pytest tests/full/ -x -s
	./demo.sh
	cp result.png docs/best-output.png
	./scripts/archive-output.sh || echo "Warning: output archive failed (non-fatal)"
	@.venv/bin/python3 -c "import sys; sys.path.insert(0,'.'); from scripts.human_eval import check_staleness; s,r = check_staleness(); print('\n  Human review stale: ' + r + '. Run: make test-human\n') if s else None" 2>/dev/null || true

test-regression:
	.venv/bin/python -m pytest tests/medium/test_quality_regression.py -x -s

test-ocr:
	.venv/bin/python -m pytest tests/medium/test_ocr_quality.py -x -s

test: test-medium

review:
	./demo.sh
	@.venv/bin/python3 -c "\
	import numpy as np; \
	from PIL import Image; \
	from reforge.evaluate.visual import overall_quality_score; \
	img = Image.open('result.png'); \
	arr = np.array(img.convert('L')); \
	scores = overall_quality_score(arr); \
	print(); \
	print('=== Quality Review ==='); \
	print(f'Image: result.png ({img.width}x{img.height})'); \
	print(f'Aspect ratio: {img.width/img.height:.2f}:1'); \
	print(); \
	print('Metrics:'); \
	[print(f'  {k:30s} {v:.3f}' if isinstance(v, float) else f'  {k:30s} {v}') for k, v in scores.items()]; \
	print(); \
	print('Demo text: The morning sun cast long shadows across the quiet garden...'); \
	print('Style: styles/hw-sample.png'); \
	print(); \
	print('To review: paste this output and result.png into a Claude conversation.'); \
	"

test-hard:
	.venv/bin/python -m pytest tests/medium/test_hard_words.py -x -s

test-tuning:
	.venv/bin/python -m pytest tests/medium/test_parameter_optimality.py -x -s

test-human:
	@mkdir -p reviews/human/images
	.venv/bin/python scripts/human_eval.py $(if $(EVAL),--eval $(EVAL))

setup-hooks:
	./scripts/setup-hooks.sh
