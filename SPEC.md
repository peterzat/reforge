## Spec -- 2026-04-01 -- Quality convergence: from scaffold to readable handwriting

**Goal:** Transform reforge output from "words splattered on a page" to consistently readable handwritten text by decomposing quality into progressive correctness tiers (single word, word pair, full line), instrumenting each tier with measurable metrics, and establishing an autonomous experimentation loop that drives continuous improvement through A/B testing with compute-backed iteration.

### Acceptance Criteria

#### Tier 0: Single-word correctness

- [ ] A single generated word (4-8 chars, e.g. "brown") passes visual inspection by CV metrics: ink contrast > 0.5, no gray boxes, background cleanliness > 0.7, ink occupies 20-80% of image height
- [ ] A single generated short word (1-3 chars, e.g. "I", "an") meets the same thresholds without being oversized relative to longer words (ink height within 1.5x of a 6-char word generated with the same style)
- [ ] Best-of-N candidate selection demonstrably improves quality: the chosen candidate scores higher than the median of N candidates on at least 80% of runs across a 10-word test set
- [ ] Per-word postprocessing (all 5 defense layers) eliminates gray box artifacts on 95%+ of generated words when tested across a batch of 20+ words of varying length

#### Tier 1: Word-pair consistency

- [ ] Two adjacent generated words have stroke weight consistency score > 0.7 (as measured by `check_stroke_weight_consistency`) after harmonization
- [ ] Two adjacent generated words have height ratio score > 0.6 (as measured by `check_word_height_ratio`) after font normalization and harmonization
- [ ] Ink darkness (median ink pixel value) varies by less than 25 brightness levels between any two words in a 5-word sequence after harmonization

#### Tier 2: Line-level composition

- [ ] A composed line of 5-8 words has baseline alignment score > 0.7 (as measured by `check_baseline_alignment`)
- [ ] Word spacing within a line is visually consistent: the coefficient of variation of inter-word gaps is < 0.3
- [ ] No word in a composed line overlaps another word or extends beyond the page margins
- [ ] A composed line has overall quality score > 0.5 (as measured by `overall_quality_score`)

#### Tier 3: Experimentation infrastructure

- [ ] An A/B experiment can be run against a single parameter (e.g. guidance scale, DDIM steps, font normalization target) and produces a numeric before/after comparison with statistical context (mean, std across multiple runs, not just one sample)
- [ ] Experiment results are logged to a machine-readable file (JSON or CSV) so that parameter improvements accumulate across sessions
- [ ] A "quality regression test" exists that generates a fixed set of words with a fixed seed, computes quality metrics, and fails if any metric drops below a recorded baseline
- [ ] The A/B harness supports multi-word experiments (not just single-word), testing at minimum a 5-word line to capture composition-level quality effects

#### Tier 4: Quality floor enforcement

- [ ] `demo.sh` output has overall quality score > 0.5
- [ ] `demo.sh` output has zero gray box detections
- [ ] `demo.sh` output has ink contrast > 0.4
- [ ] Quick tests include at least one test per Tier 0 and Tier 1 criterion that validates the metric computation against synthetic images (not requiring GPU)
- [ ] Medium tests include at least one test per Tier 2 criterion that generates real words (requires GPU) and asserts the quality threshold

### Context

The initial scaffold spec (26/26 criteria met) delivered a working pipeline, but the output quality is poor: illegible words, inconsistent stroke widths, possible white/gray block artifacts, and no acceptance tests that would catch these problems. The pipeline code exists and runs; the issue is that parameter values, postprocessing thresholds, and composition logic have not been tuned against measurable quality targets.

**Incremental decomposition.** Quality problems compound: a bad single word cannot be fixed by better composition, and inconsistent word pairs cannot be fixed by better line layout. The tier structure (single word, word pair, line, experiment, enforcement) forces bottom-up correctness. Each tier's criteria must pass before the next tier's criteria are meaningful.

**Experimentation philosophy.** This is an applied science project. The right guidance scale, DDIM step count, font normalization target, ink threshold, and dozens of other parameters are not knowable a priori. They must be discovered through systematic A/B testing. The machine has 20GB VRAM and 14 CPU cores; experiments should exploit this compute to run multiple variants in parallel and build statistical confidence, not rely on single-sample comparisons.

**Measurement over intuition.** Every quality criterion above is tied to a specific metric function in `reforge/evaluate/visual.py` or can be computed from pipeline outputs. "Looks better" is not a criterion. If a quality dimension cannot be measured by CV metrics, add a metric function first, then add the criterion.

**Autonomous improvement loop.** The medium test tier and A/B harness exist precisely so that a coding agent can: change a parameter, run a test, observe the numeric result, and decide whether to commit or revert. The quality regression test (Tier 3) prevents improvements in one dimension from degrading another. Baseline recordings accumulate over time, ratcheting the quality floor upward.

**Coding practices (from zat.env).** Work in small increments. Get one tier working before moving to the next. Run tests after each change. If a change regresses a metric, revert and try a different approach. Do not stack multiple untested parameter changes. Write experiment results to disk so that a fresh session can pick up where the last left off.

**What this spec does not prescribe.** It does not specify which parameter values to use, which postprocessing approach is correct, or what the "right" guidance scale is. Those are implementation decisions to be discovered through experimentation. The spec defines the quality floor (minimum metric thresholds) and the infrastructure to keep improving above that floor.

---
*Prior spec (2026-03-31): Scaffold reforge repo with full pipeline and demo (26/26 criteria met).*

<!-- SPEC_META: {"date":"2026-04-01","title":"Quality convergence: from scaffold to readable handwriting","criteria_total":20,"criteria_met":0} -->
