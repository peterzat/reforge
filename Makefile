.PHONY: test test-quick test-medium test-full test-regression test-ocr test-hard test-human test-tuning setup-hooks review findings-sweep

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
	@echo
	@echo "Image: result.png    Run manifest (seed, settings, metrics): result.json"
	@echo "To review: open result.png in Claude Code (it reads images directly) or ./qpeek.sh result.png"

test-hard:
	.venv/bin/python -m pytest tests/medium/test_hard_words.py -x -s

test-tuning:
	.venv/bin/python -m pytest tests/medium/test_parameter_optimality.py -x -s

test-human:
	@mkdir -p reviews/human/images
	REFORGE_LOG_CANDIDATES=$(if $(EVAL),$(if $(findstring candidate,$(EVAL)),1,),1) \
	.venv/bin/python scripts/human_eval.py $(if $(EVAL),--eval $(EVAL))

setup-hooks:
	./scripts/setup-hooks.sh

findings-sweep:
	.venv/bin/python scripts/findings_sweep.py
