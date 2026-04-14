# Research Survey: Handwriting Synthesis Techniques for Reforge

Surveyed 2026-04-14. Goal: identify wrapper-layer improvements from the
handwriting synthesis literature that can address reforge's open quality
problems without retraining or swapping the base model.

## Open Problems

| # | Problem | Current state | Root cause |
|---|---------|---------------|------------|
| P1 | Trailing punctuation invisible | 1/5 human rating | DiffusionPen ignores trailing punctuation marks (IAM dataset bias) |
| P2 | Chunk stitching baseline mismatch | Stitch eval suspended | Single-point ink-bottom alignment is fragile under generation variance |
| P3 | Candidate selection disagrees with human | 7/8 reviews disagree | Quality scoring weights do not match human perception |
| P4 | Stroke weight inconsistency | Acceptable (5 reviews identical A/B) | Per-word generation variance; harmonization cannot fix within-word variation |

## A. Graves 2013: Sequence Generation with RNNs

**Reference:** Graves, "Generating Sequences with Recurrent Neural Networks,"
arXiv:1308.0850 (2013).

**What it is:** Mixture density network (MDN) over pen stroke sequences. The
model generates (dx, dy, pen-up) tuples conditioned on a character sequence.
Produces smooth, continuous strokes that form recognizable characters. The
model was trained on the IAM online handwriting dataset (pen trajectories,
not images).

**Relevance to reforge:**

1. *Programmatic glyph generation.* Graves demonstrated that simple characters
   (periods, commas, short strokes) can be generated from a small MDN. This
   validates the synthetic punctuation approach: for geometrically simple marks,
   a parametric model (Bezier curves, stroke sequences) produces more reliable
   output than forcing a diffusion model to render marks it was not trained to
   produce.

2. *IAM punctuation limitation.* Graves noted that IAM's character-level
   labeling collapses most punctuation into generic non-letter categories. This
   observation was confirmed by VATr++ (Pippi et al., 2024): punctuation marks
   "lose their scale and spatial context" when treated as standalone entries.
   DiffusionPen inherits this limitation. The fix is to bypass the model for
   punctuation, not to hope it learns to render marks it was never trained on.

**Recommendation:** Skip as a model replacement (online handwriting is a
different modality). Use as theoretical backing for the synthetic punctuation
approach (B1/B2).

## B. Bezier Curve Approaches to Glyph Synthesis

**Reference:** "Pictographic Character Reconstruction via Program Synthesis
with Cubic Bezier Curves," arXiv:2511.00076 (2025).

**What it is:** Frames glyph synthesis as program synthesis over cubic Bezier
splines. A set of parametric Bezier curves, each defined by 4 control points,
is optimized to match a target glyph. For simple marks (dots, short curves,
tapered strokes), hand-tuned Bezier templates produce smooth, resolution-
independent output.

**Relevance to reforge (P1):**

The current `make_synthetic_apostrophe()` uses pixel-by-pixel row loops with
linear taper. The result is functional but blocky. Cubic Bezier curves offer:

- Smooth stroke profiles with natural taper (thick-to-thin or thin-to-thick)
  via the control point spacing.
- Consistent rendering at any body_height scale (the curve is defined in
  normalized coordinates, then rasterized).
- Easy parameterization: ink_intensity controls fill darkness, body_height
  controls rasterization resolution.

For the 5 target marks (comma, period, question mark, exclamation mark,
semicolon), each mark decomposes into 1-3 Bezier curves:

| Mark | Curves | Description |
|------|--------|-------------|
| Period (.) | 1 | Filled circle at baseline (dot via short thick stroke) |
| Comma (,) | 1 | Tapered curve descending below baseline |
| Exclamation (!) | 2 | Tapered vertical stroke + dot below |
| Question (?) | 2-3 | Open curve at top + dot below |
| Semicolon (;) | 2 | Dot above baseline + comma below |

**Recommendation:** Prototype (B1). Replace pixel-loop rendering with Bezier
curve rasterization for all synthetic marks. The apostrophe can also be
migrated to this approach for consistency.

## C. Ink-Profile Cross-Correlation for Stitching Alignment

**References:** Standard technique in document image analysis. Used in text
line segmentation (Manmatha & Srimal, 1999), word spotting (Rath & Manmatha,
2007), and binarization evaluation. Not a single paper but a well-established
signal processing approach.

**What it is:** Instead of aligning chunks by a single-point baseline (last
ink row), compute the vertical ink-density profile of each chunk (sum of ink
pixels per row, normalized). Then find the vertical offset that maximizes the
cross-correlation between overlapping profiles. This uses the full vertical
ink distribution, not just one row.

**Relevance to reforge (P2):**

The current `stitch_chunks` function aligns by ink bottom:
```python
ink_rows = np.any(chunk < INK_THRESH, axis=1)
last_ink = len(ink_rows) - 1 - np.argmax(ink_rows[::-1])
```

This is brittle because:
- A single outlier row (descender tip, noise) shifts the entire alignment.
- Chunks with different ascender/descender distributions have different ink-
  bottom positions even when their body zones are at the same vertical offset.
- The x-height normalization pass changes chunk dimensions, but the subsequent
  ink-bottom measurement can be thrown off by residual noise.

Cross-correlation alignment:
1. Compute row-wise ink density: `profile[r] = sum(chunk[r, :] < INK_THRESH) / width`
2. For each candidate vertical offset `d`, compute `corr(profile_A, shifted_profile_B)`
3. Pick the offset with maximum correlation

This naturally weights the body zone (dense ink, high profile values) more
than ascenders and descenders (sparse ink, low profile values). The body zone
dominates the correlation signal, producing alignment that matches the
perceived baseline.

**Recommendation:** Prototype (C1). Implement as an alternative alignment
function in `stitch_chunks`, A/B test against current ink-bottom alignment.
If it visually improves "understanding" and similar stitched words, integrate.

**Result (2026-04-14):** Cross-correlation alignment dramatically improved
"understanding" stitching. The ink-bottom method placed "tanding" well above
"unders" (the problem flagged in 4+ human reviews); cross-correlation aligned
both chunks to the same baseline. Integrated as the new default in
`stitch_chunks`. Comparison saved to `experiments/output/stitch_alignment_comparison.png`.

## D. Learned Perceptual Metrics for Candidate Scoring

**References:**
- HWD (Handwriting Distance), BMVC 2023. VGG16 features trained on handwriting
  for style-level comparison.
- LPIPS (Zhang et al., 2018). Learned perceptual similarity using AlexNet/VGG
  activations, trained on human perceptual judgments.
- FID/KID: Frechet/Kernel Inception Distance for distribution-level quality.

**What they are:** These metrics extract deep features from generated images
and compare them to reference images. HWD uses a VGG16 backbone fine-tuned
on IAM handwriting data to compute style distance between generated and
reference samples. LPIPS uses features from image classification networks
(AlexNet, VGG) calibrated against human perceptual similarity judgments.

**Relevance to reforge (P3):**

The current candidate scoring (`quality_score` in `quality/score.py`) uses
hand-crafted features: background cleanliness, ink density, edge sharpness,
height consistency, contrast. Seven of eight human reviews disagree with the
metric's candidate pick. The features are measuring "image quality" (clean
background, sharp edges), not "handwriting quality" (natural letterforms,
consistent stroke character, readable output).

Learned perceptual features could help because:
- VGG-based features capture mid-level structure (stroke patterns, letter
  shapes) that pixel-level statistics miss.
- HWD specifically captures handwriting style similarity, which is closer to
  what a human evaluates when picking the "best" candidate.
- LPIPS could serve as a general perceptual quality proxy.

However, practical concerns:
- HWD requires the VGG16 backbone (additional ~500MB model). Adding a second
  neural network to the scoring loop would roughly double candidate evaluation
  time.
- LPIPS operates on color images by default and would need adaptation for
  grayscale handwriting.
- With only 8 candidate reviews, any learned reweighting is underfit. The
  minimum for reliable logistic regression on 5 features is ~50 samples.
- The disagreement pattern (7/8) is so extreme that the current features may
  be capturing the wrong signal entirely, not just weighting it wrong.

**Recommendation:** Skip for now. The data is insufficient (8 reviews, 2
agreements) to train or validate a learned metric. The immediate path is the
analysis in D1: examine which of the existing sub-scores (background, ink,
edge, height, contrast, OCR) correlate with human picks, and whether a simple
reweighting improves agreement. If agreement stays below 50% after reweighting,
the features themselves are wrong and a VGG-based approach should be the next
step. Collect at least 15 more candidate reviews before investing in a learned
metric.

## E. Post-DiffusionPen Models

### DiffBrush (ICCV 2025)

Full text-line generation model. Generates entire lines of handwriting
conditioned on text and a style reference, eliminating the word-level
segmentation, generation, and stitching pipeline entirely.

**Pros:** Removes P2 (stitching) entirely. Likely handles punctuation better
since it operates at line level. Style conditioning may be stronger with
line-level context.

**Cons:** Requires a model swap (out of scope). Weights may not be publicly
available. Line-level generation introduces new problems (line-break
positioning, paragraph handling). Evaluation infrastructure would need to be
rebuilt.

**Recommendation:** Skip for this turn. Worth evaluating as a DiffusionPen
replacement if the project's non-goal on model swaps is reconsidered. File
under "future model evaluation."

### One-DM (ICDAR 2023)

One-shot diffusion model for handwriting style transfer. Uses a single style
reference image (vs. DiffusionPen's 5). Character-level attention mechanism.

**Pros:** Reduces the 5-image requirement. Character-level attention might
handle punctuation better.

**Cons:** Single-image style reference may produce less faithful style
transfer. Model swap required. Published results are on word-level generation
(same granularity as DiffusionPen).

**Recommendation:** Skip. Same word-level granularity means the same stitching
and punctuation problems persist. The 5-image requirement is not a pain point.

### WriteViT (2024)

Vision transformer-based handwriting generation. Attention-based architecture
with patch-level style encoding.

**Pros:** Modern architecture, potentially better at capturing fine details
(punctuation, thin strokes).

**Cons:** Model swap required. ViT architectures tend to need more VRAM.
Limited published comparisons with DiffusionPen on the same benchmarks.

**Recommendation:** Skip. Insufficient evidence that it solves reforge's
specific problems better than wrapper-layer fixes.

## Summary: Problem-to-Fix Mapping

| Problem | Recommended fix | Approach | Section |
|---------|----------------|----------|---------|
| P1: Trailing punctuation invisible | Synthetic punctuation via Bezier curves | Strip trailing punctuation before generation, render synthetic mark, reattach at correct baseline | B |
| P2: Chunk stitching baseline mismatch | Ink-profile cross-correlation alignment | Replace single-point ink-bottom with full vertical profile matching | C |
| P3: Candidate selection disagrees with human | Feature analysis + reweighting | Analyze which sub-scores correlate with human picks; reweight if data supports it. Collect more data before trying learned metrics (HWD/LPIPS). | D |
| P4: Stroke weight inconsistency | No further wrapper-layer fix | Accepted: 5 consecutive reviews show no visible A/B difference. Within-word variation is a generation property. | N/A |

## Citations

1. Graves, A. "Generating Sequences with Recurrent Neural Networks." arXiv:1308.0850 (2013).
2. Nikolaidou, K., et al. "Pictographic Character Reconstruction via Program Synthesis with Cubic Bezier Curves." arXiv:2511.00076 (2025).
3. Pippi, R., et al. "VATr++: Choose Your Words Wisely for Handwritten Text Generation." Pattern Recognition (2024).
4. Gui, C., et al. "HWD: A Novel Evaluation Score for Styled Handwritten Text Generation." BMVC (2023).
5. Manmatha, R. and Srimal, N. "Scale Space Technique for Word Segmentation in Handwritten Documents." SDIUT (1999).
6. Rath, T.M. and Manmatha, R. "Word Spotting for Historical Documents." IJDAR (2007).
7. Zhang, R., et al. "The Unreasonable Effectiveness of Deep Features as a Perceptual Metric." CVPR (2018).
8. Nikolaidou, K., et al. "DiffBrush: Handwritten Text Rendering with Diffusion Models." ICCV (2025).
9. Kang, L., et al. "One-DM: One-Shot Diffusion Mimicker for Handwritten Text Generation." ICDAR (2023).
