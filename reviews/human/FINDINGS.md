# Human Review Findings

Durable quality principles extracted from human evaluation reviews. Each finding
includes the reviews that support it and any code changes it motivated.

## Status Summary

| Status | Count |
|--------|-------|
| Active | 4 |
| In Progress | 2 |
| Resolved | 1 |
| Acceptable | 1 |
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
- **Reviews:** 2026-04-03_021330.json, 2026-04-04_010317.json, 2026-04-09_220812.json, 2026-04-13_213330.json, 2026-04-14_143735.json
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
  meaningless.
  Review 5 (2026-04-14): picked 4px. "this test is broken, the 'unders'
  is way below 'tanding' making it hard to see the seam." Pre-normalization
  of chunk heights (added for spec D1) made the baseline alignment worse
  by interfering with stitch_chunks' internal x-height normalization.
  Pre-normalization reverted; stitch_chunks handles normalization internally.
  The underlying issue is that stitch_chunks' baseline alignment is fragile
  when chunks have very different vertical ink distributions.
  Review 6 (2026-04-14, second run): picked 4px. Human reiterated the test
  is still broken: "the vertical misalignment makes it difficult to pick
  the right overlap." The eval has been called broken in 3 consecutive
  reviews. Until the baseline mismatch between chunks is fixed, the
  overlap comparison is not producing useful signal.
- **Test design note:** The stitch eval is designed to compare overlap widths, but
  when chunk baseline positions differ dramatically, the overlap is
  irrelevant. The problem is baseline alignment between chunks, not height.
  Human has flagged this test as broken 3 times running. It should either
  be fixed (equalize chunk baselines before comparing overlaps) or
  suspended until stitch_chunks baseline alignment is addressed.
- **Applies to:** reforge/model/generator.py (stitch_chunks baseline alignment)
- **Code changes:** (1) Replaced bounding-box height normalization with ink-height
  alignment. (2) Added horizontal tight-crop. (3) X-height normalization.
  (4) Pre-normalization of chunk heights before stitch (attempted, reverted:
  interfered with internal baseline alignment, making "unders" sit below
  "tanding"). These improved but did not solve the problem. The baseline
  alignment between chunks remains fragile under generation variance.

### Quality score disagrees with human candidate preference

- **Status:** Active
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_220812.json, 2026-04-13_213330.json, 2026-04-14_143735.json
- **Principle:** Human picked candidate B for "garden" but disagreed with the
  quality_score metric's pick. This suggests the scoring weights
  (background 0.20, ink_density 0.15, edge_sharpness 0.15, height 0.25,
  contrast 0.25) do not match human perception of "good handwriting."
- **Evidence:** Review 1: Human selected B, marked "Agree with quality score
  pick?" = false. Review 2 (2026-04-09): Human picked C, noted "C by far
  better than E, second closest is A." Again disagrees with metric pick.
  Review 5 (2026-04-13): Human picked A, again disagrees with metric.
  Review 6 (2026-04-14): Human picked B, again disagrees with metric.
  Review 7 (2026-04-14, second run): Human picked C, again disagrees with
  metric. Six of seven reviews show human-metric disagreement.
- **Applies to:** reforge/quality/score.py (QUALITY_WEIGHTS)
- **Code changes:** OCR-aware candidate scoring (40% OCR weight), stroke
  width scoring (20% of image quality component), and height-aware scoring
  (target closeness in height_consistency weight) added to candidate
  selection. Review 3 (2026-04-10): agreed for first time. Review 4
  (2026-04-10, post height scoring): disagreed again, picked D. The
  one agreement was an outlier, not a trend. The metric still does not
  reliably match human preference. Four of five reviews disagree.

### Ink weight inconsistency across words

- **Status:** Acceptable (promoted 2026-04-14)
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_220812.json, 2026-04-10_002757.json, 2026-04-13_213330.json, 2026-04-14_041753.json, 2026-04-14_143735.json
- **Principle:** Adjacent words have visibly different stroke weight. The
  brightness-median harmonization has no visible effect (wrong signal).
  Two-pronged fix applied: (1) blended morphological stroke width
  harmonization in post-processing, (2) stroke width scoring in candidate
  selection using style images as reference.
- **Evidence:** Reviews 1-5: A/B comparison rated "identical" or "no
  difference" five consecutive times. Review 5 (2026-04-14): "identical,
  but definitely not perfect." Review 6 (2026-04-14, second run): preferred
  A, "very close, possibly identical." Six consecutive reviews with no
  visible A/B difference. The A/B harmonization comparison cannot show
  further improvement. Composition quality gains (4/5 peak) came from
  candidate selection (stroke width scoring), not post-processing.
- **Applies to:** reforge/quality/harmonize.py, reforge/quality/score.py,
  reforge/model/generator.py (candidate selection)
- **Code changes:** (1) Blended morphological harmonization: removed broken
  global gate, per-word 15% threshold with proportional alpha blend.
  (2) Stroke width scoring in quality_score: reference from style images,
  20% weight in combined score, active during best-of-N selection.
- **Acceptance rationale:** Five consecutive reviews where the A/B
  comparison shows no visible difference. The real ink weight improvement
  comes from candidate selection, not post-processing harmonization. The
  A/B eval measures post-processing only and cannot improve further.
  Within-line variability remains, but that is a generation-level property
  that wrapper-layer harmonization cannot fix. The user confirmed the
  comparison lines look identical but noted the imperfection is within
  each line, not between the A/B variants.

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
  "apostrophes are terrible looking."
  Review 6 (2026-04-14, post contraction-splitting): 2/5, can't,
  impossible, book flagged unreadable. can't still unreadable despite
  contraction splitting; impossible and book are persistent hard words.
  Rating unchanged at 2/5.
  Review 7 (2026-04-14, second run): 3/5, can't and impossible flagged
  unreadable. "book" no longer flagged (improvement or generation variance).
  Specific defects from human: "don't" is looking better but the cropping
  on the "t" is too close; "can't" has a malformed "t"; "impossible"
  reads as "impoosssible" (repeated letters "oo" and "sss"). The
  letter-duplication issue in "impossible" is a generation-level problem
  (DiffusionPen repeating glyphs for long words), not a postprocessing
  failure. First improvement past 2/5 in several reviews.
- **Applies to:** reforge/model/generator.py (postprocess_word defense layers,
  contraction splitting), reforge/config.py (gray box thresholds)
- **Code changes:** (1) Fixed isolated_cluster_filter to preserve word fragments
  with >= 15% of total ink. (2) Raised OCR rejection threshold from 0.3 to 0.4.
  (3) Contraction splitting bypasses DiffusionPen for apostrophe rendering,
  generating left/right parts separately with a synthetic mark. OCR accuracy
  for contractions improved (multi-seed avg 0.593-0.750) but visual quality
  still flagged as unreadable by human. The right-side single character
  ("t", "s", "d") suffers from the same canvas-fill problem as other short
  words.

### Baseline alignment fragile across generation runs

- **Status:** In Progress
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_220812.json, 2026-04-10_021645.json, 2026-04-10_023103.json, 2026-04-13_213330.json, 2026-04-14_041753.json, 2026-04-14_143735.json
- **Principle:** Baseline alignment was fragile because the composition used
  max-baseline per line. Median-based normalization with outlier clamping
  improved it to 4/5, but the fix is not stable across generation runs.
  Words with descender-like strokes ("gray" with its g, "fences" with its
  f extending into descender territory) still cause per-word baseline
  detection errors that the median approach cannot fully absorb.
- **Evidence:** Review 1: 4/5. Review 2 (2026-04-09): regressed to 2/5.
  Review 3 (2026-04-10, pre-fix): 1/5. Review 4 (2026-04-10, post median
  fix): 4/5. Review 5 (2026-04-13): regressed to 2/5 with no code changes.
  Review 6 (2026-04-14, post character-aware detect_baseline): improved to
  3/5. CV baseline_alignment: 0.816. The character-aware detection (higher
  body-density threshold for descender letters) is helping but not solving
  completely. The user also noted that "gray" appears much bigger than
  other words in the baseline eval, suggesting font normalization (not
  baseline detection) is a contributing factor: words with dots on i/j
  have their total ink height inflated by the dots, causing them to be
  scaled down more, making "gray" (no ascenders) look disproportionately
  large.
  Review 7 (2026-04-14, second run): holding at 3/5. CV baseline_alignment:
  0.826. Character-aware baseline detection is stabilizing: two consecutive
  reviews at 3/5 after the fix, versus the 2/5-4/5 swings before it.
  Human reiterated the "gray" size issue: "gray" still looks much bigger
  than other words. The hypothesis that dots on i/j inflate ink height
  (causing words with ascenders to be scaled down, making "gray" look
  disproportionately large) remains the most likely root cause. The
  combination of letters in a word should not affect its relative scaling.
  Composition still lists baseline_drift as a defect.
- **Applies to:** reforge/compose/render.py (line baseline computation),
  reforge/compose/layout.py (per-word baseline detection),
  reforge/quality/font_scale.py (ink height includes dots/ascenders)
- **Code changes:** (1) Replaced max-baseline with median-baseline per line.
  (2) Added outlier clamping. (3) Character-aware detect_baseline: words
  with descender letters (g,j,p,q,y) use a higher body-density threshold
  (25% vs 35%) to avoid treating descender ink as body text.
- **Next step:** The font normalization issue (total ink height includes
  dots/ascenders, distorting relative body sizes) may need x-height-based
  normalization instead of total-ink-height-based. This would be a
  significant change to font_scale.py.

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
- **Test design problem (2026-04-13, confirmed 2026-04-14):** The sizing eval
  display is broken. Human reports: in the white box, "Word sizing
  consistency" followed by "Multi-char sizing: the, quick, something" with
  handwritten words, then "Case proportion (known limitation): I The"
  (verbatim, nonsensical label), with only the handwritten letter "I" and
  nothing else below it. "The whole test doesn't make sense."
  The original design conflated two distinct questions: (a) multi-char
  consistency and (b) single uppercase proportion. The display now fails
  to even render the second test word ("The") for the case proportion
  section. The eval should be either fixed (render all words, clarify
  labels) or stripped to just the multi-char consistency comparison
  ["the", "quick", "something"], since the single-char issue is Plateaued.
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
- **Reviews:** 2026-04-03_012736.json, 2026-04-03_021330.json, 2026-04-03_024039.json, 2026-04-04_010317.json, 2026-04-09_220812.json, 2026-04-10_002757.json, 2026-04-13_213330.json, 2026-04-14_143735.json
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
  letter_malformed. "apostrophe in can't remains super malformed."
  Review 10 (2026-04-14, post contraction-splitting + baseline fix): 3/5,
  defects: size_inconsistent, baseline_drift, letter_malformed. '"by" is
  tiny.' Same defect set as prior review.
  Review 11 (2026-04-14, second run): 4/5 (human noted this was generous),
  defects: size_inconsistent, baseline_drift. "by" is still super small.
  Notable: letter_malformed dropped from defects for the first time in 4
  reviews. This is the second 4/5 rating overall. The generous self-
  assessment means the true quality is closer to 3.5/5; the 4 should not
  be treated as solid evidence of a quality jump. Last 5 composition
  ratings: 3, 3, 3, 3, 4; median: 3/5 (target: 4/5).
- **Applies to:** reforge/compose/layout.py (baseline), reforge/quality/font_scale.py
  (sizing), reforge/model/generator.py (candidate selection, contraction splitting)
- **Code changes:** Spacing fix (2->3/5). OCR-aware candidate selection,
  stroke width scoring in candidate selection, blended morphological
  harmonization, contraction splitting, character-aware baseline detection.
  Two 4/5 ratings now achieved; the second came after contraction splitting
  and baseline fixes. Remaining defects: baseline_drift (stabilizing at 3/5
  in targeted eval), size_inconsistent (Plateaued for single-char).

### Apostrophe rendering is consistently poor

- **Status:** In Progress
- **Reviews:** 2026-04-04_010317.json, 2026-04-09_220812.json, 2026-04-13_213330.json, 2026-04-14_041753.json, 2026-04-14_143735.json
- **Principle:** The apostrophe character produces oversized, malformed dark
  blobs rather than a delicate stroke. This degrades all contractions
  (can't, don't, it's, they'd) and is now the most frequently cited
  letter-level defect.
- **Evidence:** Reviews 1-3: apostrophe complaints in both hard_words and
  composition evals. Review 4 (2026-04-14, post contraction-splitting):
  can't still flagged unreadable in hard_words (2/5). However, OCR
  accuracy for apostrophe words improved significantly: multi-seed
  averages 0.750/0.708/0.593 (seeds 42/137/2718), all above the 0.5
  target, compared to 0.0-0.5 baseline before splitting. The contraction
  splitting generates left/right parts separately with a synthetic
  apostrophe mark. OCR improvement is clear, but visual quality still
  needs human validation in context (the hard_words eval shows individual
  words, not the stitched contraction in composition).
  Review 5 (2026-04-14, second run): can't still flagged in hard_words
  (3/5 overall, improved from 2/5). Specific defects from human: "don't"
  is looking better but the cropping on the "t" is too close; "can't"
  has a malformed "t." The "t" cropping problem is likely tight-crop in
  postprocessing clipping the thin stroke too aggressively. Mixed signal
  in composition: rated 4/5 (generous) with letter_malformed dropped from
  defects for first time in 4 reviews. Contraction splitting looks
  acceptable in full composition context but isolated word view still
  exposes cropping and canvas-fill problems on single-character parts.
- **Applies to:** reforge/model/generator.py (contraction splitting,
  synthetic apostrophe), reforge/config.py (charset)
- **Code changes:** (1) `is_contraction()` / `split_contraction()` detect
  and split at apostrophe. (2) `make_synthetic_apostrophe()` creates a
  programmatic thin stroke from the ink properties of generated parts.
  (3) `stitch_contraction()` assembles left + apostrophe + right with
  baseline alignment. (4) Punctuation test added (6 words, avg OCR 0.772).
  17 unit tests cover detection, splitting, and stitching.
- **Progress note:** The synthetic punctuation approach is a net positive:
  it avoids DiffusionPen's worst punctuation artifacts (double apostrophes,
  oversized blobs) that previously degraded output quality. The approach
  needs refinement (tight cropping on right-side "t", canvas-fill on
  single-char parts) but the direction is correct.
- **Next step:** Perfect the contraction splitting output, and add targeted
  human eval test loops for punctuation rendering specifically. The current
  hard_words eval covers contractions incidentally but does not isolate
  punctuation quality. A dedicated punctuation eval type would provide
  focused signal for iteration.

## Graduated Findings

_None yet._
