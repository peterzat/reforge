## Review -- 2026-04-02 (commit: 90343f1)

**Summary:** Refresh review of 2 unpushed commits: word density / ragged margin spec implementation (ece0378) and qpeek visual inspection tool (90343f1). 13 focus-set files reviewed in full; 1 already-reviewed file (.claude/settings.local.json) checked for interactions only.

**Review scope:** Refresh review. Focus: 13 file(s) changed since prior review (commit e0ae42a). 1 already-reviewed file(s) checked for interactions only.

### Findings

1. [WARN] reforge/evaluate/visual.py:387 -- Stale docstring in `check_composition_score`. Docstring said "Aspect ratio proximity to 1.0 (0.7-1.3 range is ideal)" but the code now targets 0.75 with a 0.55-0.95 range.
   Evidence: Docstring not updated when code changed to portrait aspect ratio target.
   Suggested fix: Update docstring to match code.

2. [WARN] reforge/config.py:98-100 -- Dead constants `TARGET_ASPECT_RATIO`, `TARGET_ASPECT_MIN`, `TARGET_ASPECT_MAX` defined but never imported anywhere. The old `compute_page_width` used these; the new implementation uses `TARGET_WORDS_PER_LINE` instead.
   Evidence: `grep -r TARGET_ASPECT` finds only config.py and SPEC.md (prose).
   Suggested fix: Remove unused constants.

3. [WARN] reforge/config.py:49 -- Dead constant `LONG_WORD_AREA_TARGET` defined but never imported. `font_scale.py` computes the long-word target as `int(SHORT_WORD_HEIGHT_TARGET * 1.1)` directly.
   Evidence: `grep -r LONG_WORD_AREA_TARGET` finds only config.py.
   Suggested fix: Remove unused constant.

4. [WARN] reforge/compose/layout.py:53 -- `import math` moved from module-level to inside function body in a conditional block. Stdlib imports belong at module level per Python convention; the deferred import here adds no benefit since `math` has no import cost.
   Evidence: `import math` was previously at the top of the file (removed in this diff), re-added inside `compute_page_width` in a `if usable > 0` block.
   Suggested fix: Move `import math` back to module level.

### Fixes Applied

1. Fixed stale docstring in `check_composition_score` (WARN #1).
2. Removed dead constants `TARGET_ASPECT_RATIO`, `TARGET_ASPECT_MIN`, `TARGET_ASPECT_MAX` from config.py (WARN #2).
3. Removed dead constant `LONG_WORD_AREA_TARGET` from config.py (WARN #3).
4. Moved `import math` back to module level in layout.py (WARN #4).

All fixes verified: 151 quick tests pass (same count as baseline).

---
*Prior review (2026-04-02, commit e0ae42a): Refresh review of dead-code removal in compose/render.py. 0 BLOCK, 0 WARN, 0 NOTE.*

<!-- REVIEW_META: {"date":"2026-04-02","commit":"90343f1","reviewed_up_to":"90343f1c512a88e614306e62ece721a71eff4a3e","base":"origin/main","tier":"refresh","block":0,"warn":4,"note":0} -->
