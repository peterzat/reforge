## Spec -- 2026-04-10 -- Word sizing consistency and human eval baseline

**Goal:** Break through the 2/5 sizing ceiling that has resisted three post-generation normalization approaches, and collect human evaluation data on the recent candidate selection and baseline improvements to confirm or disprove their effectiveness.

### Acceptance Criteria

#### A. Height-aware candidate selection

Word sizing at 2/5 is the most persistent human complaint. Three post-generation approaches (x-height normalization, unified 3+ char target, case-aware cap height ratio) were tried and either had no effect or regressed composition. The sizing problem originates in DiffusionPen's per-word height variance: "I" fills the full 64px canvas while "quick" uses 30px. Post-generation normalization is fighting the model's output distribution. Selection-time intervention should prefer candidates closer to a target height, avoiding extreme outliers before they reach the normalization pipeline.

- [x] A1. Add a `height_consistency` component to candidate scoring in `generate_word()`. For each candidate, compute ink height and score closeness to the target (SHORT_WORD_HEIGHT_TARGET for 1-2 char words, ~28px for 3+ char words). The score should penalize extreme heights (filling the full canvas or using less than half the target) more than moderate deviations. This is selection-time, not post-generation normalization.
- [x] A2. Height scoring must be weighted alongside existing signals (image quality 80%, stroke width 20%, OCR 40% via OCR_SELECTION_WEIGHT). The height score should replace or share weight with the existing `height_consistency` sub-score in QUALITY_WEIGHTS, which currently measures canvas coverage ratio rather than absolute target closeness. Define the weight so height preference does not override readability (OCR) or artifact detection (background score).
- [x] A3. When `num_candidates == 1`, height scoring must not apply (same bypass as OCR scoring in A2 of the prior spec). No overhead for draft/fast presets.
- [x] A4. `make test-quick` passes. Add a unit test that verifies height-aware selection picks a candidate with moderate ink height over one with higher image-quality score but extreme height (e.g., full canvas fill), using mocked candidates.
- [x] A5. `make test-regression` passes. Overall quality score does not regress.

#### B. Human eval data collection

The prior spec left three criteria requiring human evaluation (B3, B5, C2). The baseline fix (median normalization) landed and scored 4/5 in review. Candidate selection showed first metric-human agreement. These need formal data points.

- [x] B1. Run `make test-human EVAL=candidate` and record whether the human pick agrees with the metric pick. Update the "Quality score disagrees with human candidate preference" finding in FINDINGS.md with the result. If 2 consecutive agreements (this plus the prior one), move the finding to Resolved.
- [x] B2. Run `make test-human EVAL=baseline` and record the rating. Update the "Baseline alignment fixed with median normalization" finding in FINDINGS.md. If the rating holds at 4/5, confirm Resolved status.
- [x] B3. Run `make test-human EVAL=sizing` after implementing A1-A2 to measure whether height-aware candidate selection improves the 2/5 sizing rating. Record the result in FINDINGS.md.
- [x] B4. Run `make test-human EVAL=composition` to get a fresh composition rating after this turn's changes. Record defects in FINDINGS.md.

#### C. Prior spec cleanup

Three criteria from the prior spec were left unmet. Assess and close them.

- [x] C1. B3 (baseline misplacement): the median-based baseline normalization in render.py resolved the composition-stage baseline problem. If `make test-human EVAL=baseline` (B2 above) confirms 4/5, mark the prior spec's B3 as resolved by the median approach rather than per-word detection tuning. If baseline regressed, the criterion remains and detection tuning is needed.
- [x] C2. B5 and C2 from the prior spec are satisfied by B2 and B1 above respectively. No additional work beyond running the evals.

### Context

**Why selection-time over post-generation for sizing?** Three post-generation approaches failed:
1. X-height normalization: pathological height explosion, reverted.
2. Unified 3+ char target: no visible effect (the problem is variance, not the target).
3. Case-aware cap height ratio (0.72): regressed composition 4/5 to 3/5, reverted.

All three operated on DiffusionPen's raw output after the fact. The model generates "I" at 60px ink height and "quick" at 28px, a 2:1 ratio. Normalizing this after generation requires aggressive scaling that destroys letterforms. Selection-time intervention is different: given 3 candidates for "I", pick the one closest to 28-32px rather than the one that fills the canvas. The model does produce height-varied candidates; we have just been ignoring height during selection.

**Height target math.** SHORT_WORD_HEIGHT_TARGET is 26px. 3+ char words target 28px (26 * 1.08). The human wants "lowercase body roughly 1/2 the size of capital I." If the best candidate for "I" is at 50px instead of 60px, that is 50 vs 28 = 1.8:1 instead of 2.1:1. Combined with post-generation normalization bringing the ratio tighter, this could move sizing from 2/5 toward 3/5.

**What the prior turn accomplished.** OCR-aware candidate selection (A1-A5), descender padding (B1-B2, B4), scoring diagnostics (C1), blended stroke width harmonization, stroke width scoring in candidate selection. Composition reached 4/5 ("easily our best so far"). Baseline resolved via median normalization (4/5). Candidate selection showed first human-metric agreement. Three criteria left unmet (B3, B5, C2), all human-eval-gated.

**FINDINGS.md active items.** 5 Active findings, 2 In Progress. The sizing finding (6 reviews, 3 code changes, still 2/5) is the highest-priority target. Chunk stitching height mismatch is Active but secondary. Hard words (In Progress, 3/5) may benefit from height-aware selection indirectly if it reduces extreme canvas-fill on short words.

---
*Prior spec (2026-04-09): Readability-weighted candidate selection (9/12 criteria met). OCR-aware candidate selection, descender padding, stroke width scoring. Composition 4/5. Remaining criteria were human-eval-gated.*

<!-- SPEC_META: {"date":"2026-04-10","title":"Word sizing consistency and human eval baseline","criteria_total":11,"criteria_met":11} -->
