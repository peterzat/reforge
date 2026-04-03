## Review -- 2026-04-03 (commit: 3c2e054)

**Summary:** Refresh review of 1 unpushed commit: finding-driven quality iteration loop (3c2e054). 24 focus-set files reviewed in full, including new modules (hard words watchlist, human eval system, stitch improvements) and updated documentation.

**Review scope:** Refresh review. Focus: 24 file(s) changed since prior review (commit 90343f1). 0 already-reviewed file(s) checked for interactions only.

### Findings

1. [WARN] CLAUDE.md:110,114,236 -- Eval type count says "7" but code has 8 (hard_words added in this commit). Listed evaluation types in CLAUDE.md omit hard_words.
   Evidence: `EVAL_TYPES` in human_eval.py has 8 entries; CLAUDE.md says "Seven structured evaluation types" and "7 eval types" in three places.
   Suggested fix: Update counts to 8 and add hard_words to the eval type list.

2. [WARN] reviews/human/FINDINGS.md:10 -- Status Summary shows "Active: 5" but manual count of findings with "Status: Active" yields 6 (quality score, ink weight, hard words gray box, baseline alignment, word sizing, composition illegibility).
   Evidence: Six "**Status:** Active" entries in the Findings section.
   Suggested fix: Update count to 6.

### Fixes Applied

1. Fixed eval type count and list in CLAUDE.md (WARN #1): updated "Seven" to "Eight", "7" to "8" in three places, added hard_words to evaluation types list.
2. Fixed human_eval.py docstring to include hard_words eval type (WARN #1).
3. Fixed FINDINGS.md Status Summary Active count from 5 to 6 (WARN #2).

All fixes verified: 151 quick tests pass (same count as baseline).

---
*Prior review (2026-04-02, commit 90343f1): Refresh review of word density spec and qpeek tool. 4 WARNs (stale docstring, dead constants, import placement), all auto-fixed.*

<!-- REVIEW_META: {"date":"2026-04-03","commit":"3c2e054","reviewed_up_to":"3c2e05441fbc0e5d4ab37c0a555e375021b42181","base":"origin/main","tier":"refresh","block":0,"warn":2,"note":0} -->
