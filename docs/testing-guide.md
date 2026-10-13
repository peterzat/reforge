# Testing guide

Moved from CLAUDE.md on 2026-10-13. CLAUDE.md keeps the commands and the
gating rules; TESTING.md holds the periodic test-strategy review.

## Three tiers

| Tier | Directory | Runtime | GPU | Purpose |
|------|-----------|---------|-----|---------|
| Quick | `tests/quick/` | <10s | No | Component logic: segmentation, normalization, sizing, scoring, harmonization, charset, gray-box detection, syllable splitting, baseline detection and placement, punctuation routing, gate logic. All models mocked. |
| Medium | `tests/medium/` | ~4 min | Yes | Regression gate, A/B quality harnesses, OCR, hard words, contraction sizing, parameter optimality, diagnostics. Skips without GPU. |
| Full | `tests/full/` | <10 min | Yes | E2E pipeline: real weights, real style image, real output. Visual output saved to `tests/full/output/`. |

`conftest.py` implements a tier DAG: a medium run includes the quick tier, a
full run includes both. All tiers share one pytest process, so no module may
change global torch state at import (see docs/compute-strategy.md).

Test fixtures are generated inline with numpy (there is no fixtures
directory). When a test reproduces a bug seen on real output, build the
synthetic image from the measured profile of the real word (see
`tests/quick/test_baseline.py::TestBaselineFailureModesFromRealOutput`) and
confirm the test fails on the old code before keeping it.

## Regression gate (`tests/medium/test_quality_regression.py`)

- Words: the five style words plus `was so on by it` (short words of each
  letter class), seeds 42/137/2718, fast preset (20 steps, CFG 3.0), one
  candidate, deterministic cuDNN.
- Topology: `generate_word` -> `pipeline.postprocess_words` -> `compose_words`,
  the same stage graph as production.
- Gating: `PRIMARY_METRICS` (`x_height_consistency`) must not drop more than
  0.05 below the per-seed baseline on any seed, checked strictly (missing in
  scores or baseline = failure); OCR floor 0.3 on words of 3+ letters; SSIM
  >= 0.80 against `reference_output.png`. Everything else is a diagnostic.
- Baselines change only deliberately:
  `pytest tests/medium/test_quality_regression.py --update-baseline --update-reference -x -s`.
  A baseline recorded for a different word list fails with that instruction.

## CV evaluation functions (`reforge/evaluate/visual.py`)

Validity status matters more than the list: see docs/metric_correlation.md.

| Function | Measures | Status |
|----------|----------|--------|
| `check_x_height_consistency(word_imgs, words)` | all-body word body size vs. long-word x-height | Gating. Matches the 3/3 human A/B direction. |
| `check_gray_boxes(img)` | rectangular gray artifacts | Gate in `overall` (constant 1.0 on recent output) |
| `check_ink_contrast(img)` | ink-to-background contrast | Gate in `overall` |
| `check_background_cleanliness(img)` | non-white non-ink pixels | Gate in `overall` |
| `check_stroke_weight_consistency(word_imgs)` | cross-word ink median spread | Diagnostic |
| `check_word_height_ratio(word_imgs)` | max/min total ink height | Diagnostic; rewards equal total height, which zone sizing gives up |
| `compute_height_outlier_ratio(word_imgs)` | max/median total ink height | Diagnostic; did not replicate on held-out reviews |
| `check_baseline_consistency(word_imgs, positions, words)` | placed ink baselines vs line median | Diagnostic; clean 0.92 vs jitter canary 0.63-0.65 |
| `check_word_gap_ratio(word_imgs, positions)` | median inter-word ink gap in x-heights | Diagnostic measurement; clean ~0.8-0.9 |
| `check_baseline_alignment(img, positions)` | canvas bottoms, not ink baselines | Retired in practice (ignores `img`); still in `overall` at 0.05 pending a weights decision |
| `compute_style_similarity` / `style_fidelity` | similarity to style crops | One third is `_xheight_ratio`, ~1.0 for nearly every word |
| OCR (`ocr_accuracy`, `ocr_min`, `word_readability_rate`) | TrOCR-small character accuracy (`REFORGE_OCR_BACKEND=vlm` for the local VLM reader) | Hallucinates on 1-2 letter words; no reader detects misspelled renderings (docs/cv-instruments.md) |
| `overall_quality_score(...)` | weighted composite + gates | Diagnostic composite |

## Autonomous quality loop

1. Write the expected outcome first (docs/experiment-log.jsonl `expected`).
2. Change a parameter or postprocessing approach.
3. For compose/sizing/post-processing changes, replay cached generations so
   both arms share identical words; otherwise use seeded runs.
4. Run `make test-quick`, then `make test-regression`.
5. Look at the output (Claude Code reads PNGs). Metrics alone have been gamed
   before ("The" -> "Tle" at word_height_ratio 1.00).
6. Keep or revert, and log the outcome against the expectation.

## pytest markers

```ini
[pytest]
markers =
    quick: component tests, mocked, <10s
    medium: A/B harness tests, optional GPU, <2min
    full: e2e tests, requires GPU + model weights, <10min
    gpu: requires CUDA GPU
```

## Hard words watchlist

`reforge/data/hard_words.json` tracks words that are difficult for the
generation pipeline. Two tiers: **curated** (verified hard words, the
regression baseline) and **candidates** (automatically collected, awaiting
triage).

Candidates are added automatically when the OCR rejection loop in
`generate_word()` exhausts retries without reaching 0.4 accuracy; from human
eval nominations in `hard_words` review notes; or by editing the JSON.

Triage: `python -m reforge.data.words triage` reviews candidates and promotes
or dismisses them (manual).

`make test-hard` generates every curated word, runs OCR, and asserts average
accuracy > 0.5, recording to `tests/medium/hard_words_ledger.jsonl`.
