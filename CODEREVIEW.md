## Review -- 2026-04-09 (commit: 485f4db)

**Summary:** Refresh review of uncommitted changes implementing spec criteria B (score cap rethinking), C (ragged right margin fix), D (test cleanup), plus new parameter optimality test infrastructure and documentation updates. Focus: 14 files changed since prior review (commit 5a33bda). 0 already-reviewed files checked for interactions only.

**Review scope:** Refresh review. Focus: 14 file(s) changed since prior review (commit 5a33bda). 0 already-reviewed file(s) checked for interactions only.

**External reviewers:**
[openai] o3 (high) -- 5360 in / 4796 out / 4608 reasoning -- ~$.0859

### Findings

1. [WARN] reforge/evaluate/visual.py:536-538 -- Docstring said "Unreadable words (OCR < 0.5) ... tank the overall score" but the behavior was changed from a hard 0.45 cap to a proportional penalty (`overall *= word_readability_rate`). The docstring misled callers about the severity of the penalty. **Auto-fixed.**

2. [WARN] reforge/compose/layout.py:147 -- Docstring said "5-20% shorter" but the implementation uses 0-5% for even lines and 8-18% for odd lines. The docstring was not updated when the ragged right range changed. **Auto-fixed.**

3. [NOTE] (openai) tests/medium/test_ab_harness.py:193 and tests/medium/test_quality_thresholds.py:213 -- The `if min(heights) > 0:` guard before the height ratio assertion means a zero-ink-height word would cause the test to pass silently. However, `compute_ink_height` guarantees a return value >= 1 (returns `max(1, ...)` or `img.shape[0]`), so this guard never triggers in practice. The guard is unnecessary but not harmful.

4. [NOTE] (openai) reforge/evaluate/visual.py:631 -- External reviewer flagged potential TypeError if `ocr_per_word` contains non-numeric entries. Verified as false positive: `_compute_ocr_scores` calls `ocr_accuracy()` which returns `float`, and wraps in `float()`. The `per_word` list only ever contains floats.

### Fixes Applied

1. Updated `overall_quality_score` docstring in visual.py to describe proportional penalty for unreadable words and hard cap for blank words separately (WARN #1).
2. Updated `compute_word_positions` docstring in layout.py to reflect actual ragged right range "0-18% shorter, alternating full/short" (WARN #2).

### Accepted Risks

None.

---
*Prior review (2026-04-04, commit 5a33bda): Refresh review of 2 commits. 1 WARN (unused import in stitch_chunks), auto-fixed. 2 NOTEs (missing x_height tests, diagnostic_results.json tracked).*

<!-- REVIEW_META: {"date":"2026-04-09","commit":"485f4db","reviewed_up_to":"485f4db4b40911e2cd603cedcd641a9ca2fe1937","base":"origin/main","tier":"refresh","block":0,"warn":2,"note":2} -->
