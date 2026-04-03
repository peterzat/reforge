## Spec -- 2026-04-03 -- Per-word readability improvements

**Goal:** Reduce per-word illegibility, which is the dominant complaint in the last three human reviews (composition stuck at 3/5, "many words still illegible"). Attack from three angles: gray box artifacts on short/punctuated words, chunk x-height mismatch, and OCR rejection loop tuning. Each fix follows the finding-driven iteration pattern: implement, targeted eval, update finding status.

### Acceptance Criteria

#### A. Gray box defense for short and punctuated words

The 5-layer gray box defense fails on short words ("a", "I", "no") and punctuated words ("can't", "it's", "they'd"). Two reviews flagged this. The problem: DiffusionPen generates dark gray backgrounds (~150-175) for these words, and the adaptive background estimate (90th percentile) is pulled down by the large gray region, making the ink threshold too low to separate ink from background.

- [ ] A1. Diagnose the gray box failure mode for short/punctuated words by generating "a", "I", "can't", and "it's" and inspecting the postprocessing pipeline output at each defense layer. Identify which layer(s) fail and why.
- [ ] A2. Implement a fix to the failing defense layer(s). The fix should not regress gray box detection for normal-length words.
- [ ] A3. `make test-quick` passes (gray box tests in tests/quick/test_graybox.py).
- [ ] A4. `make test-hard` passes with no regression in average OCR accuracy below current baseline (0.742). Short words ("a", "I", "an", "no") should show improvement.

#### B. Chunk x-height normalization

The stitch gap is fixed, but chunks still render at different x-heights (letter body size). The human noted "tanding is visibly smaller than the first part." Total ink-height normalization matches ascender-to-descender extent but not the letter body, so "under" (tall letters) and "standing" (shorter body) appear mismatched.

- [ ] B1. Measure x-height (distance from baseline to top of lowercase body, excluding ascenders) for each chunk, and scale chunks so x-heights match rather than total ink heights.
- [ ] B2. `make test-hard` passes after the change. Chunked words ("everything", "understand", "impossible") should not regress.
- [ ] B3. A targeted human eval (`make test-human EVAL=stitch`) confirms the x-height fix is visually better than before.

#### C. OCR rejection loop improvements

The OCR rejection loop retries twice at a 0.3 accuracy threshold. For composition text (40 words), a few illegible words tank readability. Tuning the loop could improve per-word quality at acceptable cost.

- [ ] C1. Profile the current rejection loop: what fraction of words trigger retries, what is the accuracy improvement from retries, and what is the time cost per retry?
- [ ] C2. Based on C1 data, adjust the rejection threshold and/or retry count. If the data shows retries are effective (accuracy improves significantly), consider raising the threshold to 0.4 or adding a third retry. If retries rarely help, the loop may need a different strategy.
- [ ] C3. `make test-hard` passes. Average OCR accuracy should improve or hold steady.

#### D. Composition re-evaluation

After A-C fixes, run a full composition eval to measure the cumulative impact on readability.

- [ ] D1. Run `make test-human EVAL=hard_words,composition`. The hard_words eval validates short-word improvements. The composition eval measures overall readability.
- [ ] D2. Update FINDINGS.md: "Hard words show gray box artifacts" and "Composition has persistent illegibility" findings get updated with the eval results. Move to Resolved if the human confirms improvement, or record remaining issues for the next iteration.
- [ ] D3. If composition rating improves above 3/5, update FINDINGS.md status summary. If it stays at 3/5, note what the remaining blockers are.

### Context

**Why these three findings together?** They all converge on the same symptom (illegible words in composition) through different mechanisms: gray boxes make short words unreadable, x-height mismatch makes chunked words look wrong, and the rejection loop is the last chance to catch poor generations before they hit the canvas. Fixing any one helps composition; fixing all three should move the needle past 3/5.

**Why not quality_score disagreement?** Still only one data point. Needs more reviews before tuning scoring weights.

**Why not ink weight harmonization?** Human found "no visible effect." This is a candidate for Acceptable status, not a code change. Can be closed out during the D2 finding update.

**Interaction with test gates.** These changes affect generator.py (postprocess_word, stitch_chunks, generate_word). Pre-commit runs quick tests (includes gray box tests). Pre-push runs regression test. Hard words test is the primary quality gate for these changes.

---

*Prior spec (2026-04-03): Finding-driven quality iteration loop (14/14 criteria met).*

*Prior spec (2026-04-03): Hard words watchlist and targeted quality stress testing (14/14 criteria met).*

*Prior spec (2026-04-02): Human-in-the-loop quality evaluation (25 criteria). Infrastructure built, first feedback loop completed.*

<!-- SPEC_META: {"date":"2026-04-03","title":"Per-word readability improvements","criteria_total":12,"criteria_met":0} -->
