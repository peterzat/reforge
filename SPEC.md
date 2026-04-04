## Spec -- 2026-04-04 -- Height consistency and score accuracy

**Goal:** Fix the two most visible remaining quality issues: (1) word height variation that humans keep flagging as "size_inconsistent" despite CV metrics showing height_outlier_ratio=1.0, and (2) the overall quality score being misleadingly low (0.45 on a 43-word demo) because one bad word's OCR tanks the entire page. Secondary: clean up test infrastructure debt and address composition stagnation levers.

### Acceptance Criteria

#### A. X-height based height harmonization

The current height normalization pipeline uses total ink height (ascender-to-descender extent) for both font_scale.py and harmonize.py. Human reviews flag "size_inconsistent" at 3/5 despite CV metrics showing height_outlier_ratio=1.0. The gap: total ink height can be "consistent" while the letter body (x-height) varies wildly.

Diagnostic measurements confirm the problem. After font normalization, total ink heights are consistent (25-28px) but x-heights vary 2.8x:

| Word | norm total_h | norm x-height | x/h ratio |
|------|-------------|---------------|-----------|
| I | 26 | 25 | 0.96 |
| a | 26 | 22 | 0.85 |
| the | 25 | 10 | 0.40 |
| but | 26 | 11 | 0.42 |
| they'd | 28 | 9 | 0.32 |
| perfect | 28 | 12 | 0.43 |
| Katherine | 28 | 12 | 0.43 |
| beautiful | 27 | 10 | 0.37 |

"I" renders with a 25px body while "they'd" gets a 9px body, both at the same total height. This is what humans see as "size_inconsistent." The fix: use x-height (compute_x_height from ink_metrics.py, already implemented for chunk stitching) as the normalization signal for both font_scale.py and harmonize.py.

The pipeline order is: `normalize_font_size` (per-word, font_scale.py) then `harmonize_words` (cross-word, harmonize.py: two height passes then stroke weight/width). Both currently use `compute_ink_height`. Switching to `compute_x_height` will make font normalization target equal body sizes, and harmonization will catch remaining outliers in body size rather than total extent.

Risk: words with tall ascenders ("t", "l", "h") will scale up to match body size, making their total height larger than before. This is correct behavior (the ascender should be proportional to the body), but it means the total height variance may increase while perceptual consistency improves. The `word_height_ratio` metric uses total ink height, so it may get slightly worse even as human perception improves. The `height_outlier_ratio` metric should still pass since it's relative to the new median.

- [ ] A1. Diagnose: generate the full 40-word demo text, measure total ink height and x-height for each word after font normalization, confirm the x-height variation pattern shown above. Record the x-height coefficient of variation (std/mean) before the fix to establish the improvement target.
- [ ] A2. Update `font_scale.py`: replace `compute_ink_height` with `compute_x_height` for the normalization target. SHORT_WORD_HEIGHT_TARGET (26px) becomes the x-height target instead of total height target. Short words (1-3 chars) often have no ascenders/descenders, so x-height and total height are similar; the main impact is on 4+ char words with ascenders/descenders. The `compute_ink_height` re-export in font_scale.py is used by harmonize.py; keep it but add `compute_x_height` to the imports.
- [ ] A3. Update `harmonize_heights` and `harmonize_heights_pass2` in `harmonize.py`: use `compute_x_height` instead of `compute_ink_height` for measuring and comparing heights. The thresholds (110%/88% pass1, 105%/93% pass2) stay the same since they're relative to the median.
- [ ] A4. `make test-quick` and `make test-regression` pass. If `word_height_ratio` worsens due to increased total height variance from ascenders, verify that x-height variance improved to confirm the trade-off is correct.
- [ ] A5. `make test-human EVAL=sizing,composition` confirms the height fix is visually better. Target: sizing improves from 3/5.

#### B. Overall score cap rethinking

The overall quality score is capped at 0.45 when any single word has OCR < 0.5 (lines 629-632 in visual.py). On the 40-word demo, 6 words have OCR < 0.5:

| Word | OCR | Length |
|------|-----|--------|
| was | 0.25 | 3 |
| a | 0.00 | 1 |
| on | 0.33 | 2 |
| by | 0.17 | 2 |
| too | 0.00 | 3 |
| for | 0.25 | 3 |

All are short words (1-3 chars), the known DiffusionPen weakness. The remaining 34/40 words (85%) have OCR >= 0.5, with 27/40 (68%) scoring 1.0. The current binary cap throws away this signal: overall drops from ~0.77 to 0.45 because of `min(overall, 0.45)` when `ocr_min < 0.5`.

A second cap (`blank_word_ratio < 0.8`) also triggers at 0.45 but is not currently a problem (no blank words in recent runs).

The regression test (test_quality_regression.py) separately asserts `ocr_min >= 0.3` and `overall >= 0.8`. The overall threshold was calibrated when the 5-word regression text had no bad words. After this fix, the 5-word regression score should stay above 0.8 (it doesn't hit the cap), but the demo score should jump from 0.45 to the 0.65-0.75 range.

- [ ] B1. Replace the hard cap (`overall = min(overall, 0.45)` when `ocr_min < 0.5`) with a proportional penalty: multiply overall by `word_readability_rate` (fraction of words with OCR >= 0.5). With 34/40 readable, the penalty is 0.85x instead of a cliff to 0.45. Keep the `blank_word_ratio` cap as-is (it catches degenerate outputs).
- [ ] B2. Add `word_readability_rate` to the metrics dict so it's visible in quality printouts and review JSON. Computed as: `sum(1 for o in ocr_per_word if o >= 0.5) / len(ocr_per_word)`.
- [ ] B3. Update the regression test baseline if needed. The test's `ocr_min >= 0.3` hard failure stays. The `overall >= 0.8` threshold should still pass for the 5-word regression text (no short words in "Quick Brown Foxes Jump High"). Verify with `make test-regression`.
- [ ] B4. `make test-quick` and `make test-regression` pass. Run demo.sh and verify the overall score is in the 0.65-0.80 range instead of 0.45.

#### C. Ragged right margin wastes too much line space

The layout engine creates ragged right margins for a natural handwritten look. The current implementation (compose/layout.py lines 166-174) alternates between "full" lines (0-5% shortening) and "short" lines (28-42% shortening). The short lines lose nearly a third of their usable width. In the demo output, the second line reads "a Thursday the bakery on" and then has a huge whitespace gap, with "Birchwood" wrapping to the next line despite clearly fitting.

28-42% shortening is not "ragged right", it is "half a line." Real handwriting has subtle right-edge variation (5-15%), not alternating full/half lines. The current approach was designed to pass the `layout_regularity` metric (B1: right-edge std >= 8%), but over-corrected.

- [ ] C1. Reduce the short-line shortening from 28-42% to 8-18%. This still produces visible ragged right variation (adjacent lines differ by ~10%) without wasting a third of the line. Full lines stay at 0-5%.
- [ ] C2. Verify `layout_regularity` still passes (the metric requires right-edge std >= 8% of usable width; a 0-5% vs 8-18% alternation should still clear this).
- [ ] C3. `make test-quick` passes (layout tests). Run demo.sh and visually confirm lines use more of the available width.

#### D. Test infrastructure cleanup

- [ ] D1. The `test_quality_thresholds.py` flaky test upper bound was removed in this session. Verify it stays stable across 5 runs of `make test`.
- [ ] D2. Clean up `tests/medium/diagnostic_results.json` if it's checked in (it's in .gitignore but the diff shows it's tracked). Remove from git tracking if so.

### Context

**Why x-height for harmonization?** The diagnostic data is unambiguous: after font normalization, total ink heights are 25-28px (consistent) but x-heights range from 9-25px (2.8x variation). `compute_x_height` (50% of peak row density as the body zone threshold) is already implemented and tested for chunk stitching. The same function can be reused in font_scale.py and harmonize.py. The `word_height_ratio` CV metric measures total ink height ratio, which may worsen with this change (ascender words get taller overall). If so, consider adding an `x_height_ratio` metric that measures body consistency directly. Human eval is the ground truth for this change.

**Why fix the score cap now?** The 0.45 cap makes the overall metric useless for tracking quality improvements. Every recent demo scores 0.45 because 6/40 words (all short, 1-3 chars) fail OCR. The other 34 words are 85% readable. The proportional penalty (`overall *= word_readability_rate`) preserves the quality signal: a demo with 2 bad words scores higher than one with 6. This makes the metric useful for tracking per-word improvements across specs.

**Why not tackle the "a"/"or" problem directly?** All 6 words scoring OCR < 0.5 in the demo are 1-3 chars: "a", "on", "by", "too", "for", "was". DiffusionPen was trained on words >= 4 chars (IAM filter). The OCR rejection loop (threshold 0.4, 2 retries) already does what it can; the model simply cannot produce readable 1-2 character words reliably. A glyph library or letter-fragment compositing would be a significant feature addition for a future spec.

**Why not more candidates for composition quality?** Profiling showed 3 candidates per word costs ~2.6s with marginal quality improvement over 1 candidate. The quality preset (50 steps, 3 candidates) did not improve the 3/5 human rating over fast preset. The bottleneck is DiffusionPen's per-word generation fidelity, not candidate count.

**Why fix ragged right now?** The 28-42% shortening was introduced to pass the layout_regularity B1 metric (right-edge std >= 8%). It over-corrected: the test passes, but the visual result is worse than uniform lines because a third of each short line is wasted space. "Birchwood" fits on the "Thursday" line with room to spare. Reducing to 8-18% keeps the ragged effect without the waste.

**Interaction with existing code.** font_scale.py re-exports `compute_ink_height` which harmonize.py imports. After the change, harmonize.py should import `compute_x_height` directly from ink_metrics.py. The font_scale re-export can remain for any other callers. The pipeline order (font_scale then harmonize) is unchanged.

---

*Prior spec (2026-04-03): Per-word readability improvements (12/12 criteria met). Gray box cluster filter fix, x-height chunk stitching, OCR threshold 0.3->0.4.*

*Prior spec (2026-04-03): Finding-driven quality iteration loop (14/14 criteria met).*

*Prior spec (2026-04-03): Hard words watchlist and targeted quality stress testing (14/14 criteria met).*

*Prior spec (2026-04-02): Human-in-the-loop quality evaluation (25 criteria). Infrastructure built, first feedback loop completed.*

<!-- SPEC_META: {"date":"2026-04-04","title":"Height consistency and score accuracy","criteria_total":14,"criteria_met":0} -->
