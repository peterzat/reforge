# Human Review Findings

Durable quality principles extracted from human evaluation reviews. Each finding
includes the reviews that support it and any code changes it motivated.

## Status Summary

| Status | Count |
|--------|-------|
| Active | 4 |
| In Progress | 2 |
| Resolved | 2 |
| Acceptable | 0 |
| Plateaued | 1 |
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
- **Plateaued** -- iteration has stalled at the wrapper layer. See promotion rule
  below. Agents should skip Plateaued findings when picking the next work target.
- **Graduated** -- promoted to CLAUDE.md per the graduation rules below.

### Plateau promotion rule (spec 2026-04-10 D1)

A finding moves to **Plateaued** when:

- **3 or more code changes** have been applied to address it, AND
- **3 or more reviews** have rated it, AND
- the human rating has not moved by at least 1 point across those reviews.

A Plateaued finding requires a **design-level change** to leave that status:
retraining, a different architecture, intervention at a different layer, or
the user explicitly accepting the current quality as the target. Plateaued
findings do not consume iteration budget. The finding-driven iteration pattern
in CLAUDE.md instructs agents to skip them when selecting the next work item.

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
- **Code changes:** OCR-aware candidate scoring (40% OCR weight), stroke
  width scoring (20% of image quality component), and height-aware scoring
  (target closeness in height_consistency weight) added to candidate
  selection. Review 3 (2026-04-10): agreed for first time. Review 4
  (2026-04-10, post height scoring): disagreed again, picked D. The
  one agreement was an outlier, not a trend. The metric still does not
  reliably match human preference. Three of four reviews disagree.

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

### Baseline alignment fixed with median normalization

- **Status:** Resolved
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_220812.json, 2026-04-10_021645.json, 2026-04-10_023103.json
- **Principle:** Baseline alignment was fragile because the composition used
  max-baseline per line. One word with a bad baseline detection would anchor
  the whole line to the wrong position. Median-based normalization with
  outlier clamping (> 20% from median snapped to median) fixes this.
- **Evidence:** Review 1: 4/5. Review 2 (2026-04-09): regressed to 2/5.
  Review 3 (2026-04-10, pre-fix): 1/5. Review 4 (2026-04-10, post median
  fix): 4/5, "descenders in gray seem to struggle here, the rest looked
  right." CV baseline_alignment: 0.576 -> 0.897. Only residual issue is
  descender detection on specific words like "gray."
- **Applies to:** reforge/compose/render.py (line baseline computation)
- **Code changes:** Replaced max-baseline with median-baseline per line.
  Added outlier clamping (> 20% deviation from line median). Updated SSIM
  reference image. Compliance tests for outlier clamping and consistent
  word alignment.
- **Resolution:** Confirmed by human review 2026-04-10_023103: 4/5.

### Word sizing is inconsistent

- **Status:** Plateaued (promoted 2026-04-10 per spec D2)
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_023255.json, 2026-04-09_024632.json, 2026-04-09_220812.json, 2026-04-10_023103.json, 2026-04-10_023824.json
- **Principle:** Short/medium/long word sizing ("I", "quick", "something")
  holds at 2/5. The core complaint: capital "I" fills all available space,
  making lowercase words look tiny. Human wants "lowercase body roughly
  1/2 the size of capital I." This is fundamentally a case-awareness
  problem, not a height normalization problem.
- **Evidence:** Reviews 1-4: fluctuated 2/5 to 3/5. Review 5 (2026-04-10):
  2/5, "I takes up all the room available, lowercase should be roughly
  1/2 the size of capital I." Review 6 (2026-04-10, post cap-height fix):
  2/5, no improvement; cap height ratio (0.72) was attempted and reverted
  because it regressed composition 4/5 -> 3/5.
- **Applies to:** reforge/quality/font_scale.py, reforge/config.py
- **Code changes:** X-height normalization (attempted, reverted). Unified
  3+ char target (attempted, no visible effect). Case-aware cap height
  ratio at 0.72 (attempted, regressed composition, reverted). Height-
  aware candidate selection with target-closeness scoring (attempted,
  2/5 unchanged in review 7). Four approaches tried: three post-generation
  and one selection-time. None moved sizing past 2/5.
- **Plateau rationale:** 6 reviews and 4 code changes without the rating
  moving past 2/5. Promotion rule met (3+ reviews, 3+ code changes, no
  movement >= 1 point). This is a DiffusionPen-level limitation on single-
  character word generation: the model produces "I" at full canvas height
  regardless of candidate selection pressure, because all candidates for
  short words fill the canvas similarly. Wrapper-layer interventions
  (post-generation normalization, candidate scoring) have been exhausted.
- **Exit criteria:** To leave Plateaued status, one of (a) retraining or
  fine-tuning DiffusionPen on case-proportional data, (b) a different
  generative model with case awareness, (c) pre-generation case handling
  (e.g., generating "I" in a forced narrow canvas and adjusting composition
  baseline to compensate, which would require architectural changes to the
  pipeline layering), or (d) the user explicitly accepting 2/5 as the target.
  Agents should skip this finding when selecting the next iteration target
  unless one of these exit paths is being explored.

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
