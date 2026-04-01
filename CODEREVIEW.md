## Review -- 2026-04-01 (commit: b17efe0)

**Review scope:** Refresh review. Focus: 4 code files changed since prior review (commit 067f996). 1 already-reviewed file (docs/OUTPUT_HISTORY.md) checked for interactions only.

**Summary:** One unpushed commit tightens height harmonization to achieve word_height_ratio >= 0.95: percentile-based height ratio metric for 10+ words, scale-to-median instead of scale-to-threshold, and 105%/93% band. One WARN found and auto-fixed: CLAUDE.md referenced "92%" in two places but config.py was changed to 0.93 (93%).

### Findings

[WARN] CLAUDE.md:264,371 -- Documentation referenced "92%" undersize threshold but config.py `HEIGHT_UNDERSIZE_THRESHOLD` was changed to 0.93 (93%) in this commit. The prior review updated these lines from 80% to 92%, but the config was then bumped to 93% without updating CLAUDE.md.
  Evidence: CLAUDE.md line 264: "scale UP words <92%"; config.py line 51: `HEIGHT_UNDERSIZE_THRESHOLD = 0.93`
  Suggested fix: Applied -- updated both CLAUDE.md references to 93%.

[NOTE] tests/quick/test_stroke_weight.py:45,64 and tests/quick/test_tier1_metrics.py:60 -- Test docstrings still reference the old 120%/80% thresholds. These are pre-existing (not modified in this commit). The test logic itself uses actual word images that trigger the thresholds correctly regardless of the docstring wording, so the tests are still valid.

### Fixes Applied

1. `CLAUDE.md` -- Updated two references from 92% to 93% to match current `HEIGHT_UNDERSIZE_THRESHOLD = 0.93` in config.py.

---
*Prior review (2026-04-01, commit 067f996): Refresh review of output quality spec (27 files). 2 WARNs auto-fixed: stale threshold docstrings in harmonize.py/CLAUDE.md, unused imports in render.py. 1 NOTE: compute_margins() defined and tested but unused in production.*

<!-- REVIEW_META: {"date":"2026-04-01","commit":"b17efe0","reviewed_up_to":"b17efe081cb6547d212e8e6ea97a12be22719c1b","base":"origin/main","tier":"refresh","block":0,"warn":1,"note":1} -->
