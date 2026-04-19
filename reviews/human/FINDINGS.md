# Human Review Findings

Durable quality principles extracted from human evaluation reviews. Each finding
includes the reviews that support it and any code changes it motivated.

## Status Summary

| Status | Count |
|--------|-------|
| Active | 2 |
| In Progress | 4 |
| Resolved | 3 |
| Acceptable | 1 |
| Plateaued | 1 |
| Graduated | 0 |

## How this file works

After each `make test-human` review, the coding agent processes unprocessed review
JSON files in two steps:

1. **Triage each human note.** Every freeform note, defect flag, and verbal comment
   from the review is a signal. Classify each one:
   - **(a) Evidence for an existing finding** -- append to that finding's Evidence
     section with the review timestamp.
   - **(b) New standalone finding** -- create a new entry. A note qualifies as a new
     finding when it describes a distinct quality problem not covered by any existing
     finding. "I is missing ink" is not "I is too tall" (Plateaued sizing). When in
     doubt, create the finding; it can be merged later.
   - **(c) Not actionable** -- generation variance, one-off observation, or already
     addressed. No update needed, but note the classification in the commit message
     so the decision is reviewable.

2. **Draft updates** to this document. The human confirms changes before they are
   committed.

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

- **Status:** Resolved
- **Reviews:** 2026-04-03_021330.json, 2026-04-04_010317.json, 2026-04-09_220812.json, 2026-04-13_213330.json, 2026-04-14_143735.json, 2026-04-16_020920.json
- **Principle:** The stitching problem was not visible seams at the overlap boundary.
  The problem was that chunks rendered at different heights, making them look like
  two separate words ("under" "standing") rather than one. The root cause was
  single-point ink-bottom baseline alignment, which placed chunks at different
  vertical positions when their ink distributions differed.
- **Evidence:** Reviews 1-7 (2026-04-03 through 2026-04-14): human called the eval
  "broken" in 4 consecutive reviews due to severe vertical misalignment between
  "under" and "standing". Eval was suspended 2026-04-14.
  Review 8 (2026-04-16, post cross-correlation alignment): human confirmed chunks
  are "now correctly on the same baseline, much easier to use this eval!" Picked
  4px overlap. No complaints about vertical misalignment.
- **Applies to:** reforge/model/generator.py (stitch_chunks baseline alignment)
- **Code changes:** (1-4) Various height normalization approaches, all insufficient.
  (5) Ink-profile cross-correlation alignment (2026-04-14): replaced single-point
  ink-bottom alignment with vertical ink-density profile cross-correlation. This
  was the fix. Eval un-suspended 2026-04-16 after human confirmed resolution.
- **Resolution:** Cross-correlation stitch alignment confirmed by human review
  2026-04-16_020920. Eval un-suspended.

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
  Review 8 (2026-04-14, post x-height equalization): Human picked E,
  again disagrees with metric. Seven of eight reviews disagree.
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
- **Review 8 (2026-04-19_181354): duplicate-letter hallucination words
  promoted to curated hard_words; rating 2/5 → 3/5.** Spec 2026-04-19
  "Duplicate-letter hallucination class" added `mornings`, `something`,
  `really` to `reforge/data/hard_words.json::curated` alongside the
  already-present `impossible`. These words had been cited as
  `morninggs`, `somettthing`, `reallly` across Reviews 5-7 but weren't
  gated. On today's tree (commit `1a6e03e`, post-`_match_chunk_to_reference`
  and Caveat 1.15×), all three pass cleanly: seed-42 test-hard reads
  mornings=0.889, something=1.000, really=1.000 with zero critical
  flags (prior run had 2 critical). Medium-tier multi-seed test
  `tests/medium/test_duplicate_letter_hallucinations.py` confirmed each
  target word clears OCR >= 0.5 on all three seeds (42/137/2718); the
  weakest cell was `mornings` at seed 2718 at 0.750. No generation-side
  code change was needed — the defect was the test-gating gap. Human
  Review 8: composition held at 3/5, hard_words lifted to **3/5** (up
  from 2/5 in Review 6). No freeform defect flags on the three target
  words. This was the pragmatic confirmation of the hypothesis that the
  composition plateau persists partly because the gates weren't catching
  the exact words humans kept flagging.

### Baseline alignment fragile across generation runs

- **Status:** In Progress
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_220812.json, 2026-04-10_021645.json, 2026-04-10_023103.json, 2026-04-13_213330.json, 2026-04-14_041753.json, 2026-04-14_143735.json, 2026-04-17_141320.json
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
  Review 8 (2026-04-14, post x-height equalization): improved to 4/5.
  The equalize_body_zones() pass in font_scale.py scales down words
  whose x-height (body zone) exceeds 105% of median, addressing the
  "gray too big" problem. CV baseline_alignment: 1.0. Three code changes
  now contributing: median baseline, character-aware detection, and
  body-zone equalization. Rating trajectory: 2/5 -> 3/5 -> 3/5 -> 4/5.
  Review 9 (2026-04-17_141320): composition 2/5 with baseline_drift in
  defects. CV baseline_alignment 0.701 -- first drop below the recent
  0.78-0.85 stable range since the cross-correlation stitch fix.
  **New failure mode:** per-word descender clipping. Human on `by`:
  "`by` is blurry and the bottom of the `b` and the descender in get
  `y` is significantly clipped (only the two peaks of the `y` are
  visible)." This is distinct from cross-line drift -- it is the
  per-word bounding box underestimating the vertical extent so the
  bottom of rounded letters and full descenders get chopped off in
  either crop or composite paste. Candidate causes: over-tight
  postprocess crop on short words, aggressive body-zone equalization
  shrinking the canvas below descender reach, or a regression from
  the `_reinforce_thin_strokes()` change darkening ink that then
  shifts the per-word crop bounds.
- **Applies to:** reforge/compose/render.py (line baseline computation),
  reforge/compose/layout.py (per-word baseline detection),
  reforge/quality/font_scale.py (body-zone equalization)
- **Code changes:** (1) Replaced max-baseline with median-baseline per line.
  (2) Added outlier clamping. (3) Character-aware detect_baseline: words
  with descender letters (g,j,p,q,y) use a higher body-density threshold
  (25% vs 35%) to avoid treating descender ink as body text.
  (4) equalize_body_zones(): post-normalization pass scales down words
  whose x-height exceeds 105% of median, preventing non-ascender words
  from appearing disproportionately large.
- **Review 10 (2026-04-19_154926): short-word baseline fix landed; baseline
  eval 4/5.** Spec 2026-04-19 "Short-word baseline alignment at composition"
  identified a two-part root cause in `detect_baseline`: (a) the absolute
  `BASELINE_DENSITY_DROP = 0.15` threshold was calibrated against solid
  rectangle fixtures and was too high for real handwriting words whose
  body density tops out around 0.12-0.28, and (b) when the density-walkback
  failed to find a row meeting `BASELINE_BODY_DENSITY = 0.35`, the baseline
  silently stayed at the descender-bottom default. Fix: replace the
  absolute drop threshold with a per-word relative one
  (`min(body_peak * 0.3, BASELINE_DENSITY_DROP)`), and when the walkback
  fails on a known-descender word fall back to `r - 1` (the row just
  before the detected drop, which is always body). Human review 2026-04-19:
  baseline 4/5 (up from 3/5 stable plateau at Review 8), composition 3/5
  (no regression), no freeform notes citing `two is super low` or
  `by` descender clipping. The line-median drift that made non-descender
  neighbors like `two` render low is gone because descender words now
  report their body baseline, not their descender bottom, so the median
  no longer drifts. Regression test coverage added in
  `tests/quick/test_baseline.py::TestBaselineOnRealisticWordShapes` (cv2
  script-font renders of `two/an/he/jump/by/py/gp`) and
  `TestComposedLineBaselineAlignment` (end-to-end `compose_words` line of
  `two + by + morning + he` asserts within-line baseline spread <= 3 px).

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
- **Reviews:** 2026-04-03_012736.json, 2026-04-03_021330.json, 2026-04-03_024039.json, 2026-04-04_010317.json, 2026-04-09_220812.json, 2026-04-10_002757.json, 2026-04-13_213330.json, 2026-04-14_143735.json, 2026-04-16_021400.json, 2026-04-17_141320.json, 2026-04-18_154757.json
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
  be treated as solid evidence of a quality jump.
  Review 12 (2026-04-14, post x-height equalization): 4/5, defects:
  size_inconsistent, baseline_drift (from notes). '"by" is tiny,
  punctuation is completely invisible.' Third 4/5 rating. letter_malformed
  still absent from defects (2 reviews running). New finding: trailing
  punctuation (commas, periods, etc.) is invisible in composition output.
  Review 13 (2026-04-14, post Bezier punctuation + cross-correlation
  stitching): 2/5, defects: size_inconsistent, ink_weight_uneven,
  letter_malformed. ink_weight_uneven reappeared after being absent for
  2 reviews. letter_malformed returned. CV metrics: height_outlier_score
  0.818 (below 0.90 gate), ocr_min 0.0 (below 0.30 gate), baseline_alignment
  0.806. The dip may reflect generation variance (composition has hit 2/5
  multiple times without code changes) or interaction between the new
  trailing-punctuation path and composition text (5 words in the test text
  trigger synthetic mark attachment).
  Review 14 (2026-04-14, composition re-run): 3/5, defects: ink_weight_uneven.
  Human: "punctuation is nearly completely broken." letter_malformed and
  size_inconsistent dropped from defects. Only ink_weight_uneven remains.
  CV: height_outlier_score 0.923, baseline_alignment 0.854, ocr_min 0.0.
  Confirms prior 2/5 was generation variance; composition holds at 3/5.
  Review 15 (2026-04-14, post 3x mark scaling): 4/5, defects:
  size_inconsistent, letter_malformed. Punctuation marks clearly visible
  in composition ("exactly," "Thursday;" "noon." "three?" "breakfast."
  all readable). CV: height_outlier_score 0.923, baseline_alignment 0.757,
  ocr_min 0.167. Fourth 4/5 rating. The mark scaling fix resolved the
  "punctuation nearly completely broken" complaint from the prior review.
  Review 16 (2026-04-16, clean eval on committed code): 4/5, defects:
  size_inconsistent. Human: '"by" is slightly bigger but still too small.
  The initial "I" is missing a lot of ink, hard to read (second or third
  time I have seen this so I do not think it is just a generation fluke).'
  Fifth 4/5 rating. The "I" ink-loss issue is new as an explicit finding;
  may be related to single-char canvas-fill + aggressive postprocessing.
  Last 5 composition ratings: 2, 3, 4, 4, 4; median: **4/5 (target met)**.
  Review 17 (2026-04-16, post "I" ink reinforcement): 3/5, defects:
  spacing_loose, baseline_drift, letter_malformed. spacing_loose reappeared
  (was Resolved). CV: height_outlier_score 1.0, baseline_alignment 0.784,
  ocr_min 0.0. The 3/5 is within generation variance range (composition has
  bounced between 2-4/5 without code changes). Last 5: 2, 3, 4, 4, 3;
  median: **3/5** (target regressed from 4/5).
  Review 18 (2026-04-17_141320, post spec 2026-04-17 turn -- punctuation
  CV metric, candidate log, contraction width experiment, reinforcement
  kept): 2/5, defects: size_inconsistent, baseline_drift, letter_malformed.
  Three specific regressions called out by human:
  (a) `can't` reads as "cantt" (duplicate-letter artifact around the
      synthetic apostrophe -- see Apostrophe rendering finding);
  (b) `by` is clipped -- "b" bottom missing, "y" descenders clipped so
      only the two peaks are visible (see Baseline alignment fragile
      finding);
  (c) punctuation is "very bad" -- apostrophe tiny, commas and periods
      in the middle of words not at the bottom, semicolon tiny (see
      Trailing punctuation finding).
  CV: height_outlier_score 0.964 (passes 0.90 gate), baseline_alignment
  0.701 (below recent 0.78-0.85 stable range), ocr_min 0.0, `ocr_accuracy`
  0.903, `punctuation_visibility` 0.5 (new diagnostic from spec 2026-04-17
  B). The review JSON reports `gates_passed: true`, but that reflects a
  narrower gate set (gray_boxes, ink_contrast, background_cleanliness);
  **ocr_min = 0.0 fails the CLAUDE.md primary gate** of `ocr_min >= 0.30`.
  Last 5: 3, 4, 4, 3, 2; median: **3/5** (target still regressed from 4/5).
  Review 19 (2026-04-18_154757, post attempted full-word + overlay path
  on 3 seeds; now reverted): **2/5** with `defects=[]` in the flagged
  set but notes calling out `can'''t` (three apostrophes) as the primary
  complaint. Primary CV gates failed on every seed: seed 42 `ocr_min`
  0.00, seed 137 `ocr_min` 0.00 / `height_outlier_score` 0.887, seed
  2718 `ocr_min` 0.286 / `height_outlier_score` 0.846. Root cause: the
  overlay approach stacked marks on top of DP's stray body-zone
  apostrophe ink on 2 of 3 seeds (seed 2718 happened to come out clean).
  Documented in detail in the Apostrophe-rendering finding above and in
  `BACKLOG.md`. Code reverted to pre-Turn-2b state; the primary-gate
  regression was specifically caused by the overlay commits (fe12a7b,
  7d55f9c), not by a model or data change. Last 5: 4, 4, 3, 2, 2;
  median: **3/5** (target still regressed from 4/5).
- **Applies to:** reforge/compose/layout.py (baseline), reforge/quality/font_scale.py
  (sizing), reforge/model/generator.py (candidate selection, contraction splitting,
  trailing punctuation)
- **Code changes:** Spacing fix (2->3/5). OCR-aware candidate selection,
  stroke width scoring in candidate selection, blended morphological
  harmonization, contraction splitting, character-aware baseline detection,
  Bezier synthetic punctuation, cross-correlation stitch alignment,
  single-char ink reinforcement (2026-04-16).
  Remaining defects: baseline_drift, size_inconsistent
  (Plateaued for single-char), spacing_loose (intermittent), letter_malformed
  (intermittent).

### Apostrophe rendering is consistently poor

- **Status:** In Progress
- **Reviews:** 2026-04-04_010317.json, 2026-04-09_220812.json, 2026-04-13_213330.json, 2026-04-14_041753.json, 2026-04-14_143735.json, 2026-04-17_141320.json, 2026-04-18_154757.json
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
  oversized blobs) that previously degraded output quality. Tight-crop
  padding increased from 1px to 3px for 1-2 char right-side parts to
  preserve thin stroke edges. A dedicated `punctuation` eval type now
  provides focused signal (first result: 1/5, "punctuation is all bad,
  largely invisible"). Apostrophe migrated from pixel-loop to Bezier
  curve rendering (2026-04-14) for consistency with the new synthetic
  mark system. Contractions ("it's", "she'd") still flagged unreadable
  in second punctuation eval (2/5): the single-character right-side parts
  remain the bottleneck, not the apostrophe mark itself.
- **Spec 2026-04-17 C right-side canvas width experiment:** Added
  `CONTRACTION_RIGHT_SIDE_WIDTH` config hook (default `None`, matching
  current behavior) and ran the composition eval on seeds {42, 137, 2718}
  at the default width vs 128px for 1-2 char right parts. Contraction OCR
  mean improved only +5.67% (default 0.476 -> narrow 0.503), well below
  the +10% accept gate, and two primary CV metrics regressed beyond the
  5% tolerance: `baseline_alignment` default 0.765 -> narrow 0.691,
  `ocr_min` default 0.229 -> narrow 0.206. Decision: reject the narrower
  width; the default (`None`) stays. The narrower canvas does not
  meaningfully reduce DiffusionPen's hallucination of surrounding
  letters around tiny suffixes at this contraction set, and it disturbs
  the baseline alignment of the stitched output (likely because a
  smaller canvas shifts the right part's baseline during stitching).
  Per spec C3, stopping at one narrower candidate. Next wrapper-layer
  move would be P2 (fully synthetic suffix) from the previous spec's
  out-of-scope list; this finding remains In Progress pending that
  evaluation.
- **Review 6 (2026-04-17_141320):** composition 2/5, punctuation 2/5.
  `can't` and `it's` flagged unreadable. **New failure mode** observed:
  duplicate-letter artifact around the synthetic apostrophe -- `can't`
  reads as "cantt" and `it's` reads as "itss". This is distinct from the
  prior single-char canvas-fill complaint; the split/stitch path appears
  to be injecting or duplicating content adjacent to the apostrophe
  attachment point. Reinforces the spec 2026-04-17 C conclusion that
  wrapper-level right-side width tuning is exhausted; P2 (fully synthetic
  suffix) is now the obvious next wrapper-layer move.
- **Plateau consideration (2026-04-17):** 6+ reviews, 4+ code changes.
  Rating did move 1/5 -> 2/5 after Bezier marks landed, so the strict
  plateau rule (no >=1 point movement across 3+ reviews and 3+ code
  changes) is not yet satisfied. But the punctuation-eval rating has
  held at 2/5 across the last three code changes, and the wrapper layer
  is running out of obvious levers. If P2 does not move the rating,
  promote to Plateaued next review.
- **Review 7 (2026-04-18_154757): overlay approach failed, reverted.**
  Turn 2026-04-18 tried a different structure: remove `is_contraction`
  dispatch, let DP generate full contractions, overlay a clean apostrophe
  post-hoc (plan F). Full docs and failure mechanism in
  `BACKLOG.md` under "Cantt-specific proposals — status update
  2026-04-18". Short version: on seeds 42 and 137 the overlay added its
  mark *on top of* DP's body-zone apostrophe-shaped ink, producing
  "can'''t" visibly stacked. Seed 2718 happened to produce a clean
  single apostrophe (DP didn't stray). Safety valve (OCR < 0.5 ->
  fall back to split) never fired because OCR reads "canit" at 0.8
  even when three marks are present — OCR is insensitive to mark
  stacking that humans readily see. Ratings: composition 2/5,
  punctuation 2/5 (flagged `really?`; notes cite `reallly`, `it'''o`,
  `can''t'`, small `;` and `!`). The overlay was reverted to the
  pre-Turn-2b split path (commits fe12a7b, 7d55f9c). Findings stands
  unchanged; next-turn candidate is option E (full-word DP, NO overlay)
  rather than more overlay tuning — see BACKLOG for rationale.
- **Review 8 (2026-04-18_213857): option E (full-word DP) failed, reverted.**
  Spec 2026-04-18 deleted `is_contraction` dispatch + split_contraction +
  make_synthetic_apostrophe + stitch_contraction so DP rendered whole
  contractions via the normal generate_word path. Automated gates all
  passed: test-quick 281, test-regression clean on all 3 seeds,
  test-hard avg OCR 0.868, primary CV gates held. Human review
  regressed: composition 2/5 notes `"can''t", other punctuation wrong
  (too small). "they'd" looks right.`; punctuation 2/5 notes `double
  apostrophes, small and too low ! and ;`; hard_words notes
  `"impoocgsiblle", "can''t", gray boxes, "'t" in don't is cropped too
  close, apostrophe and t both offset far to the right.` The `can''t`
  double-apostrophe defect is the apostrophe-stacking failure mode the
  spec explicitly guarded against — but it originates in DP itself this
  time, not an overlay. DP sometimes renders a contraction with two
  apostrophe-shaped strokes side by side, and without a split path
  there is no wrapper layer to suppress the duplicate. `they'd` looked
  clean in this review, matching the seed-2718 observation that drove
  option E: DP *can* render contractions well, just not reliably
  enough for a gate. The code change was reverted to the split path.
  Per the spec's failure protocol, do not re-attempt option E with
  tweaks; the next candidate is option W (split at `'t`) or a
  BACKLOG F revisit with morphological-component apostrophe detection.
  **Update to the understanding of this finding:** split-path right-side
  weakness (Review 6 "cantt") and full-word DP stacking (Review 8
  "can''t") are *both* seed-variant failure modes. Neither path is
  robust across seeds 42/137/2718; both produce readable output on
  some seeds and human-visible defects on others. Wrapper-layer tuning
  has been exhausted at three structural levels (split, overlay, no
  intervention); moves that remain are sub-word-level (option W split
  at the `'t` boundary, keeping 2-char chunks above the IAM
  `MIN_WORD_CHARS=4` filter via padding) or metric-layer (morphological
  component detection to identify DP's spurious apostrophe ink).
- **Review 9 (2026-04-18_233350): option W (split at `'t`) landed.**
  Spec 2026-04-18 Option W changed `split_contraction("can't")` to
  return `("can", "'t")` (apostrophe retained on the right part), so
  both parts render through the normal word path and the synthetic
  apostrophe generator was deleted. All 8 criteria met, including
  criterion 8 (human review). Composition 3/5 (up from E's 2/5,
  +1 point). None of the forbidden defect patterns appeared in notes:
  no duplicated letter adjacent to apostrophe ("cantt"/"itss"), no
  stacked apostrophes ("can''t"/"can'''t"), no detached apostrophe
  ("can 't"). Human verbatim: "apostrophes look better." The
  wrapper-layer exhaustion concern from Review 8 was incorrect — W
  was a viable structural move that had not yet been tried.
  **New sub-issue observed in the same review** (tracked as a W
  follow-up, not a regression): the `'t` 2-char chunk renders with
  visibly lighter ink weight than the `can` left part, and the `t`
  glyph itself is tiny ("'t' in 'can't' has very light ink width vs
  'can'"). This is the IAM `MIN_WORD_CHARS=4` risk the spec flagged —
  DP produces a thin-ink 2-char output because 2-char inputs are below
  its training distribution. The existing cross-word stroke-weight
  harmonization pass should help but clearly isn't closing the gap on
  a 2-char chunk against a 3-char neighbor. Candidate fixes for a
  future spec: (a) pad the right chunk to >= 4 chars with a leading
  invisible filler and tight-crop post-generation; (b) extend
  `harmonize_words` stroke-shift to apply more aggressively when the
  chunk length is below a threshold; (c) accept as a known W-era
  limitation if the next spec targets a different quality dimension.
  Other composition-level defects flagged in Review 9 (`by` descender
  clipping, `morninggs`/`somettthing` duplicate letters, punctuation
  still too small and low) are tracked in their own FINDINGS entries
  or BACKLOG items (Caveat glyph dilate, baseline alignment); not
  apostrophe-rendering issues.
- **Review 10 (2026-04-19_173130): `_match_chunk_to_reference` landed;
  per-seed contraction OCR went 0.125-0.4 → 1.000.** Spec 2026-04-19
  "Contraction right-side sizing + Caveat thickness" added a post-generate
  / pre-stitch step inside `_generate_contraction` that measures the left
  chunk's ink height, stroke width, and ink-median and adjusts the right
  chunk to match (bounded scale up to 1.8×; grayscale erode with 3×3
  kernel then 5×5 fallback; double-pass ink-intensity shift). Seed-42
  test-hard ledger for the four common contractions went from
  `can't=0.4, they'd=1.0, don't=0.125 CRITICAL, it's=1.0` to all four
  at **1.000**. Regression test `tests/medium/test_contraction_sizing.py`
  asserts right/left stroke ratio ≥ 0.85, ink-median delta ≤ 20%, and
  ink-height delta ≤ 15% across seeds 42/137/2718 × the four words, 24
  cases total. Human Review 10 confirmed the improvement was visible
  ("punctuation is improved"; "every word + punctuation improved over
  prior runs") with no forbidden-phrase flags on contractions. Composition
  held at 3/5; the 4/5 rating target was aspirational and user accepted
  as partial (5/6 criteria). Option W's thin-ink sub-issue from Review 9
  is closed at the automated level.

### Trailing punctuation is invisible in generated output

- **Status:** In Progress
- **Reviews:** 2026-04-14_154117.json, 2026-04-14_170508.json, 2026-04-17_141320.json, 2026-04-18_154757.json
- **Principle:** DiffusionPen renders trailing punctuation marks (commas,
  periods, question marks, exclamation marks, semicolons) as invisible or
  imperceptible in the output. The model simply does not produce visible
  ink for these characters. This is distinct from the apostrophe problem
  (contraction splitting works around that). Trailing punctuation is
  now stripped before generation, with synthetic Bezier-rendered marks
  attached afterward.
- **Evidence:** First punctuation eval (2026-04-14): 1/5. Human: "punctuation
  is all bad (largely invisible)." Composition review (same session): 4/5
  but noted "punctuation is completely invisible."
  Second punctuation eval (2026-04-14, post Bezier marks): 2/5. Human:
  "lots of regression." Flagged unreadable: hello,, world., great!, wait;,
  it's, she'd. The synthetic marks themselves are now visible (period on
  "world.", question mark on "really?", semicolon on "wait;", comma on
  "hello,"), but the overall word quality around the marks is poor. "great!"
  has severe gray box artifacts; the contraction words ("it's", "she'd")
  still suffer from canvas-fill problems on single-character parts.
  The "regression" note likely refers to the base word generation quality
  rather than mark visibility, since marks were invisible before and are
  now visible. Rating improvement 1/5 -> 2/5 reflects marks being present
  but the surrounding words still being hard to read.
  Composition re-run (2026-04-14): 3/5. Human: "punctuation is nearly
  completely broken." The synthetic marks are present but too small relative
  to the surrounding text at composition scale. The marks are derived from
  the generated word's body_height (x-height), which is correct for
  isolated words but may be too small when the composition upscales.
  Third punctuation eval (2026-04-14, post 3x mark scaling): 2/5. Only
  "it's" and "she'd" flagged unreadable (contraction path, not trailing
  marks). The trailing marks (comma, period, question, semicolon) are
  now clearly visible. Composition: 4/5 with visible punctuation
  throughout ("exactly," "Thursday;" "noon." "three?" "breakfast." all
  have clear marks). The remaining punctuation problem is isolated to
  the contraction path (single-character right-side parts).
- **Applies to:** reforge/model/generator.py (strip_trailing_punctuation,
  _generate_punctuated_word, make_synthetic_mark)
- **Code changes:** (1) make_synthetic_mark() renders 5 mark types using
  cubic Bezier curves. (2) strip_trailing_punctuation() detects and strips
  trailing marks. (3) _generate_punctuated_word() generates base word
  then attaches synthetic mark. (4) generate_word() routes punctuated
  words through the new path. Marks are now visible; word quality around
  marks needs further work.
- **Review 4 (2026-04-17_141320):** punctuation 2/5 (flat). Flagged
  unreadable: `really?`, `great!`, `wait;`, plus the contraction-path
  words (`can't`, `it's`). CV `punctuation_visibility` = 0.5 (half the
  expected marks not visible). **Two new failure modes** after the
  2026-04-17 turn:
  (a) **Placement regression** -- human: "commas and periods are in the
      middle of words, not at the bottom." Prior 3x-scaling run placed
      marks at the baseline; something in the interim changed the
      attach point or the composition upscale is shifting the marks'
      vertical offset.
  (b) **Size regression** -- apostrophe described as "tiny" and semicolon
      "tiny." After the 3x scaling fix, marks read as "clearly visible";
      this review reads as a regression back toward invisibility. May
      interact with the `_reinforce_thin_strokes()` change (added in
      the same turn as this eval), which darkens faint ink on aggressive
      downscales and could affect mark sizing heuristics derived from
      the generated word's body_height.
- **Regression consideration (2026-04-17):** The trailing-mark problem
  looked Resolved after the 3x-scaling run (clear marks in the test
  output). The reappearance of "tiny" + mid-word placement means the
  fix has decayed or been disturbed. Candidate for a dedicated spec
  item: (1) verify `make_synthetic_mark` attach point math still
  targets the baseline, (2) audit mark-size derivation from
  `body_height` post-reinforcement, (3) consider recording a mark
  placement diagnostic (vertical offset from median baseline) alongside
  `punctuation_visibility`.
- **Review 5 (2026-04-18_154757): OFL font glyphs landed, still visually
  thin.** Turn 2026-04-18 replaced `make_synthetic_mark` with Caveat
  TTF rasterization for trailing `, . ; ! ?`. Smoke test with DP word +
  Caveat glyph at body_height=80 passed human inspection (stroke weight
  reasonable, baseline okay-ish). BUT production composition (body_height
  post-normalization ~18-30px) rendered Caveat marks visibly thin —
  human notes cite *"small `;` and `!`"*. Caveat's natural stroke at a
  given cap-height is thinner than the old Bezier's filled-blob marks.
  **Fix approach captured in `BACKLOG.md`** under "Caveat glyphs
  too thin in composition (Turn 2d follow-up)": add a morphological
  dilate in `reforge/model/font_glyph.py::render_trailing_mark` targeting
  the Bezier-equivalent `body_height * 0.12` stroke width. Verify with a
  production-scale smoke test before integrating.
- **Review 6 (2026-04-19_021632): Caveat dilate + baseline alignment
  landed; punctuation None/5 → 3/5.** Spec 2026-04-19 added an iterative
  morphological dilate in `render_trailing_mark` (3x3 grayscale erode
  loop, iterates until median stroke width measured via distance
  transform meets the Bezier baseline) and changed `_attach_mark_to_word`
  to align the mark against the word's detected baseline
  (`reforge.compose.layout.detect_baseline`) instead of its full ink
  bottom. For descender marks (`,`, `;`) the mark's own body baseline is
  used so the tail extends below without pulling the alignment point
  down. All 7 criteria met: test-quick 299, test-regression clean on 3
  seeds, test-hard avg OCR 0.694, human review punctuation 3/5 (up from
  Review 5's None/5 in the first Caveat landing), composition 3/5 (no
  regression from Option W). Human verbatim: *"all significantly
  improved.. ; ? and ! are all a bit small"*. The "a bit small" residual
  is a softened echo of Review 5's "small" complaint — further thickness
  gain (e.g. targeting 1.2× Bezier rather than 1.0×, or re-calibrating
  `_font_for_body_height`'s cap-height factor from 0.55 to something
  larger) is a plausible next-iteration knob but not urgent.
- **Unrelated observations from Review 6** (tracked here so they don't
  get lost; not trailing-punctuation issues): *"`two` is super low"* —
  a non-descender short word composited below its expected baseline.
  Likely a composition-time baseline-detection bug in `compose/render.py`
  (not `_attach_mark_to_word`, which this spec changed). Related to the
  BACKLOG "`by` descender clipping" entry; may be the same underlying
  baseline-detection problem on short words generally. *"apostrophe+t in
  first `can't` still too small and too thin ink weight"* — W follow-up,
  already captured in FINDINGS Review 9 under Apostrophe-rendering. No
  action needed under this finding.
- **Review 7 (2026-04-19_173130): Caveat dilation target lifted 1.0× → 1.15×
  Bezier; punctuation notes positive, rating held at 3/5.** Spec 2026-04-19
  "Contraction right-side sizing + Caveat thickness" introduced
  `TRAILING_MARK_TARGET_MULTIPLIER = 1.15` in `reforge/model/font_glyph.py`
  and retargeted `_dilate_to_stroke_width` against the measured Bezier
  stroke instead of the nominal `body_height * 0.12` formula, so marks
  like `!` and `?` (whose Bezier dot component already measures higher
  than nominal) receive the correct 1.15× target. Unit test
  `TestDilateToBezierBaseline` asserts the 1.15× ratio at body_heights
  {18, 24, 32} across `. , ; ! ?`. Human Review 7: punctuation still
  rated 3/5, but freeform note "every word + punctuation improved over
  prior runs" confirms the thickness lift was visible. Rating bar to
  4/5 aspirational; residual held at 3/5. No "a bit small" or
  equivalent softened complaint in this review's notes.

### Single-character "I" loses ink, appears half-missing

- **Status:** Resolved
- **Reviews:** 2026-04-14_212810.json, 2026-04-16_011718.json
- **Principle:** The uppercase letter "I" in composition output appears with
  significant ink missing, making it hard to read. The human reported this as
  recurring (2-3 observations) and explicitly stated it is not a generation
  fluke. This is distinct from the Plateaued sizing issue (that is about "I"
  being too tall relative to lowercase; this is about "I" having too little
  visible ink).
- **Evidence:** Review 15 (2026-04-14): composition 4/5, no explicit note but
  "I" visible in output. Review 16 (2026-04-16): composition 4/5, human:
  "The initial 'I' is missing a lot of ink, hard to read (second or third
  time I've seen this so I don't think it's just a generation fluke)."
- **Root cause (confirmed 2026-04-16):** Not the defense layers (body-zone,
  cluster filter, gray cleanup remove 0-4 ink pixels total). The cause is
  font normalization: "I" fills the 64px canvas, and normalize_font_size
  scales it to 26px (SHORT_WORD_HEIGHT_TARGET), a 0.41x factor. INTER_AREA
  interpolation averages the thin 2-3px vertical stroke into 1px of gray,
  washing out ink. Strong ink pixels drop from 500-1000 to 80-166.
- **Applies to:** reforge/quality/font_scale.py (normalize_font_size)
- **Code changes:** (1) Added _reinforce_thin_strokes() in font_scale.py:
  after aggressive downscaling (scale < 0.6) of single-char words, faint
  ink pixels (80-200) are darkened by 35% to compensate for INTER_AREA
  averaging.
- **Spec 2026-04-17 A variance check:** Ran the composition eval on five
  seeds (42, 137, 2718, 7, 2025) with reinforcement ON and OFF. Mean
  strong-ink pixels (< 80) in the "I" bbox: 368.8 ON vs 289 OFF (+27.6%,
  clears the ≥25% gate). No CV regression across the primary set
  (`height_outlier_score` identical, `baseline_alignment` +0.43%, `ocr_min`
  +16%); `punctuation_visibility` also +6.25%. Decision: keep
  `_reinforce_thin_strokes()` as written. Promoted to Resolved.

## Graduated Findings

_None yet._
