# Human Review Findings

Durable quality principles extracted from human evaluation reviews. Each finding
includes the reviews that support it and any code changes it motivated.

## Status Summary

| Status | Count |
|--------|-------|
| Active | 5 |
| In Progress | 2 |
| Resolved | 1 |
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
- **Reviews:** 2026-04-03_021330.json, 2026-04-04_010317.json, 2026-04-09_220812.json, 2026-04-13_213330.json
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
  Review 4 (2026-04-13): picked 4px, but called the test "flawed" because
  "tanding" is significantly higher than "under," making overlap comparison
  meaningless. The height mismatch dominates visual impression across all overlap
  variants.
- **Test design note:** The stitch eval is designed to compare overlap widths, but
  when chunk heights differ dramatically (as they do here), the overlap is
  irrelevant. The test may need redesign: either normalize chunk heights before
  the comparison, or acknowledge that stitch quality depends on solving the chunk
  height problem first, which is a generation-level issue.
- **Applies to:** reforge/model/generator.py (stitch_chunks height normalization)
- **Code changes:** (1) Replaced bounding-box height normalization with ink-height
  alignment. (2) Added horizontal tight-crop. (3) X-height normalization. These
  improved but did not solve the problem. The height mismatch recurred without
  code changes, indicating chunk height normalization is fragile under generation
  variance. Reopened from Resolved status.

### Quality score disagrees with human candidate preference

- **Status:** Active
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_220812.json, 2026-04-13_213330.json
- **Principle:** Human picked candidate B for "garden" but disagreed with the
  quality_score metric's pick. This suggests the scoring weights
  (background 0.20, ink_density 0.15, edge_sharpness 0.15, height 0.25,
  contrast 0.25) do not match human perception of "good handwriting."
- **Evidence:** Review 1: Human selected B, marked "Agree with quality score
  pick?" = false. Review 2 (2026-04-09): Human picked C, noted "C by far
  better than E, second closest is A." Again disagrees with metric pick.
  Two consecutive reviews where human and metric disagree.
  Review 5 (2026-04-13): Human picked A, again disagrees with metric.
  Four of five reviews show human-metric disagreement.
- **Applies to:** reforge/quality/score.py (QUALITY_WEIGHTS)
- **Code changes:** OCR-aware candidate scoring (40% OCR weight), stroke
  width scoring (20% of image quality component), and height-aware scoring
  (target closeness in height_consistency weight) added to candidate
  selection. Review 3 (2026-04-10): agreed for first time. Review 4
  (2026-04-10, post height scoring): disagreed again, picked D. The
  one agreement was an outlier, not a trend. The metric still does not
  reliably match human preference. Four of five reviews disagree.

### Ink weight inconsistency across words

- **Status:** In Progress
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_220812.json, 2026-04-10_002757.json, 2026-04-13_213330.json
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
  Review 4 (2026-04-13): preferred A, "looks identical." Four consecutive
  reviews where the A/B comparison shows no visible difference.
- **Applies to:** reforge/quality/harmonize.py, reforge/quality/score.py,
  reforge/model/generator.py (candidate selection)
- **Code changes:** (1) Blended morphological harmonization: removed broken
  global gate, per-word 15% threshold with proportional alpha blend.
  (2) Stroke width scoring in quality_score: reference from style images,
  20% weight in combined score, active during best-of-N selection.
  Composition 4/5 suggests the candidate selection approach is more
  effective than post-hoc harmonization. The ink weight A/B eval may need
  redesign to test candidate selection quality, not post-processing.
- **Plateau risk:** Four reviews with "identical" or "no difference" on the
  A/B test. The harmonization may already be at the limit of what
  post-processing can do, with candidate selection carrying the actual
  weight. If the next review still shows no visible difference, consider
  promoting to Acceptable (the real improvement is happening in candidate
  selection, not this A/B comparison).

### Hard words show gray box artifacts and poor apostrophes

- **Status:** In Progress
- **Reviews:** 2026-04-03_012736.json, 2026-04-03_021330.json, 2026-04-04_010317.json, 2026-04-09_220812.json, 2026-04-13_213330.json
- **Principle:** Gray box artifacts appear on hard words at the fast preset.
  The 5-layer gray box defense works for typical words but fails on short
  and punctuated words. can't, than, and impossible were flagged unreadable
  across both reviews. Apostrophe rendering is a persistent sub-problem:
  the apostrophe character produces oversized dark blobs rather than
  delicate strokes, degrading readability of all contractions.
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
  Review 5 (2026-04-13): 2/5, can't, noon, impossible flagged unreadable.
  "apostrophes are terrible looking." Regressed from 3/5 to 2/5. The
  apostrophe complaint now appears in both hard_words and composition
  evals ("apostrophe in can't remains super malformed"), indicating this
  is a cross-cutting issue, not limited to hard words.
- **Applies to:** reforge/model/generator.py (postprocess_word defense layers),
  reforge/config.py (gray box thresholds)
- **Code changes:** (1) Fixed isolated_cluster_filter to preserve word fragments
  with >= 15% of total ink, preventing apostrophe-gap stripping of "'t", "'s",
  "'d". (2) Raised OCR rejection threshold from 0.3 to 0.4 to catch borderline
  cases. Structural improvement confirmed (punctuated words no longer truncated),
  but human still sees gray artifacts from DiffusionPen's inherent generation
  quality on short/hard words. Apostrophe rendering may be a base-model
  limitation: the apostrophe character is rare in IAM training data relative to
  letters, so DiffusionPen likely has poor learned representations for it.

### Baseline alignment fragile across generation runs

- **Status:** Active (reopened from Resolved)
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_220812.json, 2026-04-10_021645.json, 2026-04-10_023103.json, 2026-04-13_213330.json
- **Principle:** Baseline alignment was fragile because the composition used
  max-baseline per line. Median-based normalization with outlier clamping
  improved it to 4/5, but the fix is not stable across generation runs.
  Words with descender-like strokes ("gray" with its g, "fences" with its
  f extending into descender territory) still cause per-word baseline
  detection errors that the median approach cannot fully absorb.
- **Evidence:** Review 1: 4/5. Review 2 (2026-04-09): regressed to 2/5.
  Review 3 (2026-04-10, pre-fix): 1/5. Review 4 (2026-04-10, post median
  fix): 4/5, "descenders in gray seem to struggle here, the rest looked
  right." CV baseline_alignment: 0.576 -> 0.897.
  Review 5 (2026-04-13): regressed to 2/5 with no code changes. "gray
  sits too high, fences sits too low (the f extends into descender
  territory)." CV baseline_alignment: 0.830, down from 0.897. The median
  fix helped but the underlying per-word baseline detection is unreliable
  for words where ascender/descender strokes confuse the density scan.
- **Applies to:** reforge/compose/render.py (line baseline computation),
  reforge/compose/layout.py (per-word baseline detection)
- **Code changes:** Replaced max-baseline with median-baseline per line.
  Added outlier clamping (> 20% deviation from line median). Updated SSIM
  reference image. Compliance tests for outlier clamping and consistent
  word alignment.
- **Previous resolution was premature:** The 4/5 rating was likely a
  favorable generation run. Without code changes, the rating reverted to
  2/5. The median approach handles outlier words but cannot fix incorrect
  per-word baseline detection, which is the root cause. Next step:
  improve baseline detection for words with prominent ascenders/descenders
  (g, f, y, j, p, q).

### Word sizing is inconsistent

- **Status:** Plateaued (promoted 2026-04-10 per spec D2)
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_023255.json, 2026-04-09_024632.json, 2026-04-09_220812.json, 2026-04-10_023103.json, 2026-04-10_023824.json, 2026-04-13_213330.json
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
  Review 7 (2026-04-13): dropped to 1/5 (first time below 2/5), no code
  changes since last review. "continued problem with this test: the I
  takes up the full vertical space, with no room for descenders, so the
  whole thing looks wrong (q is as big as I)." The drop from 2/5 to 1/5
  without code changes suggests growing frustration with the test design
  rather than quality regression.
- **Applies to:** reforge/quality/font_scale.py, reforge/config.py
- **Code changes:** X-height normalization (attempted, reverted). Unified
  3+ char target (attempted, no visible effect). Case-aware cap height
  ratio at 0.72 (attempted, regressed composition, reverted). Height-
  aware candidate selection with target-closeness scoring (attempted,
  2/5 unchanged in review 7). Four approaches tried: three post-generation
  and one selection-time. None moved sizing past 2/5.
- **Plateau rationale:** 7 reviews and 4 code changes without the rating
  moving past 2/5. Promotion rule met (3+ reviews, 3+ code changes, no
  movement >= 1 point). This is a DiffusionPen-level limitation on single-
  character word generation: the model produces "I" at full canvas height
  regardless of candidate selection pressure, because all candidates for
  short words fill the canvas similarly. Wrapper-layer interventions
  (post-generation normalization, candidate scoring) have been exhausted.
- **Test design problem (2026-04-13):** The sizing eval uses `["I", "quick",
  "something"]`, which conflates two distinct questions: (a) are multi-char
  words of different lengths sized consistently relative to each other? and
  (b) is a single uppercase character proportioned correctly vs lowercase
  body height? Question (b) is the Plateaued DiffusionPen limitation, and
  including "I" in the test makes it impossible to evaluate question (a)
  because the oversized "I" dominates the visual impression. Concretely:
  "I" renders at full canvas height (~64px), normalization targets it to
  26px, and "quick" is targeted to 28px, so they end up at nearly equal
  total height. But "quick" includes a descender (q), so its body appears
  the same height as the full "I", which looks wrong. The test should be
  split: (1) multi-char consistency eval with words like ["the", "quick",
  "something"] to test the actionable pipeline question, and (2) optionally
  a separate case-proportion eval that tracks the known Plateaued limitation
  without polluting the sizing signal.
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
- **Reviews:** 2026-04-03_012736.json, 2026-04-03_021330.json, 2026-04-03_024039.json, 2026-04-04_010317.json, 2026-04-09_220812.json, 2026-04-10_002757.json, 2026-04-13_213330.json
- **Principle:** Composition quality has ranged from 2/5 to 4/5. The dominant
  remaining complaints are baseline drift, size inconsistency, and malformed
  punctuation (especially apostrophes). Candidate selection improvements
  (OCR-aware scoring, stroke width scoring) appear to have the largest
  positive effect on composition quality.
- **Evidence:** Reviews 1-2: 2/5, illegible. Review 3 (spacing fix): 3/5.
  Reviews 4-6: held at 3/5. Review 7 (2026-04-09): regressed to 2/5 with
  no code changes. Review 8 (2026-04-10, post stroke-width scoring + OCR
  selection): 4/5, "easily our best so far." Defects: size_inconsistent,
  baseline_drift, letter_malformed (but no ink_weight_uneven for first time).
  Review 9 (2026-04-13): 3/5, defects: size_inconsistent, baseline_drift,
  letter_malformed. "apostrophe in can't remains super malformed." The 4/5
  peak has not been sustained; composition oscillates between 2/5 and 4/5
  depending on generation variance. Apostrophe quality is now a recurring
  composition defect (see also: hard words finding).
- **Applies to:** reforge/compose/layout.py (baseline), reforge/quality/font_scale.py
  (sizing), reforge/model/generator.py (candidate selection)
- **Code changes:** Spacing fix (2->3/5). OCR-aware candidate selection,
  stroke width scoring in candidate selection, blended morphological
  harmonization. The 4/5 rating came after candidate selection improvements,
  suggesting that improving per-word generation quality at selection time
  has more impact than post-processing fixes. Remaining defects: baseline
  (reopened), apostrophe rendering (cross-cutting), size inconsistency
  (Plateaued for single-char words).

### Apostrophe rendering is consistently poor

- **Status:** Active
- **Reviews:** 2026-04-04_010317.json, 2026-04-09_220812.json, 2026-04-13_213330.json
- **Principle:** The apostrophe character produces oversized, malformed dark
  blobs rather than a delicate stroke. This degrades all contractions
  (can't, don't, it's, they'd) and is now the most frequently cited
  letter-level defect. The problem appears across both the hard_words eval
  and the composition eval, making it a cross-cutting quality issue rather
  than something confined to difficult words.
- **Evidence:** Review 1 (2026-04-04): "'t' in can't has a weird tail."
  Review 2 (2026-04-09): "don't" apostrophe and "t" look "zoomed-in/badly
  cropped." Review 3 (2026-04-13): composition notes "apostrophe in can't
  remains super malformed," hard_words notes "apostrophes are terrible
  looking." can't flagged unreadable. The apostrophe is the common element
  in all three reviews.
- **Applies to:** reforge/model/generator.py (generation + postprocessing),
  reforge/config.py (charset includes apostrophe as `'`)
- **Root cause hypothesis:** The apostrophe is a single-pixel-width mark in
  real handwriting but occupies a full character position in the Canine-C
  tokenization. DiffusionPen likely has few IAM training examples with
  apostrophes (most IAM words are dictionary words without contractions),
  so the learned representation is poor. This may be a base-model limitation
  similar to the single-char sizing problem.
- **Potential interventions:** (1) OCR rejection loop already catches some
  bad apostrophe generations, but the model's best-of-N candidates for
  apostrophe words may all be poor. (2) Post-processing could attempt to
  detect and clean up oversized apostrophe glyphs. (3) Splitting
  contractions at the apostrophe (e.g., generating "can" and "t" separately
  with a synthetic apostrophe) would be a more invasive pipeline change.
  None attempted yet.

## Graduated Findings

_None yet._
