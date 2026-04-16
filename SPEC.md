## Spec -- 2026-04-16 -- Stabilize composition at 4/5, close stale findings

**Goal:** The composition median hit 4/5 (target met). This turn consolidates: stabilize the median by addressing the remaining composition defects (size_inconsistent, "I" ink loss), close or promote stale findings, un-suspend the stitch eval, and fix the codereview WARN (duplicate output history entry). No new features; this is a hardening turn.

### Acceptance Criteria

#### A. "I" ink loss investigation

- [ ] A1. Investigate why "I" loses ink (reported as recurring in 2-3 composition reviews). Generate "I" at quality preset, inspect the postprocessed output, and identify which defense layer (if any) removes ink. Document the root cause: is it body-zone noise removal blanking the thin vertical stroke, isolated-cluster filter discarding it, or a font-normalization artifact?
- [ ] A2. If the root cause is a postprocessing layer stripping ink, implement a targeted fix (e.g., skip body-zone blanking for single-character words, or lower the ink threshold for narrow strokes). If the root cause is generation-level (DiffusionPen produces faint "I"), document it as a base-model limitation. Either way, `make test-quick` and `make test-regression` pass.

#### B. Short-word sizing ("by" is tiny)

- [ ] B1. Generate the composition text at quality preset. Measure the ink height of "by", "it", "a", "on", "so" after font normalization. Compare to the median ink height of 4+ char words on the same line. Report the ratio.
- [ ] B2. If short words (2-3 lowercase chars, not single uppercase) are consistently < 80% of median ink height, adjust `normalize_font_size` or `equalize_body_zones` to bring them closer. The fix must not regress single-uppercase sizing (Plateaued) or trigger the height_outlier gate. `make test-quick` and `make test-regression` pass.

#### C. Stitch eval un-suspension

- [ ] C1. Re-enable the stitch eval in `human_eval.py` (remove the suspension flag/skip). Generate "understanding" with the current cross-correlation alignment and present the stitch comparison via the eval.
- [ ] C2. Run `make test-human EVAL=stitch`. If the human rates the stitching >= 3/5 (up from the broken-eval era), update FINDINGS.md to reflect the cross-correlation fix. If it is still broken, document why and re-suspend.

#### D. Findings housekeeping

- [ ] D1. If the stitch eval passes (C2 >= 3/5), update the "Chunk stitching produces visible height mismatch" finding to Resolved with the cross-correlation fix as the resolution.
- [ ] D2. If baseline alignment holds at 4/5 in the composition eval this turn, promote "Baseline alignment fragile across generation runs" to Acceptable with rationale (4 code changes, 3 consecutive reviews at 3-4/5, cross-correlation stitching contributing).
- [ ] D3. Update the FINDINGS.md status summary table to reflect any status changes from D1-D2.

#### E. Codereview WARN fix

- [ ] E1. Remove the duplicate OUTPUT_HISTORY.md entry (keep only the most recent per the one-entry-per-push convention). Commit.

#### F. Integration gates

- [ ] F1. `make test-quick` passes.
- [ ] F2. `make test-regression` passes on all 3 seeds.
- [ ] F3. Run `make test-human EVAL=composition`. Composition holds at >= 3/5 (no regression). Present rating and defects in terminal.
- [ ] F4. Last 5 composition ratings still have median >= 4/5 after this turn's eval.

### Context

**Prior turn (2026-04-14):** Research survey, Bezier synthetic punctuation, cross-correlation stitch alignment, candidate scoring analysis. 12/14 criteria met. Trailing punctuation went from invisible (1/5) to visible in composition. Cross-correlation alignment dramatically fixed the "tanding above unders" problem. Mark sizing increased 3x for composition visibility. Composition median reached 4/5 (last 5: 2, 3, 4, 4, 4).

**Composition defects in recent 4/5 reviews:** size_inconsistent (every review), letter_malformed (intermittent), ink_weight_uneven (intermittent). The size_inconsistent defect is driven by "by" and other 2-3 char lowercase words appearing too small, and "I" appearing ink-depleted. These are the two most actionable remaining issues.

**Stitch eval status:** Suspended since 2026-04-14 after 4 consecutive "broken" reviews where vertical misalignment between chunks made overlap comparison meaningless. Cross-correlation alignment was integrated after suspension. The eval has not been run with the new alignment.

**Findings status:** 4 Active, 2 In Progress, 1 Resolved, 1 Acceptable, 1 Plateaued. The two In Progress findings (baseline alignment, apostrophe rendering) and the chunk stitching Active finding are candidates for status changes based on this turn's evaluations.

**zat.env practices:** Work in small committable increments. Run GPU tests aggressively. Run `~/src/qwen-2.5-localreview/gpu-release` before GPU work to free the warm server's VRAM. If two consecutive fix attempts fail, document the negative result and move on.

---
*Prior spec (2026-04-14): Research: approaches from handwriting synthesis literature (12/14 criteria met).*

<!-- SPEC_META: {"date":"2026-04-16","title":"Stabilize composition at 4/5, close stale findings","criteria_total":13,"criteria_met":0} -->
