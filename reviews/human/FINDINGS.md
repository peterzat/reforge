# Human Review Findings

Durable quality principles extracted from human evaluation reviews. Each finding
includes the reviews that support it and any code changes it motivated.

## Status Summary

| Status | Count |
|--------|-------|
| Active | 6 |
| In Progress | 2 |
| Resolved | 1 |
| Acceptable | 0 |
| Graduated | 0 |

## How this file works

After each `make test-human` review, the coding agent analyzes unprocessed review
JSON files and drafts updates to this document. The human confirms changes before
they are committed.

### Finding statuses

- **Active** -- identified but not yet worked on.
- **In Progress** -- code changes are underway.
- **Resolved** -- human confirmed improvement via a targeted eval.
- **Acceptable** -- human reviewed it and decided current quality is good enough.
- **Graduated** -- promoted to CLAUDE.md per the graduation rules below.

### Graduation to CLAUDE.md

A finding is a candidate for promotion to CLAUDE.md when:
- It has been observed in **3 or more reviews**
- The underlying code has changed **at least twice** without invalidating the finding

Graduated findings represent stable human-validated quality principles that should
inform all future development. They are marked `[GRADUATED]` with a date and the
CLAUDE.md section where they were added.

## Findings

### Word spacing is too loose

- **Status:** Resolved
- **Reviews:** 2026-04-03_012736.json, 2026-04-03_021330.json
- **Principle:** WORD_SPACING=16 produces unnaturally wide gaps between words. Human
  preferred tighter spacing (8px) in the A/B test but noted even that was "still
  over spaced out." Both reviews flagged spacing_loose as a composition defect.
- **Evidence:** Review 1: flagged spacing_loose. Review 2: preferred B (8px) over
  A (16px), noted "still over spaced out, but b is a bit better."
- **Applies to:** reforge/config.py (WORD_SPACING), reforge/compose/layout.py
- **Contradicts config?** Yes. WORD_SPACING=16 was far too wide.
- **Code changes:** (1) Reduced WORD_SPACING from 16 to 6 in config.py. (2) Added
  horizontal tight-crop in compose/render.py to strip white padding from word
  images before layout. The padding (up to 30px per side) was the dominant source
  of visual gap, making WORD_SPACING irrelevant. After fix: "spacing looks much
  better" (review 2026-04-03_024039). Composition rating improved 2/5 -> 3/5.
- **Resolution:** Confirmed by human in review 2026-04-03_024039 (composition 2/5->3/5).

### Chunk stitching produces visible height mismatch, not seam artifacts

- **Status:** Active
- **Reviews:** 2026-04-03_021330.json, 2026-04-04_010317.json, 2026-04-09_220812.json
- **Principle:** The stitching problem is not visible seams at the overlap boundary.
  The problem is that chunks render at different heights, making them look like two
  separate words ("under" "standing") rather than one. Varying STITCH_OVERLAP_PX
  makes no visible difference because the overlap blending works fine; the height
  normalization before stitching does not.
- **Evidence:** Review 1: Human could not pick a preferred overlap ("They all look
  the same, and they're all terrible"). Described the issue as height mismatch.
  Review 2 (2026-04-04): composition improved to 3/5 after x-height normalization.
  Review 3 (2026-04-09): 4px preferred, but "standing is way higher than unders,
  it looks like superscript." Height mismatch persists despite x-height fix.
- **Applies to:** reforge/model/generator.py (stitch_chunks height normalization)
- **Code changes:** (1) Replaced bounding-box height normalization with ink-height
  alignment. (2) Added horizontal tight-crop. (3) X-height normalization. These
  improved but did not solve the problem. The height mismatch recurred without
  code changes, indicating chunk height normalization is fragile under generation
  variance. Reopened from Resolved status.

### Quality score disagrees with human candidate preference

- **Status:** Active
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_220812.json
- **Principle:** Human picked candidate B for "garden" but disagreed with the
  quality_score metric's pick. This suggests the scoring weights
  (background 0.20, ink_density 0.15, edge_sharpness 0.15, height 0.25,
  contrast 0.25) do not match human perception of "good handwriting."
- **Evidence:** Review 1: Human selected B, marked "Agree with quality score
  pick?" = false. Review 2 (2026-04-09): Human picked C, noted "C by far
  better than E, second closest is A." Again disagrees with metric pick.
  Two consecutive reviews where human and metric disagree.
- **Applies to:** reforge/quality/score.py (QUALITY_WEIGHTS)
- **Code changes:** None yet. Needs investigation into which dimension
  the metric overweights or underweights. Two data points now confirm
  systematic disagreement.

### Ink weight inconsistency across words

- **Status:** In Progress
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_220812.json, 2026-04-10_002757.json
- **Principle:** Adjacent words have visibly different stroke weight. The
  brightness-median harmonization has no visible effect (wrong signal).
  Two-pronged fix applied: (1) blended morphological stroke width
  harmonization in post-processing, (2) stroke width scoring in candidate
  selection using style images as reference.
- **Evidence:** Review 1: harmonization A/B "no difference." Review 2
  (2026-04-09): "identical." Review 3 (2026-04-10, post stroke-width
  scoring): ink_weight A/B still "identical," but composition jumped to
  4/5 (best ever), "easily our best so far." ink_weight_uneven no longer
  flagged as a composition defect. Stroke width scoring in candidate
  selection appears to be having a positive effect on overall composition
  quality even though the A/B ink weight comparison is too subtle to show.
- **Applies to:** reforge/quality/harmonize.py, reforge/quality/score.py,
  reforge/model/generator.py (candidate selection)
- **Code changes:** (1) Blended morphological harmonization: removed broken
  global gate, per-word 15% threshold with proportional alpha blend.
  (2) Stroke width scoring in quality_score: reference from style images,
  20% weight in combined score, active during best-of-N selection.
  Composition 4/5 suggests the candidate selection approach is more
  effective than post-hoc harmonization. The ink weight A/B eval may need
  redesign to test candidate selection quality, not post-processing.

### Hard words show gray box artifacts

- **Status:** In Progress
- **Reviews:** 2026-04-03_012736.json, 2026-04-03_021330.json, 2026-04-04_010317.json, 2026-04-09_220812.json
- **Principle:** Gray box artifacts appear on hard words at the fast preset.
  The 5-layer gray box defense works for typical words but fails on short
  and punctuated words. can't, than, and impossible were flagged unreadable
  across both reviews.
- **Evidence:** Review 1: 5/8 flagged unreadable, gray boxes noted.
  Review 2: 3/8 flagged unreadable (can't, than, impossible), "gray boxes
  appear on all of the words." Rating improved from 1/5 to 2/5.
  Review 3 (2026-04-04, post-fix): 2/5, impossible and book flagged
  unreadable, "lots of gray boxes throughout." Cluster filter fix preserved
  punctuated word fragments (can't, it's), but human noted "'t' in can't
  has a weird tail."
  Review 4 (2026-04-09): 3/5, "an" and "don't" flagged unreadable. Gray
  boxes still present. "don't" technically readable but apostrophe and "t"
  look zoomed-in/badly cropped. "book" readable but "k" looks like two
  letters. Improvement from 2/5 to 3/5 without code changes suggests
  generation variance, not a systematic fix.
- **Applies to:** reforge/model/generator.py (postprocess_word defense layers),
  reforge/config.py (gray box thresholds)
- **Code changes:** (1) Fixed isolated_cluster_filter to preserve word fragments
  with >= 15% of total ink, preventing apostrophe-gap stripping of "'t", "'s",
  "'d". (2) Raised OCR rejection threshold from 0.3 to 0.4 to catch borderline
  cases. Structural improvement confirmed (punctuated words no longer truncated),
  but human still sees gray artifacts from DiffusionPen's inherent generation
  quality on short/hard words.

### Baseline alignment regressed

- **Status:** Active
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_220812.json
- **Principle:** Baseline alignment showed a significant regression from 4/5
  to 2/5 with no pipeline code changes between reviews. The "g" in
  "jumping" looks mangled, and "gray" sits much higher than surrounding
  words. Short words ("by", "for") also drift vertically in composition.
  This suggests baseline detection is sensitive to per-word generation
  variance, particularly for descender words.
- **Evidence:** Review 1: 4/5, no complaints. Review 2 (2026-04-09): 2/5,
  "j in jumping looks perfect, but g in jumping looks a bit mangled. gray
  sits much higher than previous words." Composition review confirms:
  "by is higher than it should be, morning too high, being and for too low."
  CV baseline_alignment metric: 0.576 (low).
- **Applies to:** reforge/compose/layout.py, reforge/compose/render.py
- **Code changes:** None between reviews. The regression without code changes
  indicates baseline detection is fragile under generation variance. The
  descender detection algorithm may need robustness improvements, or
  composition needs a cross-word baseline normalization pass.

### Word sizing is inconsistent

- **Status:** Active
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_023255.json, 2026-04-09_024632.json, 2026-04-09_220812.json
- **Principle:** Short/medium/long word sizing ("I", "quick", "something")
  has fluctuated between 2/5 and 3/5 across reviews. The height
  normalization produces inconsistent relative sizes: "something" renders
  much smaller than "quick", and single-char words ("I") are too short.
  X-height normalization was attempted and reverted. Ink-height
  normalization is better but not sufficient.
- **Evidence:** Review 1: 3/5, no specific complaints. Review 2 (x-height):
  2/5, "Capital I is way too small, smaller than lowercase q." Review 3
  (ink-height reverted): 3/5, "'something' noticeably smaller, uppercase I
  could be larger, q descender appears cut off." Review 4 (2026-04-09):
  2/5, "I is a bit short, something looks much smaller than quick."
  Sizing regression to 2/5 without code changes suggests font_scale is
  sensitive to generation variance.
- **Applies to:** reforge/quality/font_scale.py, reforge/config.py
  (HEIGHT_OUTLIER_THRESHOLD, SHORT_WORD_HEIGHT_TARGET)
- **Code changes:** X-height normalization attempted and reverted. The
  fundamental issue: compute_x_height (50% peak density body zone) is
  unreliable across diverse word shapes. Ink-height normalization is the
  correct approach but may need tighter outlier clamping or a different
  height target for multi-char words like "something" that generate small.

### Composition quality improving but still variable

- **Status:** Active
- **Reviews:** 2026-04-03_012736.json, 2026-04-03_021330.json, 2026-04-03_024039.json, 2026-04-04_010317.json, 2026-04-09_220812.json, 2026-04-10_002757.json
- **Principle:** Composition quality has ranged from 2/5 to 4/5. The dominant
  remaining complaints are baseline drift and size inconsistency. Candidate
  selection improvements (OCR-aware scoring, stroke width scoring) appear
  to have the largest positive effect on composition quality.
- **Evidence:** Reviews 1-2: 2/5, illegible. Review 3 (spacing fix): 3/5.
  Reviews 4-6: held at 3/5. Review 7 (2026-04-09): regressed to 2/5 with
  no code changes. Review 8 (2026-04-10, post stroke-width scoring + OCR
  selection): 4/5, "easily our best so far." Defects: size_inconsistent,
  baseline_drift, letter_malformed (but no ink_weight_uneven for first time).
- **Applies to:** reforge/compose/layout.py (baseline), reforge/quality/font_scale.py
  (sizing), reforge/model/generator.py (candidate selection)
- **Code changes:** Spacing fix (2->3/5). OCR-aware candidate selection,
  stroke width scoring in candidate selection, blended morphological
  harmonization. The 4/5 rating came after candidate selection improvements,
  suggesting that improving per-word generation quality at selection time
  has more impact than post-processing fixes. Remaining defects (baseline,
  sizing) are the next targets.

## Graduated Findings

_None yet._
