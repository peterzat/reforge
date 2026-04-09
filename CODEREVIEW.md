## Review -- 2026-04-09 (commit: 844e31b)

**Summary:** Refresh review of 1 unpushed commit (844e31b) implementing spec criteria B (score cap fix), C (ragged right margin), D (test cleanup), plus new parameter optimality test infrastructure and documentation updates. Focus: 22 file(s) changed since prior review (commit 485f4db). 0 already-reviewed file(s) checked for interactions only.

**Review scope:** Refresh review. Focus: 22 file(s) changed since prior review (commit 485f4db). 0 already-reviewed file(s) checked for interactions only.

**External reviewers:**
None returned.

### Findings

1. [WARN] tests/medium/test_parameter_optimality.py:24 -- `DEFAULT_GUIDANCE_SCALE` was imported from `reforge.config` but never used. Dead import. **Auto-fixed.**

2. [NOTE] tests/medium/test_ab_harness.py:193 and tests/medium/test_quality_thresholds.py:213 -- The `if min(heights) > 0:` guard before the height ratio assertion means a zero-ink-height word would cause the test to pass silently. However, `compute_ink_height` guarantees a return value >= 1, so this guard never triggers in practice. Carried forward from prior review.

### Fixes Applied

1. Removed unused `DEFAULT_GUIDANCE_SCALE` import from test_parameter_optimality.py (WARN #1).

### Accepted Risks

None.

---
*Prior review (2026-04-09, commit 485f4db): Refresh review of uncommitted changes. 2 WARNs (stale docstrings in visual.py and layout.py), auto-fixed. 2 NOTEs (dead guard in height tests, false positive TypeError in ocr_per_word).*

<!-- REVIEW_META: {"date":"2026-04-09","commit":"844e31b","reviewed_up_to":"844e31bb748e8bb6b7649f5e01a49d4351297543","base":"origin/main","tier":"refresh","block":0,"warn":1,"note":1} -->
