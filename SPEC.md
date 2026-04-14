## Spec -- 2026-04-14 -- X-height normalization, punctuation polish, eval fixes

**Goal:** Address the three root causes behind stalled composition quality (median 3/5, target 4/5): (1) font normalization uses total ink height including ascender dots and descender tails, causing words with i/j to be scaled down disproportionately and "gray" to appear oversized, (2) contraction splitting is a net positive (avoids DiffusionPen double-apostrophes and blobs) but produces tight cropping on right-side parts and lacks dedicated eval signal, and (3) two eval tests (stitch, sizing) have been flagged broken by the human 3 and 2 consecutive reviews respectively, producing frustration instead of signal.

### Acceptance Criteria

#### A. X-height font normalization

Font normalization currently uses `compute_ink_height()` (first ink row to last ink row, including ascender dots and descender tails). This inflates the measured height for words containing i, j, t, l, and descender letters, causing them to be scaled down more than words without those features. "gray" (no ascenders) looks disproportionately large next to "jumping" (j dot inflates height). The fix: normalize by body-zone height (x-height) instead of total ink height.

- [ ] A1. `normalize_font_size()` in `font_scale.py` uses `compute_x_height()` instead of `compute_ink_height()` as the normalization signal. The x-height function already exists in `ink_metrics.py` (used by `stitch_chunks`). If `compute_x_height()` returns a degenerate value (< 5px or equal to total height, meaning no body zone was detected), fall back to `compute_ink_height()`.
- [ ] A2. `make test-quick` passes. Add or update unit tests: two words with ascender dots ("jumping", "quiet") and two without ("gray", "brown") should have body-zone heights within 20% of each other after normalization.
- [ ] A3. `make test-regression` passes on all 3 seeds. Primary gates (height_outlier_score >= 0.90, ocr_min >= 0.30) hold.
- [ ] A4. Run `make test-human EVAL=baseline,composition`. Baseline rating does not decrease from 3/5. "gray" should no longer appear visibly larger than other words in the baseline eval.

#### B. Contraction splitting refinement

The synthetic punctuation approach is a net positive: it avoids DiffusionPen's worst artifacts (double apostrophes, oversized blobs). But right-side parts have two problems: (1) tight-crop clips thin strokes too aggressively (human: "the cropping on the 't' is too close"), and (2) single-char parts like "t" suffer from DiffusionPen's canvas-fill behavior, producing oversized glyphs. The first is fixable at the wrapper layer; the second is a known limitation.

- [ ] B1. Increase tight-crop padding in `stitch_contraction()` for right-side parts that are 1-2 characters. Current padding is 1px on each side. Use at least 3px for parts <= 2 chars to preserve thin stroke edges.
- [ ] B2. OCR accuracy for contraction words (can't, don't, it's, they'd) does not regress from current multi-seed averages (0.593-0.750 across seeds 42/137/2718). Run `make test-hard` to verify.
- [ ] B3. `make test-quick` passes. Existing contraction unit tests (17 tests in test_contraction.py) still pass.

#### C. Punctuation eval type

The hard_words eval covers contractions incidentally but does not isolate punctuation quality. A dedicated eval type provides focused signal for iterating on synthetic punctuation rendering.

- [ ] C1. Add a `punctuation` eval type to `scripts/human_eval.py`. Generate 6+ words with different punctuation from the charset (at least: apostrophe contraction, comma-adjacent, period, question mark, exclamation, semicolon). Present as a grid or composed line for human rating.
- [ ] C2. The new eval type integrates with `make test-human` and `make test-human EVAL=punctuation`. Review data is saved to the standard JSON format with a "punctuation" key.
- [ ] C3. Add `punctuation` to the eval type mapping table in CLAUDE.md so the finding-driven iteration loop knows which code areas map to this eval.

#### D. Eval fixes

Two evals are producing frustration instead of signal. Fix or simplify them.

- [ ] D1. **Sizing eval:** The sizing eval should show only the multi-char consistency test (["the", "quick", "something"]) with a clear description. Remove or fix any remnant of the "Case proportion (known limitation)" section that was reported as broken (showing only "I" with "The" missing). The Plateaued single-char issue does not need eval coverage.
- [ ] D2. **Stitch eval:** The stitch eval has been called broken 3 consecutive reviews because chunk baseline mismatch makes overlap comparison meaningless. Fix by equalizing chunk baselines in the eval image (not in production stitch_chunks), or suspend the eval with a clear note in human_eval.py explaining it is blocked on stitch_chunks baseline alignment.
- [ ] D3. `make test-quick` passes after eval changes. `make test-human EVAL=sizing,stitch` generates correct output (or skips stitch cleanly if suspended).

#### E. Integration gates

- [ ] E1. `make test-regression` passes on all 3 seeds after all changes.
- [ ] E2. `make test-hard` passes.
- [ ] E3. Run `make test-human` (full 8+ eval types including new punctuation). Present results in terminal for review.

### Context

**Prior turn (2026-04-13):** Contraction splitting for apostrophe words, character-aware baseline detection, sizing and stitch eval redesigns. 14/14 criteria met. Two human review sessions on 2026-04-14 validated the changes: composition hit 4/5 (generous, closer to 3.5), letter_malformed dropped from composition defects for the first time, hard_words improved from 2/5 to 3/5.

**Human review 2026-04-14 results (two sessions combined):**
- composition: 3/5 then 4/5 (generous). Defects: size_inconsistent, baseline_drift. "by" still super small. letter_malformed dropped from defects.
- hard_words: 2/5 then 3/5. "don't" looking better but "t" cropped too close. "can't" has malformed "t". "impossible" reads as "impoosssible" (letter duplication, generation-level).
- baseline: 3/5 both sessions. Stabilizing after character-aware fix (was 2/5-4/5 swings). "gray" still too big.
- sizing: 3/5 (up from 1/5). Display reported broken in first session.
- stitch: 4px picked both times. "Still broken, vertical misalignment makes it difficult to pick the right overlap."
- ink_weight: "very close, possibly identical." 6th consecutive review with no A/B difference. Promoted to Acceptable.
- candidate: C picked, disagrees with metric. 6 of 7 reviews disagree.

**Root cause: "gray" too big.** Font normalization targets total ink height. "jumping" (j dot above body) has larger ink_height than "gray" (no ascenders), so "jumping" is scaled down more. After normalization, "gray"'s body appears disproportionately large. The fix is to normalize by x-height (body zone only). `compute_x_height()` already exists and is used by `stitch_chunks` for chunk alignment. This is the same function, just applied earlier in the pipeline.

**Contraction splitting status.** The approach works: OCR accuracy improved (0.593-0.750 multi-seed, up from 0.0-0.5), and letter_malformed dropped from composition defects. Problems are refinement-level: tight-crop 1px padding clips thin "t" strokes, and single-char right parts suffer from DiffusionPen's canvas-fill (a Plateaued limitation, not addressable at the wrapper layer). Human noted: "the new punctuation generation makes things better but needs to be perfected and should have targeted human eval test loops too."

**Process feedback captured this turn:** (1) Freeform notes in review JSON must be given high weight in FINDINGS updates, especially when flagging broken tests. (2) Findings summaries should be presented in the terminal, not via qpeek.

**What this spec does NOT do:**
- Retrain or fine-tune DiffusionPen (non-goal)
- Fix single-char canvas-fill ("I", single-char contraction parts) -- Plateaued
- Reweight QUALITY_WEIGHTS for candidate selection (6/7 disagreement rate, but insufficient data for principled reweighting)
- Fix "impossible" letter duplication (generation-level glyph repetition, not postprocessing)

**zat.env practices carried forward:** Work in small committable increments. Run test suite after each functional change. If two consecutive fix attempts fail, revert and re-evaluate. GPU tests aggressively as part of the dev loop.

---
*Prior spec (2026-04-13): Punctuation defense and eval test fixes (14/14 criteria met). Contraction splitting, character-aware baseline, sizing/stitch eval redesigns.*

<!-- SPEC_META: {"date":"2026-04-14","title":"X-height normalization, punctuation polish, eval fixes","criteria_total":14,"criteria_met":0} -->
