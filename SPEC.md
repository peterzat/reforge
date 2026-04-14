## Spec -- 2026-04-14 -- Research: approaches from handwriting synthesis literature

**Goal:** Survey handwriting synthesis literature for techniques that can improve reforge's wrapper layer, then prototype the most promising ones. The project has hit wrapper-layer ceilings on several fronts (invisible punctuation, stitching baseline mismatch, candidate scoring that disagrees with humans). This turn steps back from incremental tuning to find better algorithms from the research literature, prototype the top candidates, and produce a written assessment of what is worth integrating.

### Acceptance Criteria

#### A. Research document

- [ ] A1. `docs/research_survey.md` exists and covers at least: (a) Graves 2013 sequence generation and its relevance to synthetic stroke generation, (b) Bezier curve approaches to programmatic glyph synthesis, (c) ink-profile or cross-correlation methods for baseline alignment in stitching, (d) learned perceptual metrics (HWD, LPIPS, VGG-based features) for candidate scoring, (e) post-DiffusionPen models (DiffBrush, One-DM, WriteViT) and whether any are worth evaluating as replacements. Each section states what the approach is, which reforge problem it addresses, and a concrete recommendation (integrate / prototype / skip / requires model swap).
- [ ] A2. The document includes a summary table mapping each open problem to the recommended wrapper-layer fix, with citations. Problems covered: trailing punctuation invisible, chunk stitching baseline mismatch, candidate selection disagreement, stroke weight inconsistency.

#### B. Synthetic punctuation prototype (Bezier curves)

- [ ] B1. A `make_synthetic_mark(mark, ink_intensity, body_height)` function exists (in generator.py or a new module) that renders at least: comma, period, question mark, exclamation mark, semicolon. Each mark uses Bezier curves or parametric strokes (not pixel-by-pixel row loops like the current apostrophe). The function returns a grayscale ndarray suitable for stitching.
- [ ] B2. A `strip_and_reattach_punctuation(word, img)` pipeline helper exists that: detects trailing punctuation on a word, strips it before generation, generates the base word, then appends the synthetic mark at the correct baseline position. Works for at least the 5 marks in B1 plus the existing apostrophe path.
- [ ] B3. `make test-quick` passes. Unit tests verify each mark type produces non-empty output with ink pixels, correct baseline positioning (comma/semicolon below baseline, period at baseline, exclamation/question extending above), and dimensions proportional to body_height.
- [ ] B4. `make test-regression` passes on all 3 seeds. Primary gates hold.
- [ ] B5. Run `make test-human EVAL=punctuation,composition`. Present results in terminal. Punctuation rating improves from 1/5 baseline. Composition does not regress.

#### C. Stitching alignment prototype (ink-profile cross-correlation)

- [ ] C1. An alternative alignment function exists that uses vertical ink-density profile cross-correlation (instead of single-point ink-bottom alignment) to find the optimal vertical offset between chunks. Can be a standalone function or a flag/mode in `stitch_chunks`.
- [ ] C2. A/B comparison: generate "understanding" with both alignment methods (current ink-bottom vs. profile cross-correlation), produce a visual comparison via `create_comparison_image`. Save to `experiments/output/`.
- [ ] C3. If the prototype visually improves alignment (agent or human judgment via qpeek), integrate it into `stitch_chunks` and verify `make test-regression` passes. If it does not improve, document why in the research document and leave stitch_chunks unchanged.

#### D. Candidate scoring analysis

- [ ] D1. `scripts/candidate_preference_analysis.py` exists. It reads all review JSON files from `reviews/human/`, extracts candidate eval data (human pick vs. metric pick, per-candidate scores), and reports: agreement rate, which sub-scores correlate with human picks, and a recommended weight vector (even if it is "insufficient data, need N more reviews").
- [ ] D2. If N >= 6 candidate reviews exist with per-candidate score data, fit a simple model (logistic regression or score reweighting) to maximize agreement. Report the cross-validated agreement rate. If data is insufficient, document the minimum N needed and what data to collect.

#### E. Integration gates

- [ ] E1. `make test-quick` passes after all changes.
- [ ] E2. `make test-regression` passes on all 3 seeds.
- [ ] E3. No existing human eval ratings regress (composition, baseline, hard_words hold at current levels or improve).

### Context

**Prior turn (2026-04-14):** X-height normalization, punctuation polish, eval fixes (14/14 criteria met). Body-zone equalization fixed "gray too big" (baseline improved 3/5 to 4/5). Contraction tight-crop padding increased. New punctuation eval type revealed trailing punctuation is invisible (1/5). Stitch eval suspended. Composition last 5: 3, 3, 3, 4, 4 (median 3/5, target 4/5).

**Research findings driving this spec:**
- Graves 2013 (arxiv:1308.0850) demonstrated stroke-level sequence generation with mixture density networks. Relevant not as a replacement model but as evidence that programmatic stroke generation works for characters the base model cannot render. The same paper noted IAM's punctuation limitation (most punctuation collapsed to a generic non-letter label), which persists into DiffusionPen.
- Bezier curve approaches (Pictographic Character Reconstruction, arxiv:2511.00076) frame glyph synthesis as program synthesis over cubic Bezier splines. For geometrically simple marks (dots, short curves, tapered strokes), Bezier templates parameterized by ink weight and height produce smoother output than pixel loops.
- VATr++ (Pippi et al., 2024) documented that IAM "punctuation marks lose their scale and spatial context" when treated as standalone entries, explaining why DiffusionPen ignores trailing punctuation.
- HWD (Handwriting Distance, BMVC 2023) uses VGG16 features trained on handwriting for style comparison. Its backbone could be repurposed for per-sample candidate scoring.
- DiffBrush (ICCV 2025) generates full text lines, eliminating the word-level stitching problem entirely. It is the most direct successor to DiffusionPen but would require a model swap (out of scope for this turn, but worth assessing).
- Ink-profile cross-correlation for stitching alignment uses the full vertical ink distribution rather than single-point baseline detection, which should be more robust to the chunk-to-chunk variance that breaks current alignment.

**Scope limits:** This turn produces a research document, prototypes, and an analysis. It does not swap the base model, retrain anything, or attempt to fix the Plateaued sizing issue. Prototypes that improve quality get integrated; those that don't get documented as negative results.

**zat.env practices:** Work in small committable increments. Prototype in isolation before integrating. If two consecutive attempts at a prototype fail, document the negative result and move on. GPU tests aggressively.

---
*Prior spec (2026-04-14): X-height normalization, punctuation polish, eval fixes (14/14 criteria met).*

<!-- SPEC_META: {"date":"2026-04-14","title":"Research: approaches from handwriting synthesis literature","criteria_total":14,"criteria_met":0} -->
