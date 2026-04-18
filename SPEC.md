## Spec -- 2026-04-18 -- Option E: full-word DP for contractions

**Goal:** Remove the `is_contraction()` split-and-overlay path and let DP render contractions ("can't", "don't", "it's", "they'd") as single words, relying on the existing OCR-rejection retry loop as the only safety net. Review 2026-04-18_154757 showed seed 2718 producing a visually clean native `can't` with no overlay, and the hard-words ledger showed OCR 0.8-1.0 on the four common contractions at seed 42 on the prior baseline. The split path underperforms 0.5 OCR on single-character right-side parts ("cantt" / "itss" duplicate-letter defect); the overlay path regressed composition to 2/5 by stacking marks on DP's native apostrophe ink. Option E trades both known failure modes for a leaner code path that may beat both.

### Acceptance Criteria

- [ ] 1. `is_contraction()` dispatch is removed from `generate_word()` in `reforge/model/generator.py`. Contractions flow through the same generation path as any other word.
- [ ] 2. `is_contraction`, `split_contraction`, `make_synthetic_apostrophe`, `stitch_contraction`, and any supporting helpers exclusively used by them are deleted from the codebase (not merely bypassed by a flag or conditional). `experiments/diagnose_contraction.py` (a throwaway diagnostic for the "cantt" failure mode that imports all four functions at lines 28-37) is also deleted; without the functions it imports, the script would fail at import time and has no standalone value.
- [ ] 3. Contraction-specific unit tests in `tests/quick/` that targeted the deleted functions are removed (17 `def test_` functions in `tests/quick/test_contraction.py`). One smoke test remains or is added: `generate_word("can't", ...)` returns valid output under mocked generation.
- [ ] 4. `CLAUDE.md`'s eval-type-to-code-area mapping for the `punctuation` row (line 231) is updated to reflect the new path: `stitch_contraction` and `make_synthetic_apostrophe` no longer exist and must be replaced with the live code areas (e.g. `model/generator.py (generate_word)`, `model/font_glyph.py (render_trailing_mark)`). No other CLAUDE.md text references the deleted symbols.
- [ ] 5. `make test-quick` passes.
- [ ] 6. `make test-regression` passes: the primary CV gates (`height_outlier_score >= 0.90`, `ocr_min >= 0.30`) hold on all three seeds (42, 137, 2718).
- [ ] 7. `make test-hard` passes: average OCR on the curated hard-words set remains >= 0.5.
- [ ] 8. Human review via `make test-human EVAL=composition,punctuation,hard_words`: composition rating >= 3/5 on at least 2 of 3 seeds (does not regress below the current 3/5 baseline), and no apostrophe-stacking defect ("can'''t", "it'''o", "can''t'", or similar) appears in freeform notes on any seed.

### Context

Adopted from the turn-close proposal in the prior SPEC.md entry (consumed this turn). BACKLOG.md entry `E -- Drop splitting entirely, full-word DP, NO overlay (PROMOTED TO PRIMARY CANDIDATE)` under the "Cantt-specific proposals" section carries the full risk analysis; read it before starting.

**Key data from prior turns (for the coding agent, so the prior-turn context is not re-derived from git):**

- Hard-words ledger at commit `5bfeca5` seed 42: can't 0.8, they'd 1.0, don't 1.0, it's 1.0. Ledger at `tests/medium/hard_words_ledger.jsonl`.
- Seed 2718 in review 2026-04-18_154757 composition rendered `can't` cleanly with no overlay, demonstrating DP can handle the whole word when seeds cooperate.
- The overlay path (commits `fe12a7b` Turn 2b, `7d55f9c` Turn 2c, both reverted in `0a5c1cf`) stacked marks because DP produces body-zone apostrophe-shaped ink on some seeds; high-density guards cannot distinguish that ink from letter ink.
- The split path is what existed before the overlay and remains the post-revert state. It underperforms on the right-side 1-2 char parts: BACKLOG.md entry F documents the failure mechanism.

**Pre-existing safety net to trust (do not re-implement):**

The OCR rejection + retry loop in `generate_word()` already runs up to 2 retries at accuracy floor 0.4 for every word. Words still failing after retries are automatically appended to `reforge/data/hard_words.json` candidates for manual triage. No contraction-specific safety valve is needed; that was the lesson of Turn 2c's failed OCR safety valve (OCR reads "canit" at 0.8 even when three apostrophe marks are present, so an OCR-based guard cannot catch stacking).

**Optional cleanup (not required, do not block the spec on it):**

- `docs/research_survey.md:60` discusses `make_synthetic_apostrophe()` in a "P1 Relevance to reforge" section. After this spec, that reference is historical; the surrounding prose can be dropped or flagged as "superseded by Option E" in the same commit if convenient. Leaving it stale is non-breaking.

**Out of scope (tracked in BACKLOG.md, do not bundle):**

- Caveat glyph dilate for trailing punctuation (proposal Secondary; `### Caveat glyphs too thin in composition (Turn 2d follow-up)`).
- D3 candidate-eval human-pick join key (`### candidate-eval human-pick join key`); unblocks QUALITY_WEIGHTS reweighting.
- Option W, split at `'t` as a 2-char unit (`### W -- Split at (can, 't)`); reserved fallback if E regresses.
- Morphological-component-based apostrophe detection (entry F revisit criterion (a)).

**zat.env practices carried in:**

- Smallest change that addresses the root cause. Delete the contraction path outright rather than hiding it behind a feature flag. If criteria 5-7 regress, `git revert` rather than stack further tuning on top.
- Update tests in the same increment as the code change; do not leave dead tests pointing at deleted functions.
- Two-consecutive-fix rule: if option E regresses in this spec, do not attempt option W in the same spec. Revert, capture the result in FINDINGS.md under the Apostrophe-rendering finding, and stop the turn for a proposal.
- Do not push to the remote unless explicitly asked.

**Failure protocol:**

- If criterion 6 or 7 fails: revert the code change. These are regression gates.
- If criterion 8 regresses (human review shows composition < 3/5 on 2+ seeds, or apostrophe stacking returns): revert and document in FINDINGS.md under the Apostrophe-rendering finding. Then propose: option W, or a BACKLOG revisit of F with the morphological-component detector.
- Do not attempt to fix option E by reintroducing the split path with tweaks. The split path's right-side weakness is seed-invariant and is the reason we are trying E.

---
*Prior spec (2026-04-18, BACKLOG migration): Adopted upstream zat.env root-level `BACKLOG.md` mechanism; removed `docs/BACKLOG.md` + CLAUDE.md pointer; captured D3 carryover in BACKLOG.md (7/7 met).*

<!-- SPEC_META: {"date":"2026-04-18","title":"Option E: full-word DP for contractions","criteria_total":8,"criteria_met":0} -->
