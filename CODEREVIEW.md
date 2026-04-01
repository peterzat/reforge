## Review -- 2026-04-01 (commit: 067f996)

**Review scope:** Refresh review. Focus: 27 files changed since prior review (commit 8227b0f). 1 already-reviewed file (docs/OUTPUT_HISTORY.md) checked for interactions only.

**Summary:** Large commit implementing the output quality spec: tighter height harmonization (105%/92% thresholds replacing 120%/80%), dynamic page sizing targeting near-square aspect ratio, proportional margins, generation presets (draft/fast/quality), style fidelity metric, composition score, style similarity tiebreaker in best-of-N selection, six experiment sweep scripts, and new CLI arguments (--preset, --page-ratio). Tests updated (119 quick passing). Two WARNs found and auto-fixed: stale docstrings referencing old 120%/80% thresholds in harmonize.py and CLAUDE.md, and unused imports (MARGIN_V_RATIO, compute_margins) in render.py. One NOTE: compute_margins() in layout.py is defined and tested but not used by any production code path. Security: 0 BLOCK / 0 WARN / 0 NOTE.

### Findings

[WARN] reforge/quality/harmonize.py:4,67-68 -- Docstrings referenced old 120%/80% thresholds. Config was changed to 1.05 (105%) and 0.92 (92%) but docstrings were not updated. CLAUDE.md lines 264 and 371 also referenced the old values.
  Evidence: Module docstring line 4: "scale DOWN outliers > 120% of median". Function docstring lines 67-68: "Scale DOWN words above HEIGHT_OUTLIER_THRESHOLD (120%) of median." Config.py line 50-51: `HEIGHT_OUTLIER_THRESHOLD = 1.05`, `HEIGHT_UNDERSIZE_THRESHOLD = 0.92`.
  Suggested fix: Applied -- updated docstrings to reference the config constants by name (no hardcoded percentages), updated CLAUDE.md to reference 105%/92%.

[WARN] reforge/compose/render.py:15,20 -- Unused imports: `MARGIN_V_RATIO` from config and `compute_margins` from layout. The compose_words() function computes margins inline (lines 67-68, 117-119) rather than calling compute_margins().
  Evidence: `grep -n MARGIN_V_RATIO render.py` returns only the import line. `grep -n compute_margins render.py` returns only the import line.
  Suggested fix: Applied -- removed both unused imports.

[NOTE] reforge/compose/layout.py:80-95 -- `compute_margins()` is defined, exported, and tested in test_layout.py, but not called by any production code. render.py computes the same margins inline. The function could either replace the inline computation in render.py or be removed. Leaving in place since the test coverage is a positive signal and the function may be useful for future callers.

### Fixes Applied

1. `reforge/quality/harmonize.py` -- Updated module docstring and harmonize_heights() docstring to reference config constants by name instead of hardcoded 120%/80% values.
2. `reforge/compose/render.py` -- Removed unused imports of `MARGIN_V_RATIO` and `compute_margins`.
3. `CLAUDE.md` -- Updated two references from 120%/80% to 105%/92% to match current config values.

---
*Prior review (2026-04-01, commit 8227b0f): Refresh review. No issues found. 1 unpushed commit made output archive non-fatal in test-full target.*

<!-- REVIEW_META: {"date":"2026-04-01","commit":"067f996","reviewed_up_to":"067f996476e9263da4a0634bca654f1318a7f549","base":"origin/main","tier":"refresh","block":0,"warn":2,"note":1} -->
