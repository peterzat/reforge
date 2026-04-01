## Spec -- 2026-04-01 -- Readable output: fix clipped characters, add OCR validation, repair quality score

**Goal:** Make every generated word fully readable by fixing the left-character clipping bug ("The" renders as "he"), adding OCR-based accuracy measurement so the autonomous loop can detect and reject unreadable words, and repairing the overall quality score so it reflects actual output quality rather than passing on broken output.

### Acceptance Criteria

#### Character clipping fix

- [x] The word "The" generates with all three characters visible and OCR-readable (no left-edge clipping of the "T") across 5 consecutive runs with the default style
- [x] The word "the" generates with all three characters visible and OCR-readable across 5 consecutive runs with the default style
- [x] Single-character words ("I", "A") generate with the character visible and not blanked by postprocessing
- [x] No postprocessing defense layer (body-zone noise removal, isolated-cluster filter, word-level gray cleanup, compositor ink threshold) removes ink pixels that are contiguous with the main ink body of the word

#### OCR accuracy measurement

- [x] An OCR evaluation function exists that takes a word image (numpy array) and the intended text, returns a character-level accuracy score in [0, 1] (1.0 = perfect match)
- [x] The OCR function uses a pretrained model (not a hand-rolled heuristic) capable of reading single handwritten words; the model runs on CPU without requiring additional GPU VRAM during inference
- [x] `overall_quality_score()` incorporates OCR accuracy when a target word is provided, weighting it as the single most important factor (readability matters more than aesthetics)
- [x] `demo.sh` prints per-word OCR accuracy alongside existing quality metrics
- [x] A quick test validates the OCR function against a synthetic word image with known text

#### Ink contrast consistency

- [x] After harmonization, the standard deviation of median ink brightness across all words in a 10-word sequence is less than 15 brightness levels (currently allowed up to 25)
- [x] Stroke weight harmonization shift strength is tunable via config and validated by a medium-tier A/B test comparing before/after consistency scores

#### Quality score repair

- [x] `overall_quality_score()` returns a score below 0.5 when any word in the output has OCR accuracy below 0.5 (unreadable words must tank the overall score)
- [x] `overall_quality_score()` returns a score below 0.5 when more than 20% of word images contain fewer ink pixels than expected for their target text (detecting blank or near-blank generations)
- [x] The quality gate in `demo.sh` fails if per-word OCR accuracy averaged across all words drops below 0.6
- [x] A quick test validates that `overall_quality_score()` correctly penalizes a composed image containing one blank/empty word among otherwise good words

#### Autonomous improvement loop

- [x] The `generate_word()` function rejects candidates where OCR accuracy for the target word is below 0.3, generating a replacement candidate (up to 2 retries beyond num_candidates) before accepting the best available
- [x] The A/B harness can compare OCR accuracy distributions (not just visual quality scores) between experiment arms, enabling parameter searches that optimize for readability
- [x] Medium tests include an OCR accuracy assertion: generating "The quick brown" (3 words) must achieve average per-word OCR accuracy above 0.5

### Context

**Inspection findings (2026-04-01).** Human inspection of demo.sh output revealed: (1) no gray boxes (prior defense layers working), (2) perfect background cleanliness, (3) ink contrast improved but still variable, (4) many words unreadable or partially occluded, (5) "the"/"The" consistently renders as "he" with the first character clipped, (6) the overall quality score passes despite visibly broken output.

**Root cause analysis: character clipping.** The "T" in "The" is likely being removed by body-zone noise removal (Layer 2) or isolated-cluster filtering (Layer 3). The capital T has a thin vertical stem that may not pass the body-zone ink threshold (5% of body-zone rows), causing the column to be blanked. The lowercase "t" has a similar risk with its crossbar extending above the body zone. The fix should preserve columns that are contiguous with the main ink body, even if their individual body-zone ink ratio is low. This is the highest-priority fix because it likely affects many words with ascenders or thin initial strokes (t, T, l, f, i, etc.).

**Root cause analysis: quality score.** The overall quality score averages component scores (gray_boxes, ink_contrast, background_cleanliness) that are all aesthetic rather than functional. A page where every word is illegible but has good contrast and clean background scores well. The score must incorporate readability (OCR accuracy) as the dominant factor. Without this, the autonomous improvement loop optimizes for the wrong thing.

**OCR model selection.** TrOCR (microsoft/trocr-small-handwritten) is a transformer-based model pretrained on handwritten text recognition. It runs on CPU, handles single-word images, and is available via HuggingFace transformers (already a dependency). It is the natural choice: no new dependencies, no additional GPU VRAM, and it is specifically trained on handwritten text similar to DiffusionPen output. Alternative: PaddleOCR or EasyOCR, but these add heavy dependencies for marginal benefit on single-word English handwriting.

**Coding practices (from zat.env).** Work in small increments. Fix the character clipping first (it affects the most words). Then add OCR measurement (it gives the loop a signal). Then repair the quality score (it makes the loop act on the signal). Then wire into the autonomous loop (the loop can now self-improve). Run tests after each increment. If an OCR model choice proves too slow or inaccurate, try a lighter alternative before over-engineering.

**What this spec does not prescribe.** It does not specify which postprocessing layers to modify, what threshold values to use, or how to restructure the body-zone algorithm. Those are implementation decisions to be discovered by reading the code, testing hypotheses, and measuring results. The spec defines what the output must look like (readable words, accurate scores) and what measurement tools must exist (OCR function, improved quality score).

---
*Prior spec (2026-04-01): Quality convergence: from scaffold to readable handwriting (20/20 criteria met).*

<!-- SPEC_META: {"date":"2026-04-01","title":"Readable output: fix clipped characters, add OCR validation, repair quality score","criteria_total":18,"criteria_met":18} -->
