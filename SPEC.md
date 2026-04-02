## Spec -- 2026-04-01 -- Output quality: consistency, composition, and style fidelity

**Goal:** Make the output look like a handwritten note written by one person. The three biggest visual problems are word size chaos (short words render 2-3x too large), mechanical composition (landscape layout, rigid spacing), and weak style transfer fidelity (generated words don't resemble the input writer's style). Address all three with measurable criteria and ratcheting baselines.

### Acceptance Criteria

#### A. Word size consistency

The current height harmonization (80%-120% of median) is too loose. Short words ("on", "sun", "near") still dominate visually in multi-line output. The demo output (43 words) has a word_height_ratio of 0.91, meaning the tallest word is ~2.2x the shortest after harmonization.

- [x] A1. ~~`word_height_ratio >= 0.95`~~ **Closed as infeasible.** Hitting 0.95 required tightening harmonization to 105%/93%, which was metric gaming: scores improved but visual output degraded (letter distortion, over-normalization). Reverted in b2bf61d. The honest floor is 0.91 at 110%/88% thresholds. Structural safeguards (gate/continuous scoring split, SSIM reference comparison, strict baseline management) now prevent this class of regression.
- [x] A2. On the demo text, no single word's ink height exceeds 150% of the median ink height across all words. Add this as a metric in `overall_quality_score()` reported as `height_outlier_ratio` (worst-case word height / median height). Target: <= 1.5.
- [x] A3. The quality regression baseline (`make test-regression`) does not regress: existing metrics stay within 5% of current values.

#### B. Composition and page proportions

The output should look like a handwritten note, not a wide spreadsheet. A note on paper has portrait or near-square proportions, generous margins, and natural line spacing.

- [x] B1. The pipeline accepts a `--page-ratio` CLI argument (default: auto). When set to auto, the compositor targets a width:height ratio between 0.7 and 1.3 (near-square to mild portrait/landscape) by adjusting `DEFAULT_PAGE_WIDTH` based on text length. Short text (1-5 words) should produce a compact result; long text (40+ words) should produce a page-like layout.
- [x] B2. Margins are proportional to page width: left/right margins are 5-8% of page width, top/bottom margins are 3-5% of page height. Current fixed 30px margins look thin on 1600px output and thick on small output.
- [x] B3. The demo output (43 words, 3 paragraphs) has an aspect ratio between 0.7:1 and 1.3:1 (width:height). Current: 1.39:1 (too wide).
- [x] B4. Add `composition_score` to `overall_quality_score()` that measures: (a) aspect ratio proximity to target, (b) margin proportion, (c) line fill consistency (lines shouldn't be wildly different lengths, except last lines of paragraphs). Score 0-1, threshold >= 0.6 on demo text.

#### C. Style fidelity metric

The generated words should resemble the input writer's style. We cannot change the model, but we can (a) measure how well style transferred, and (b) use style similarity in best-of-N candidate selection. Per-word comparison against style reference words on extractable features: stroke weight, slant angle, x-height proportion.

- [x] C1. Add `compute_style_similarity(generated_word_img, style_reference_imgs) -> float` to `reforge/evaluate/visual.py`. Compare: median stroke weight (ink brightness), estimated slant angle (via projection or Hough transform), and x-height to total-height ratio. Return 0-1 score. Validate with a quick test using synthetic images.
- [x] C2. Report `style_fidelity` (mean style similarity across generated words) in `overall_quality_score()` output. Do not include it in the overall weighted score yet (observation-only for this spec). This avoids gating on a metric we haven't validated.
- [x] C3. In `generate_word()` best-of-N selection, add style similarity as a tiebreaker: when two candidates have quality scores within 0.05 of each other, prefer the one with higher style similarity. This uses the style fidelity signal without letting it override readability.

#### D. Claude multimodal quality review

Formalize the existing pattern (user inspects output, identifies issues) into a repeatable development tool. This is a workflow improvement, not a runtime gate.

- [x] D1. Add `make review` target that runs demo.sh then prints the output path and quality metrics in a format suitable for pasting into a Claude conversation for visual review. Include the image path, all metric values, and the text that was generated. No automation of the Claude call itself (that would require API access and is out of scope).
- [x] D2. Document the review workflow in CLAUDE.md: after `make test-full`, run `make review`, paste output + image into Claude conversation, ask for visual assessment. Findings become items for the next spec.

#### E. Generation settings optimization

The three primary generation knobs (DDIM steps, guidance scale, num candidates) have large quality and time impacts but have never been systematically optimized. Current settings were inherited from DiffusionPen defaults or chosen ad hoc. Different test tiers use different settings (medium: 20 steps / 1-2 candidates, demo: 50 steps / 3 candidates) but the choices aren't justified by data. This section establishes optimal settings per tier through experiment.

**Current settings and time costs (per word, RTX 4000 SFF Ada):**

| Setting | Medium tests | Demo/Full | Time impact |
|---------|-------------|-----------|-------------|
| DDIM steps | 20 | 50 | ~linear (20 steps ~ 0.5s, 50 steps ~ 1.2s) |
| Guidance scale | 3.0 | 3.0 | ~2x when >1.0 (two UNet passes per step) |
| Candidates | 1-2 | 3 | ~linear (each candidate = full DDIM loop) |

- [x] E1. **Sweep DDIM steps.** Using the 5-word regression baseline (seed 42), run A/B experiments at steps = {10, 15, 20, 30, 40, 50} with guidance_scale=3.0, candidates=1. Record per-step: overall quality score, OCR accuracy, stroke weight consistency, and wall-clock time. Identify the knee of the quality/time curve. Save results to `experiments/output/steps_sweep.json`.
- [x] E2. **Sweep guidance scale.** At the optimal step count from E1, sweep guidance_scale = {1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0} with candidates=1. Record same metrics. CFG=1.0 (disabled) is already tested in the A/B harness; include it as a reference point. Save results to `experiments/output/guidance_sweep.json`.
- [x] E3. **Sweep candidates.** At optimal steps and guidance from E1/E2, sweep candidates = {1, 2, 3, 5} on 10 diverse words (mix of short/long, common/uncommon). Record quality metrics and total generation time. Identify diminishing returns. Save results to `experiments/output/candidates_sweep.json`.
- [x] E4. **Establish per-tier presets.** Based on E1-E3 results, define named presets in config.py:
  - `PRESET_FAST`: for medium tests and inner-loop iteration. Target: <1s per word, acceptable quality (overall > 0.85).
  - `PRESET_QUALITY`: for demo and final output. Target: best achievable quality, reasonable time (<3s per word).
  - `PRESET_DRAFT`: for quick smoke tests where generation is needed but quality doesn't matter. Target: <0.3s per word.
  Document the rationale (which sweep results drove each choice) in a comment block in config.py.
- [x] E5. **Apply presets to test tiers.** Update test fixtures and demo.sh to use the named presets instead of ad hoc values. Medium tests use PRESET_FAST. Full e2e tests use PRESET_FAST (they validate pipeline correctness, not output quality). demo.sh uses PRESET_QUALITY. The word clipping diagnostic uses PRESET_QUALITY (it needs realistic generation to diagnose real clipping). Verify all test tiers still pass and timings are within budget (quick: <10s, medium: <2min, full: <5min).
- [x] E6. **Add `--preset` CLI argument.** Accept `--preset fast|quality|draft` as an alternative to specifying `--steps`, `--guidance-scale`, `--candidates` individually. `--preset` sets all three; individual flags override preset values. Default preset is `quality`.

#### F. Style input optimization

The current style reference sentence "Quick Brown Foxes Jump High" was chosen for convenience, not optimized for style transfer quality. The UNet hardcodes 5 style images (immutable), but which 5 words, how they're photographed, and how they're preprocessed before encoding are all variable. This section evaluates whether changes to the style input pipeline improve output quality.

**What can vary:**
- The 5 words themselves (letter coverage, stroke diversity, ascenders/descenders)
- Input photo quality (lighting, contrast, resolution, paper texture)
- Preprocessing before encoding (thresholding, contrast normalization, crop tightness)

**What cannot vary:**
- Number of style images (hardcoded 5 in UNet reshape)
- Minimum 4 chars per word (IAM training filter)
- MobileNetV2 encoder architecture (pretrained, frozen)

- [x] F1. **Evaluate word choice coverage.** "Quick Brown Foxes Jump High" provides these stroke features: ascenders (k,h), descenders (p,g), round forms (o,e), diagonal strokes (x,w,k). Missing: the letter 't' (most common English letter, distinctive cross-stroke), 'a' and 'd' (common round+vertical combos), 'l' (pure vertical). Design 3 alternative 5-word sentences that maximize stroke diversity while meeting the >= 4 chars constraint. Generate the demo text with each sentence as style input (using the same hw-sample.png photo, re-segmented if needed, or new photos). Compare overall quality, OCR accuracy, and style fidelity (from C1) across all candidates. Save results to `experiments/output/word_choice_sweep.json`.
- [x] F2. **Evaluate preprocessing impact.** The style input pipeline is: photograph -> segment -> per-word normalize -> encode. Test whether preprocessing changes improve style encoding by running A/B experiments with variations: (a) tighter vs looser crop padding around segmented words, (b) stronger vs weaker contrast normalization (current CLAHE), (c) binarized input (pure black/white) vs grayscale. Use the demo text with PRESET_QUALITY settings. Measure output quality and style fidelity. Save results to `experiments/output/preprocess_sweep.json`.
- [x] F3. **Evaluate photo quality sensitivity.** Take 2-3 photos of the same handwriting under different conditions (good lighting vs poor, high-res vs downscaled, white paper vs lined paper). Run the demo text with each photo. If output quality varies significantly (overall score delta > 0.1), document the sensitivity and add input quality guidance to the CLI `--help` text. If output is robust to input quality, document that finding. Save results to `experiments/output/photo_quality_sweep.json`.
- [x] F4. **Apply findings.** If any experiment from F1-F3 produces a measurable improvement (overall score improvement > 0.05 or style fidelity improvement > 0.1), update the defaults: change the recommended reference sentence in CLAUDE.md and config.py, update preprocessing parameters, or add input quality validation. If the current setup is already near-optimal, document that conclusion in the experiment results.

### Context

**Word size problem root cause.** DiffusionPen generates each word independently on a 64x256 canvas. Short words (1-3 chars) fill the full canvas height; long words use proportionally less. The font normalization pass targets different heights for short vs long words, and the harmonization pass clips outliers. But the thresholds are too loose for the demo text, where short function words ("on", "the", "and") appear next to 6-8 char words, creating visible size jumps. Tightening harmonization risks over-normalizing legitimate height variation (ascenders, descenders), so the fix needs to preserve natural variation while eliminating outliers.

**Composition problem root cause.** The fixed 800px page width (1600px after 2x upscale) was chosen for development convenience, not aesthetics. For the 43-word demo text, this creates 6-7 lines of text in a wide landscape format. A real handwritten note would be closer to square or portrait. The page width should adapt to text volume: fewer words = narrower page, more words = standard page width. Margins should scale proportionally.

**Style fidelity limitations.** DiffusionPen's style transfer is the result of the pretrained model's triplet-loss training on IAM data. We cannot improve it without retraining. However, we can (a) measure it, which helps identify when generation quality degrades, and (b) use it as a selection signal in best-of-N, which biases toward more faithful output. The style similarity metric should focus on features that are reliably extractable from small grayscale word images: stroke weight, slant, and height proportions. Letter-level shape matching is too noisy at 64px height.

**Direct input/output comparison.** Comparing the full style input image against the full output image is not meaningful: one is 5 isolated words on textured paper, the other is 43 composed words on white canvas. Per-word feature comparison (criterion C1) is the right granularity. Whole-image style metrics (Gram matrices, neural style loss) would require a feature extractor and add complexity without clear benefit at this stage.

**Generation settings are unoptimized.** The current defaults (50 steps, guidance 3.0, 3 candidates) were inherited from DiffusionPen examples and early experimentation. Medium tests use 20 steps / 1-2 candidates to stay under the 2-minute budget, but this was chosen for speed, not because 20 steps is the optimal quality/time tradeoff. The gap between test quality (20 steps) and demo quality (50 steps) means tests may miss quality issues that only appear at higher step counts, or conversely, tests may be slower than necessary. A systematic sweep will identify the actual quality/time curve and let us set each tier's parameters with data rather than intuition.

**Style input is unvalidated.** "Quick Brown Foxes Jump High" was chosen as a pangram-adjacent phrase that meets the >= 4 chars constraint, but its effectiveness for style transfer has never been tested against alternatives. The MobileNetV2 style encoder extracts visual features (not letter identities), so what matters is stroke diversity: does the 5-word set contain enough variety in ascenders, descenders, curves, verticals, and widths to characterize the writer's style? The current set has decent variety but notable gaps (no 't', no 'a', no pure verticals like 'l'). Whether these gaps matter depends on how the encoder uses the features, which is empirical, not theoretical.

**Preprocessing may leave quality on the table.** The current pipeline applies CLAHE contrast normalization and standard cropping to segmented words before encoding. These parameters were set for visual clarity, not optimized for what the style encoder wants to see. The encoder was trained on IAM dataset images with specific preprocessing; matching that preprocessing more closely might improve style transfer. Alternatively, the encoder may be robust to preprocessing variation. Only experiments will tell.

**Time budget constraints.** The autonomous coding loop depends on fast feedback: `make test-quick` at 0.8s, `make test-regression` at ~14s, `make test` at ~2min. Any preset change must respect these budgets. The demo can take longer (current: ~2min for 43 words) since it runs less frequently, but should not exceed ~5min. The sweep experiments themselves are one-time costs that run in `experiments/` and produce JSON results for analysis.

---
*Prior spec (2026-04-01): Test reliability and loop cadence (7/7 criteria met).*

<!-- SPEC_META: {"date":"2026-04-01","title":"Output quality: consistency, composition, and style fidelity","criteria_total":21,"criteria_met":21,"status":"closed"} -->

---

## Spec -- 2026-04-02 -- Quality assurance trust and scoring accuracy

**Goal:** Make the autonomous coding loop trustworthy. After the A1 regression (metric gaming passed all tests but degraded visual output), we overhauled the QA infrastructure: gate/continuous scoring split, SSIM reference comparison, strict baseline management, quality ledger. This spec closes the remaining gaps: metrics that aren't tracked, outputs that aren't gated, trends that aren't detected, and lessons that aren't structurally remembered.

The overall quality score is now 0.90 (down from insensitive 0.984). The weakest continuous metric is composition_score at 0.69. The regression baseline tracks 7 metrics + SSIM but excludes OCR accuracy and style fidelity. The demo output (43 words) has no quality gate. The quality ledger records data but nothing reads it for trend detection.

### Acceptance Criteria

#### A. Composition score improvement

The composition_score (0.69) is the weakest continuous metric and has 0.20 weight in the overall score. It is the biggest lever for overall improvement. The score is the mean of three sub-scores: aspect ratio proximity to 1.0, margin proportion (5-8% horizontal, 3-5% vertical), and line fill consistency. The margin scoring function (`_margin_score` in `reforge/evaluate/visual.py:341`) penalizes any deviation from the target range at 1/0.05 = 20x rate, which is harsh. The line fill computation uses a fixed 0.88 usable-width estimate that may not match actual margins.

- [ ] A1. Diagnose which sub-score(s) are dragging composition_score down. Add diagnostic output to the regression test that prints aspect_score, margin_score, and fill_score separately when run with `-s`. Identify the primary bottleneck.
- [ ] A2. If margins are the bottleneck: widen the acceptable margin range or soften the penalty curve. The current 5-8% horizontal range with a 20x penalty cliff was set without calibration. Measure actual margins on the 5-word and 43-word outputs and adjust the target range to encompass them. The range should reflect what looks good, not an arbitrary target.
- [ ] A3. If line fill is the bottleneck: fix the usable-width estimate. Currently hardcoded at `w * 0.88`; it should derive from actual margin positions. Natural handwriting has line-length variation; the penalty for inconsistency (std / 0.3) may be too strict.
- [ ] A4. After fixes, composition_score >= 0.80 on the 5-word regression baseline. Verify the demo output (43 words) also improves. Do not game this: if the score improves but the output looks worse, revert.

#### B. OCR in the regression baseline

The regression test (`tests/medium/test_quality_regression.py`) generates 5 words but doesn't pass `words` to `overall_quality_score`, so OCR accuracy is never computed in the baseline. OCR is the most meaningful quality signal: it measures whether generated words are readable. It would have caught the A1 regression ("The" rendered as "Tle").

- [ ] B1. Pass `TEST_WORDS` to `overall_quality_score` in the regression test so OCR accuracy is computed. Add `ocr_accuracy` to `TRACKED_METRICS`. Rebaseline.
- [ ] B2. Add `ocr_min` as a gate: if any word has OCR < 0.3, the regression test fails regardless of other metrics. This catches single-word unreadability that the mean OCR score would average away.
- [ ] B3. Verify that the regression test time stays under 20s with OCR added (OCR uses TrOCR model loading).

#### C. Style fidelity evaluation

Style fidelity is computed when style reference images are provided but is currently observation-only (excluded from the overall score). The regression test doesn't pass style references, so it's never computed there.

- [ ] C1. Pass style reference images (the segmented words from hw-sample.png) to `overall_quality_score` in the regression test. Record `style_fidelity` in the baseline. This is observation-only initially.
- [ ] C2. Run the regression test 5 times and measure style_fidelity variance. If the variance is low (std < 0.05), it's stable enough to track as a regression metric. If high, keep it observation-only and document why.
- [ ] C3. If stable (C2 passes): add `style_fidelity` to `QUALITY_CONTINUOUS_WEIGHTS` with weight 0.10, redistributing from other metrics (reduce baseline_alignment to 0.05 and composition_score to 0.15, since baseline_alignment tends to saturate). Rebaseline.

#### D. Full-output quality gate

The regression test covers 5 words with seed 42. The demo generates 43 words across 3 paragraphs with PRESET_QUALITY (50 steps, 3 candidates). A change could pass the 5-word test but degrade the full output. `make test-full` runs demo.sh but only checks that the pipeline completes and basic thresholds are met (ink_contrast > 0.3).

- [ ] D1. Add a quality baseline for the full demo output. Store in `tests/full/demo_baseline.json` with the same format as the medium baseline. The full test compares against this baseline with the same tolerance (0.05). Use `--update-demo-baseline` to regenerate.
- [ ] D2. Add SSIM comparison for the demo output against a stored reference image (`tests/full/demo_reference.png`). Threshold: 0.70 (looser than the 5-word test because 43 words with 3 candidates introduces more stochasticity).
- [ ] D3. The full test must stay under 5 minutes. If adding the quality gate pushes it over, reduce demo text length or candidates rather than removing the gate.

#### E. Trend detection from quality ledger

The quality ledger (`tests/medium/quality_ledger.jsonl`) records metrics per regression test run. `metric_trend()` and `recent_runs()` exist in `reforge/evaluate/ledger.py` but nothing uses them. A slow downward drift across multiple runs (each within the 0.05 tolerance) would accumulate undetected.

- [ ] E1. Add `detect_drift(ledger_path, metric, window, threshold)` to `reforge/evaluate/ledger.py`. Returns True if the metric has declined by more than `threshold` over the last `window` runs (comparing first vs last in the window). Default window=5, threshold=0.08.
- [ ] E2. At the end of the regression test, check for drift on all continuous metrics. If drift is detected, print a warning (not a failure) with the metric name, trend values, and how much it declined. This is a soft gate: it alerts but doesn't block.
- [ ] E3. Add a quick test that validates `detect_drift` on synthetic ledger data: stable metrics return False, declining metrics return True, insufficient data returns False.

#### F. Structured experiment log

When parameter changes are tried and kept or reverted, the lesson lives in git history and prose memory files. A future agent session can read memory but can't query "what parameter changes have been tried for harmonization and what happened?" A structured log enables learning from past experiments.

- [ ] F1. Create `docs/experiment-log.jsonl` with one entry per experiment outcome. Schema: `{"date", "area" (e.g. "harmonization", "generation", "postprocessing"), "change" (what was tried), "expected" (what we expected), "metrics_before" (dict), "metrics_after" (dict), "verdict" ("keep"|"revert"|"modify"), "lesson" (what we learned)}`. This file is committed to git.
- [ ] F2. Backfill the A1 incident as the first entry: area="harmonization", change="tightened thresholds from 110%/88% to 105%/93%", expected="word_height_ratio >= 0.95", metrics_before={word_height_ratio: 0.91, overall: 0.984}, metrics_after={word_height_ratio: 1.00, overall: 0.999}, verdict="revert", lesson="metric gaming: visual quality degraded despite score improvement; thresholds must not be tightened beyond 110%/88%".
- [ ] F3. Add a helper function `reforge/evaluate/experiments.py:log_experiment()` that appends to the log and prints a summary. Wire it into the development workflow: after any A/B experiment that results in a keep or revert decision, call `log_experiment()`.
- [ ] F4. Add a query function `reforge/evaluate/experiments.py:query_experiments(area=None, verdict=None)` that filters the log. A future agent session can call `query_experiments(area="harmonization")` to see what's been tried.

### Context

**Why composition_score matters now.** With the gate/continuous scoring split, composition_score went from excluded (observation-only) to a 0.20-weighted continuous metric. At 0.69, it drags the overall score from what would be ~0.95 (if composition were 1.0) down to 0.90. This is correct: the composition needs work. But the scoring function itself may be miscalibrated. The margin ranges (5-8% horizontal, 3-5% vertical) and penalty curves were set without measuring actual output. If the output looks good but the score is low, the scoring function needs recalibration, not the output.

**Why OCR in the baseline is critical.** The A1 regression produced "The" as "Tle" and all metrics passed. OCR accuracy would have caught this immediately. Every other metric (contrast, cleanliness, height ratio) measures aesthetics, not readability. Without OCR in the baseline, the regression test is blind to the single most important quality dimension: can humans read it?

**Why full-output gating matters.** The 5-word seed-42 test generates single-line output. The demo generates multi-paragraph output with line wrapping, paragraph spacing, and dynamic page sizing. Composition issues, baseline alignment problems, and page-level artifacts only appear at scale. The regression test catches word-level and small-scale regressions; the full-output gate catches system-level regressions.

**Why trend detection matters.** The 0.05 tolerance means each run can lose 4.99% on any metric. After 5 runs of 4% decline, a metric drops from 0.90 to 0.72, and no individual run failed. The ledger has the data to catch this; it just needs a consumer.

**Why structured experiment logging matters.** The autonomous coding loop tries things, measures results, and decides whether to keep or revert. Without a structured record, each session starts fresh: it can read memory ("don't tighten harmonization") but can't query the full history of what was tried and why. This is how institutional knowledge accumulates in a coding loop that doesn't have a persistent human memory.

**Relationship to QA infrastructure overhaul.** This session restructured the scoring (gate/continuous split), fixed baseline management (strict auto-update), added SSIM comparison, added A/B baseline floors, and created the quality ledger. That work made the metrics trustworthy. This spec makes the metrics comprehensive (OCR, style fidelity, full output) and the learning loop durable (trend detection, experiment log).

---
*Prior spec (2026-04-02): Output quality: consistency, composition, and style fidelity (21/21 criteria met, A1 closed as infeasible).*
*Prior spec (2026-04-01): Test reliability and loop cadence (7/7 criteria met).*

<!-- SPEC_META: {"date":"2026-04-02","title":"Quality assurance trust and scoring accuracy","criteria_total":20,"criteria_met":0} -->
