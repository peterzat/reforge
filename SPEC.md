## Spec -- 2026-04-01 -- Output quality: consistency, composition, and style fidelity

**Goal:** Make the output look like a handwritten note written by one person. The three biggest visual problems are word size chaos (short words render 2-3x too large), mechanical composition (landscape layout, rigid spacing), and weak style transfer fidelity (generated words don't resemble the input writer's style). Address all three with measurable criteria and ratcheting baselines.

### Acceptance Criteria

#### A. Word size consistency

The current height harmonization (80%-120% of median) is too loose. Short words ("on", "sun", "near") still dominate visually in multi-line output. The demo output (43 words) has a word_height_ratio of 0.91, meaning the tallest word is ~2.2x the shortest after harmonization.

- [ ] A1. On the demo text (43 words, 50 steps, 3 candidates), `word_height_ratio >= 0.95` (max/min ink height ratio). Current: 0.91. This requires tighter harmonization or better per-word normalization. Measure on `make test-full` output.
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

<!-- SPEC_META: {"date":"2026-04-01","title":"Output quality: consistency, composition, and style fidelity","criteria_total":21,"criteria_met":20} -->
