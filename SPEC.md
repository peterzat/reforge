## Spec -- 2026-04-13 -- Punctuation defense and eval test fixes

**Goal:** Address the two most actionable quality issues from the 2026-04-13 human review: (1) apostrophe and punctuation rendering is consistently poor across contractions (can't, don't, it's, they'd), degrading both composition and hard-words evals, and (2) two human eval tests (sizing, stitch) are measuring the wrong thing, producing frustration rather than signal. Fix punctuation rendering at the wrapper layer and redesign the broken evals so future reviews produce actionable data.

### Acceptance Criteria

#### A. Punctuation and apostrophe rendering

Apostrophes have been flagged in 3 consecutive reviews. The hard_words image shows oversized dark blobs instead of delicate strokes. This is now the most frequently cited letter-level defect. The charset includes `' " ! , . ; : ? ( ) * + - / # & _` but only the apostrophe has been systematically evaluated. All punctuation characters in the charset should be covered.

- [ ] A1. Add a punctuation-specific generation test to the hard words eval: generate at least 6 words/phrases containing different punctuation marks from the charset (apostrophe in contractions, comma in a word pair, period, question mark, semicolon, exclamation). Run OCR on each. Assert average OCR accuracy >= 0.3 across the set. This establishes a punctuation readability floor alongside the existing hard-words floor.
- [ ] A2. Implement a contraction-splitting strategy in the generation pipeline: when a word contains an apostrophe, generate the parts separately (e.g., "can't" -> generate "can" + synthetic apostrophe + generate "t") and stitch them with appropriate spacing. The synthetic apostrophe should be a thin stroke derived from the style reference images, not a DiffusionPen generation. This bypasses the model's poor apostrophe representation.
- [ ] A3. After A2, the OCR accuracy for apostrophe-containing words in the hard words list (can't, don't, it's, they'd) must average >= 0.5 across 3 seeds (42, 137, 2718). Current baseline varies 0.0-0.5 depending on generation luck.
- [ ] A4. Composition eval with the standard two-paragraph text (which contains "can't" and "they'd") must not regress: composition_score and ocr_accuracy must remain at or above current baseline values. The contraction-splitting must integrate cleanly with the existing postprocessing pipeline (gray-box defense, font normalization, harmonization).
- [ ] A5. `make test-quick` passes. Add unit tests for the contraction-splitting logic: correct split points, handling of edge cases (word starting/ending with apostrophe, multiple apostrophes, possessives like "Katherine's").

#### B. Baseline detection improvement

Baseline alignment regressed from Resolved (4/5) to 2/5 without code changes. The median-based line alignment works, but per-word baseline detection fails on words with prominent ascenders/descenders (g in "gray", f in "fences"). The density-scan algorithm confuses descender strokes for body text.

- [ ] B1. Improve `detect_baseline()` in `compose/layout.py` to handle words where ascender or descender strokes extend significantly below/above the body. The fix should use the word's character content (available as a parameter) to inform baseline detection: words containing known descender letters (g, j, p, q, y) should expect ink below the baseline and adjust the density-drop scan accordingly.
- [ ] B2. Add targeted unit tests: generate or use fixture images for words with descenders ("gray", "fences", "jumping", "quickly") and assert baseline detection is within 3px of the manually measured correct baseline. At least 4 test words with descenders.
- [ ] B3. After B1, run `make test-regression` and confirm baseline_alignment metric does not regress from the current baseline. Run the baseline eval (`make test-human EVAL=baseline`) and confirm rating does not decrease from 2/5.

#### C. Sizing eval redesign

The sizing eval conflates a Plateaued limitation (single-char "I" generation) with the testable question of multi-char word consistency. 7 reviews, 4 code changes, ratings stuck at 1-2/5. The test produces frustration rather than signal.

- [ ] C1. Change the sizing eval words from `["I", "quick", "something"]` to `["the", "quick", "something"]` (all 4+ chars, varied lengths). This tests whether the font normalization pipeline produces consistent sizing across multi-char words without being dominated by the Plateaued single-char issue.
- [ ] C2. Optionally add a second sizing comparison: `["I", "The"]` as a separate labeled pair in the same eval image, explicitly captioned "Case proportion (known limitation)". This tracks the Plateaued issue without polluting the primary sizing signal.

#### D. Stitch eval redesign

The stitch eval compares overlap widths, but chunk height mismatch dominates the visual impression across all variants, making the overlap comparison meaningless. 4 reviews have noted this.

- [ ] D1. Before generating the overlap comparison, normalize both chunks ("unders" and "tanding") to the same ink height. This isolates the overlap-blending question from the height-mismatch question, which is a separate issue tracked in FINDINGS.md.
- [ ] D2. Add a label or caption to the stitch eval image noting the chunk heights before and after normalization, so the reviewer can see whether height normalization is effective.

#### E. Gating and integration

- [ ] E1. `make test-quick` passes after all changes (A5 + B2 + any new tests).
- [ ] E2. `make test-regression` passes (multi-seed, primary metric gates hold).
- [ ] E3. `make test-hard` passes. Any new punctuation words added to the hard words curated list are included in the regression.

### Context

**Prior turn (2026-04-10):** Installed convergence discipline: metric-human correlation analysis, primary metric hierarchy (height_outlier_score + ocr_min), multi-seed regression, plateau recognition, and "done" target. All 17 criteria met. Methodology turn, no quality changes.

**Human review 2026-04-13 results:**
- composition: 3/5 (defects: size_inconsistent, baseline_drift, letter_malformed; "apostrophe in can't remains super malformed")
- hard_words: 2/5 (can't, noon, impossible flagged unreadable; "apostrophes are terrible looking")
- baseline: 2/5 (regressed from Resolved 4/5; "gray sits too high, fences sits too low")
- sizing: 1/5 (user called test "broken"; "I takes up full vertical space, q is as big as I")
- stitch: 4px picked but test called "flawed" due to height mismatch
- ink_weight: "looks identical" (4th consecutive review)
- candidate: A picked, disagrees with metric (4/5 disagreement rate)
- spacing: preferred B (tighter, 3px vs 6px)

**Apostrophe root cause:** DiffusionPen's Canine-C tokenizer treats apostrophe as a full character position, but IAM training data has very few apostrophe examples (most words are dictionary words without contractions). The model's learned representation for apostrophe is poor. All N candidates for apostrophe words tend to be bad, so best-of-N selection cannot fix this. The contraction-splitting approach (A2) bypasses the model entirely for the apostrophe glyph.

**Baseline detection root cause:** The density-scan in `detect_baseline()` scans top-down from midpoint looking for density drops. Words like "gray" (g descender) and "fences" (f with a stroke that curves below) produce ink below the true baseline that the algorithm interprets as body text, pushing the detected baseline too low or causing the scan to never fire. Character-aware detection can set expectations about descender presence.

**Sizing test design problem:** The current eval uses `["I", "quick", "something"]`. "I" is a single character affected by the Plateaued DiffusionPen limitation. Including it makes the test unable to measure the actionable question (multi-char consistency). Normalization targets are 26px (1-2 char) vs 28px (3+ char), so "I" and "quick" end up at nearly the same total height, with "quick"'s q-descender making them look identical.

**What this spec does NOT do:**
- Retrain or fine-tune DiffusionPen (non-goal)
- Fix single-char word sizing (Plateaued)
- Reweight QUALITY_WEIGHTS (insufficient human data, only 1 of 5 candidate reviews agreed)
- Change spacing (B preference was without notes; monitor next review before acting)
- Promote ink weight finding (one more "identical" review and it should become Acceptable)

**zat.env practices carried forward:** Work in small committable increments; get one thing working before the next. Run test suite after each functional change. If two consecutive fix attempts fail, revert and re-evaluate.

---
*Prior spec (2026-04-10): Objective alignment and convergence discipline (17/17 criteria met). Metric-human correlation, primary metric gates, multi-seed regression, plateau recognition, "done" target.*

<!-- SPEC_META: {"date":"2026-04-13","title":"Punctuation defense and eval test fixes","criteria_total":14,"criteria_met":0} -->
