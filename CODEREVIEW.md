## Review -- 2026-04-02 (commit: 2978355)

**Summary:** QA infrastructure overhaul: gate/continuous scoring split in `overall_quality_score`, SSIM reference comparison for pixel-level regression detection, quality ledger (append-only JSONL), A/B baseline floors, new quick tests for all new evaluation functions. 11 files changed across config, evaluate modules, and tests.

### Findings

```
[BLOCK] reforge/evaluate/visual.py:513 -- overall_quality_score returns 0.5 when no continuous metrics available
  Evidence: When called with only img (no word_imgs/word_positions), no continuous
  metrics are populated, so weight_total=0 and overall defaults to 0.5. demo.sh
  (line 52) calls overall_quality_score(arr) without word data, and its gate
  (line 66) checks `scores['overall'] <= 0.5`, which trips on exactly 0.5.
  make test-full runs demo.sh, so this breaks the full test tier.
  Suggested fix: Fall back to mean of gate metric scores when no continuous
  metrics are available.
```

```
[WARN] tests/medium/test_quality_regression.py:251 -- duplicate GPU generation in regression tests
  Evidence: test_no_metric_regression and test_pixel_level_regression both call
  _generate_test_words() independently, each generating 5 words on GPU with
  identical seed. The output is deterministic, so the second call duplicates
  ~7s of GPU work. A class-scoped fixture sharing the result would halve
  regression test runtime.
  Suggested fix: Extract _generate_test_words result into a class-scoped
  fixture or module-level cache. Not auto-fixed because it requires
  restructuring test setup.
```

### Fixes Applied

- **BLOCK fix (visual.py:513):** Changed the `weight_total == 0` fallback from returning 0.5 to computing the mean of available gate metric scores. This matches the old behavior (mean of available component scores) and prevents demo.sh from hitting the `<= 0.5` quality gate on clean output. Quick tests (133/133) pass after fix.

---
*Prior review (2026-04-01, commit b2bf61d): Refresh review of A1 revert. No issues found.*

<!-- REVIEW_META: {"date":"2026-04-02","commit":"2978355","reviewed_up_to":"2978355e675856f2f6c0718515c96e5770c43863","base":"origin/main","tier":"full","block":1,"warn":1,"note":0} -->
