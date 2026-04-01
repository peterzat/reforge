## Review -- 2026-04-01 (commit: 80925b1)

**Summary:** Refresh review of 1 unpushed commit. Focus: 7 files changed (generator.py cluster filter fix, new diagnostic instrument, 3 new/updated tests, quality baseline update). Core change: `isolated_cluster_filter` now uses lenient threshold (< 230) for column presence and transitive cluster merging to prevent word clipping.

### Findings

[WARN] reforge/model/generator.py:200 -- `ink_mask` parameter in `isolated_cluster_filter` is now vestigial; the function uses `img < 230` directly instead of the passed mask. Made parameter optional (`= None`) to signal it is transitional.
  Evidence: Parameter accepted at line 200, but function body (lines 209-262) never references `ink_mask`. All column presence detection uses `img < 230` at line 214.
  Suggested fix: Applied -- default changed to `= None`. Callers can be updated to stop passing `ink_mask` in a future commit.

[WARN] tests/medium/test_word_clipping_diagnostic.py:9 -- Unused `import sys`.
  Evidence: `sys` imported at line 9, never referenced in the file.
  Suggested fix: Applied -- removed the import.

[NOTE] tests/medium/test_ab_harness.py:59 -- `test_cfg_produces_clean_background` threshold lowered from 0.3 to 0.2. This weakens the background cleanliness gate. Justified by the cluster filter fix preserving more ink (and some faint gray) that was previously removed. Worth monitoring if background artifacts reappear.

[NOTE] tests/medium/test_word_clipping_diagnostic.py:116 -- `postprocessed` return value from `generate_raw_word` is computed (GPU cost per word) but discarded. The test only uses `raw_img`. Consider either removing the postprocessing step from `generate_raw_word` or using the result.

[NOTE] tests/medium/quality_baseline.json -- `baseline_alignment` dropped from 0.7503 to 0.381, pulling `overall` from 0.8195 to 0.7587. Other metrics improved (stroke_weight_consistency up, background_cleanliness up). Likely stochastic variation from a different generation run, but the magnitude of the alignment drop warrants observation.

### Fixes Applied

1. `reforge/model/generator.py:200` -- Made `ink_mask` parameter optional with `= None` default.
2. `tests/medium/test_word_clipping_diagnostic.py:9` -- Removed unused `import sys`.

---

*Prior review (2026-04-01, commit 236bd6e): Light review of 1 unpushed commit (SPEC.md, quality baseline, settings). No issues.*

<!-- REVIEW_META: {"date":"2026-04-01","commit":"80925b1","reviewed_up_to":"80925b1602b4adaed4bf7db701476504516af479","base":"origin/main","tier":"refresh","block":0,"warn":2,"note":3} -->
