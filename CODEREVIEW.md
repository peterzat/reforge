## Review -- 2026-04-01 (commit: c16cd4a)

**Review scope:** Refresh review. Focus: 18 files changed since prior review (commit 80925b1). 0 already-reviewed files (all files in the full unpushed set were also in the focus set).

**Summary:** Two unpushed commits: unified height normalization replacing the old dual (height+area) strategy, bidirectional harmonization (scale up undersized words), Makefile with targeted test targets, pre-commit hook, setup-hooks script, README expansion, CLAUDE.md loop cadence docs, and quality baseline update reflecting improved metrics. Core code changes are correct and well-tested. Three WARN findings, all stale documentation/dead code from the strategy change, all auto-fixed.

### Findings

[WARN] reforge/quality/font_scale.py:11 -- Vestigial import and dead code from old area-based normalization. `LONG_WORD_AREA_TARGET` was imported but unused in code. `compute_ink_area()` was defined but never called. Docstring referenced "derived from LONG_WORD_AREA_TARGET" but the code used `SHORT_WORD_HEIGHT_TARGET * 1.1`. Internal comment block (lines 40-44) described an area-based derivation that no longer applied.
  Evidence: `from reforge.config import LONG_WORD_AREA_TARGET, SHORT_WORD_HEIGHT_TARGET` at line 11; `def compute_ink_area` at line 14 with zero callers; code at line 50 uses `int(SHORT_WORD_HEIGHT_TARGET * 1.1)`.
  Suggested fix: Applied -- removed import, removed dead function, updated docstring and comment.

[WARN] reforge/quality/harmonize.py:4 -- Module docstring contradicts code. Said "never scale up" but the code now scales up words below 80% of median height.
  Evidence: Line 4: `Height: scale DOWN outliers > 120% of median height (never scale up).` vs. lines 88-90 which scale up undersized words.
  Suggested fix: Applied -- updated docstring to reflect bidirectional harmonization.

[WARN] README.md:105 -- Font normalization description outdated. Said "uses a dual strategy" and "normalized by ink area per character to 550 px^2". Code now uses unified height-based normalization.
  Evidence: Line 105 text vs. `normalize_font_size()` in font_scale.py which uses height targets for all word lengths.
  Suggested fix: Applied -- updated to describe unified height strategy.

[NOTE] reforge/config.py:37 -- `LONG_WORD_AREA_TARGET = 550` is defined but no longer imported by any module. It is dead configuration. Left in place since config constants are low-risk and the value documents the old strategy for reference. Can be removed in a cleanup pass.

[NOTE] Makefile:12 -- `test-full` unconditionally runs `cp result.png docs/best-output.png`, updating the README image on every full test run regardless of whether quality improved. This is a side effect on the working tree. Acceptable given the current single-developer workflow where the developer reviews and commits changes.

### Fixes Applied

1. `reforge/quality/font_scale.py` -- Removed vestigial `LONG_WORD_AREA_TARGET` import, removed dead `compute_ink_area()` function, updated docstring to reference `SHORT_WORD_HEIGHT_TARGET * 1.1`, replaced misleading area-derivation comment with concise explanation.
2. `reforge/quality/harmonize.py:4` -- Updated module docstring from "never scale up" to "scale DOWN outliers > 120% of median, scale UP undersized < 80% of median."
3. `README.md:105` -- Replaced "dual strategy" / "ink area per character" description with unified height strategy description matching current code.

---
*Prior review (2026-04-01, commit 80925b1): Refresh review of cluster filter fix and diagnostic test. 2 WARNs (vestigial ink_mask parameter, unused sys import), both auto-fixed. 3 NOTEs (threshold loosening, discarded postprocessed value, baseline alignment drop).*

<!-- REVIEW_META: {"date":"2026-04-01","commit":"c16cd4a","reviewed_up_to":"c16cd4a27b6604dd2964c737c372abc418c2a71f","base":"origin/main","tier":"refresh","block":0,"warn":3,"note":2} -->
