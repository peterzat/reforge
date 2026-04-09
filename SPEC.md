## Spec -- 2026-04-09 -- Readability-weighted candidate selection

**Goal:** Improve composition quality by making the best-of-N candidate selection prefer readable words over visually clean but illegible ones. The current `quality_score` measures image properties (background, contrast, edges, height) but ignores readability, and human eval confirmed it disagrees with human preference. Adding OCR accuracy as a selection signal should reduce malformed words in final output, directly addressing the 3/5 composition ceiling.

### Acceptance Criteria

#### A. OCR-aware candidate scoring

The current `quality_score` in `quality/score.py` uses 5 image-quality sub-scores. The `generate_word` function in `model/generator.py` picks the highest-scoring candidate, with a style-similarity tiebreaker within 0.05 of the best. OCR is only used post-selection for rejection/retry (threshold 0.4, 2 retries). This means a candidate with perfect image metrics but garbled letters beats a slightly noisier candidate that is clearly readable.

- [ ] A1. Add an `ocr_readability` component to candidate scoring. Given a candidate image and the target word, compute `ocr_accuracy(img, word)` and incorporate it into the selection decision. The OCR score must not simply replace image quality; a candidate that is readable but has a gray box background is still bad. The two signals (image quality and readability) must both contribute.
- [ ] A2. The cost of OCR per candidate is ~0.3s (TrOCR on CPU). At 3 candidates per word, this adds ~0.9s per word (~30% overhead on the quality preset). This overhead must not apply when `num_candidates == 1` (fast/draft presets), since there is no selection to make. When `num_candidates == 1`, the existing post-selection OCR rejection loop handles readability.
- [ ] A3. When OCR-aware scoring is active (`num_candidates > 1`), the post-selection OCR rejection loop should still run but can use the already-computed OCR accuracy from candidate scoring to avoid redundant TrOCR calls for the selected candidate.
- [ ] A4. `make test-quick` passes. Add a unit test in `tests/quick/` that verifies OCR-aware scoring selects a readable candidate over one with higher image-quality score but lower OCR accuracy (using mock OCR).
- [ ] A5. `make test-regression` passes. The regression test uses the quality preset (3 candidates); verify the overall quality score does not regress.

#### B. Descender clipping diagnosis and fix

Human review flagged "q descender appears cut off" and "'for' is way too low (below descenders)" across multiple reviews. The 64px canvas constrains vertical space; deep descenders on some words may clip at the canvas bottom, and baseline detection may misplace words with unusual vertical profiles.

- [ ] B1. Diagnostic: generate words with known descenders (g, j, p, q, y, "jumping", "quickly") and measure how much ink falls below the detected baseline vs. the canvas bottom. Record whether clipping is happening at the generation stage (canvas too small) or the composition stage (baseline misplacement).
- [ ] B2. If generation-stage clipping is confirmed: add bottom padding (white rows) to the raw 64px canvas output before postprocessing, preserving any descender ink that would otherwise be cropped. The padding amount should be proportional to the detected descender depth, not a fixed number of pixels.
- [ ] B3. If composition-stage baseline misplacement is confirmed: adjust the baseline detection in `compose/layout.py` to account for the specific vertical profile of descender-heavy words. The current top-down density scan (BASELINE_DENSITY_DROP=0.15, BASELINE_BODY_DENSITY=0.35) may be setting the baseline too low for words where the descender accounts for a large fraction of total ink height.
- [ ] B4. `make test-quick` passes after any layout.py or generator.py changes. If padding is added, verify existing postprocessing (body-zone noise removal, cluster filter) still works correctly on the padded image.
- [ ] B5. Run `make test-human EVAL=baseline` to verify the fix does not regress the current 4/5 baseline alignment rating.

#### C. Scoring weight sanity check

Only 1 review data point shows quality_score disagreeing with human candidate preference. Before calibrating weights (proposal D in TODO), collect baseline data on the current disagreement rate.

- [ ] C1. After implementing A1, log (to stderr or a debug flag) both the image-quality score and OCR accuracy for each candidate during generation, plus which candidate was selected and why. This is diagnostic output for tuning, not a permanent feature.
- [ ] C2. Run `make test-human EVAL=candidate` to collect a human evaluation of the new OCR-aware candidate selection. Compare the human pick rate against the metric pick rate. Record the result in FINDINGS.md as evidence for or against further weight calibration.

### Context

**Why OCR in candidate selection, not just rejection?** The rejection loop (post-selection, threshold 0.4, 2 retries) only kicks in after the best candidate is already chosen. If candidate A scores 0.85 on image quality with 0.2 OCR and candidate B scores 0.80 with 0.9 OCR, the current code picks A and then may retry generation entirely. Using OCR during selection would pick B directly, avoiding the retry cost and getting a better result.

**Cost model.** TrOCR runs on CPU (to avoid GPU contention with UNet inference). At ~0.3s per call, 3 candidates adds 0.9s per word. For the 43-word demo at quality preset, this is ~39s additional (from ~65s to ~104s). Acceptable for quality preset. Draft and fast presets (1 candidate) skip this entirely.

**Interaction with existing OCR rejection loop.** The rejection loop in `generate_word()` currently calls `ocr_accuracy(best, word)` after selecting the best candidate. With OCR-aware scoring, the selected candidate already has a known OCR accuracy. The rejection loop can reuse this value for the first check, only calling TrOCR again on retry candidates.

**Descender diagnosis is exploratory.** B1 is a diagnostic step. B2 and B3 are conditional on what B1 finds. If descender clipping is not confirmed (the visual issue is something else), those criteria can be dropped.

**Why not the glyph cache (TODO proposal B)?** The glyph cache addresses short-word quality (1-3 chars) which is a DiffusionPen limitation, not a selection problem. OCR-aware candidate selection addresses the broader illegibility ceiling that affects all word lengths. The glyph cache remains a strong candidate for a follow-up spec if OCR-aware selection does not move composition past 3/5.

**Prior turn context.** The prior spec (2026-04-04) completed 14/14 criteria: x-height normalization was attempted and reverted (pathological height explosion), proportional OCR penalty replaced the hard 0.45 score cap, ragged right margin was fixed, parameter optimality tests were added. The composition rating holds at 3/5 across 7 reviews; the ceiling appears to be per-word generation fidelity, which OCR-aware selection directly targets.

---
*Prior spec (2026-04-04): Height consistency and score accuracy (14/14 criteria met). X-height normalization reverted; proportional OCR penalty; ragged right margin fix; parameter optimality tests.*

<!-- SPEC_META: {"date":"2026-04-09","title":"Readability-weighted candidate selection","criteria_total":12,"criteria_met":0} -->
