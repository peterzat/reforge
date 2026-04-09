# Human Review Findings

Durable quality principles extracted from human evaluation reviews. Each finding
includes the reviews that support it and any code changes it motivated.

## Status Summary

| Status | Count |
|--------|-------|
| Active | 4 |
| In Progress | 1 |
| Resolved | 2 |
| Acceptable | 1 |
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

- **Status:** Resolved
- **Reviews:** 2026-04-03_021330.json, 2026-04-04_010317.json
- **Principle:** The stitching problem is not visible seams at the overlap boundary.
  The problem is that chunks render at different heights, making them look like two
  separate words ("under" "standing") rather than one. Varying STITCH_OVERLAP_PX
  makes no visible difference because the overlap blending works fine; the height
  normalization before stitching does not.
- **Evidence:** Human could not pick a preferred overlap ("They all look the same,
  and they're all terrible"). Described the issue as height mismatch, not seam.
- **Applies to:** reforge/model/generator.py (stitch_chunks height normalization)
- **Code changes:** (1) Replaced bounding-box height normalization with ink-height
  alignment. Each chunk's ink region is measured and scaled to match median ink
  height, then chunks are baseline-aligned by ink bottom. (2) Added horizontal
  tight-crop of each chunk before stitching to eliminate whitespace gap.
  (3) Replaced total-ink-height normalization with x-height normalization:
  compute_x_height() measures the body zone (rows >= 50% peak density), excluding
  ascenders and descenders. Chunks are scaled so body heights match, preventing
  "under" (tall ascenders) and "standing" (short body) from looking mismatched.
- **Resolution:** Composition at 3/5 (2026-04-04 review), chunked words
  ("everything", "understand", "impossible") show improved OCR accuracy. X-height
  normalization addresses the specific "tanding is visibly smaller" complaint.

### Quality score disagrees with human candidate preference

- **Status:** Active
- **Reviews:** 2026-04-03_021330.json
- **Principle:** Human picked candidate B for "garden" but disagreed with the
  quality_score metric's pick. This suggests the scoring weights
  (background 0.20, ink_density 0.15, edge_sharpness 0.15, height 0.25,
  contrast 0.25) do not match human perception of "good handwriting."
- **Evidence:** Human selected B, marked "Agree with quality score pick?" = false.
- **Applies to:** reforge/quality/score.py (QUALITY_WEIGHTS)
- **Code changes:** None yet. Needs more reviews to identify which dimension
  the metric overweights or underweights.

### Ink weight harmonization has no visible effect

- **Status:** Acceptable
- **Reviews:** 2026-04-03_021330.json
- **Principle:** Comparing STROKE_WEIGHT_SHIFT_STRENGTH 0.92 vs 0.70 produced
  no visible difference to the human reviewer. Both variants had "equally
  inconsistent ink weight." The harmonization may be operating on the wrong
  signal (ink brightness median) rather than what humans perceive as
  weight inconsistency (stroke width, density).
- **Evidence:** Human could not pick a preferred variant, noted "no difference."
  Composition review (2026-04-04) still flags ink_weight_uneven, but this is
  a DiffusionPen generation property, not addressable through post-hoc
  harmonization.
- **Applies to:** reforge/quality/harmonize.py (harmonize_stroke_weight)
- **Code changes:** None. Current harmonization has no visible impact; further
  tuning would be effort without human-perceptible benefit.

### Hard words show gray box artifacts

- **Status:** In Progress
- **Reviews:** 2026-04-03_012736.json, 2026-04-03_021330.json, 2026-04-04_010317.json
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
  has a weird tail." Remaining gray boxes are from DiffusionPen generation
  quality, not postprocessing failures.
- **Applies to:** reforge/model/generator.py (postprocess_word defense layers),
  reforge/config.py (gray box thresholds)
- **Code changes:** (1) Fixed isolated_cluster_filter to preserve word fragments
  with >= 15% of total ink, preventing apostrophe-gap stripping of "'t", "'s",
  "'d". (2) Raised OCR rejection threshold from 0.3 to 0.4 to catch borderline
  cases. Structural improvement confirmed (punctuated words no longer truncated),
  but human still sees gray artifacts from DiffusionPen's inherent generation
  quality on short/hard words.

### Baseline alignment is acceptable

- **Status:** Active
- **Reviews:** 2026-04-03_021330.json
- **Principle:** Baseline alignment with descender words (jumping, quickly,
  beyond, gray, fences) rated 4/5. The ruled-line model and descender
  detection are working adequately for typical phrases.
- **Evidence:** Human rated 4/5 with no notes. No defects flagged.
- **Applies to:** reforge/compose/layout.py, reforge/compose/render.py
- **Code changes:** None needed. This is a positive signal.

### Word sizing is adequate but not great

- **Status:** Active
- **Reviews:** 2026-04-03_021330.json, 2026-04-09_023255.json, 2026-04-09_024632.json
- **Principle:** Short/medium/long word sizing ("I", "quick", "something")
  rated 3/5. The height normalization produces acceptable but not natural
  relative sizes. X-height normalization was attempted (A2/A3 in spec
  2026-04-04) but made sizing worse (2/5): words with ascenders/descenders
  scaled to pathological total heights while all-body words stayed small.
  Reverted to ink-height normalization, which restored 3/5.
- **Evidence:** Review 1: 3/5, no specific complaints. Review 2 (x-height):
  2/5, "Capital I is way too small, smaller than lowercase q." Review 3
  (ink-height reverted): 3/5, "'something' noticeably smaller, uppercase I
  could be larger, q descender appears cut off."
- **Applies to:** reforge/quality/font_scale.py, reforge/config.py
  (HEIGHT_OUTLIER_THRESHOLD, SHORT_WORD_HEIGHT_TARGET)
- **Code changes:** X-height normalization attempted and reverted. The
  fundamental issue: compute_x_height (50% peak density body zone) is
  unreliable across diverse word shapes. Words with tall ascenders get
  blown up, all-body words stay small. Ink-height normalization is the
  correct approach; remaining sizing issues are per-word generation
  variance from DiffusionPen.

### Composition has persistent illegibility at fast preset

- **Status:** Active
- **Reviews:** 2026-04-03_012736.json, 2026-04-03_021330.json, 2026-04-03_024039.json, 2026-04-04_010317.json
- **Principle:** Full composition output at the fast preset has illegible words.
  After spacing fix, rating improved from 2/5 to 3/5 and spacing_loose is no
  longer the dominant complaint. Remaining issues: specific words like
  "croissants" are unreadable, likely due to word length and chunking.
- **Evidence:** Reviews 1-2: 4 defect flags, "illegible." Review 3 (post-fix):
  3/5, "words like croissants still look horrible, but this is improved."
  Review 4 (quality preset, 2026-04-03_162051): 3/5, "punctuation is quite bad,
  some words still illegible (breakfast)." Review 5 (2026-04-04, post gray-box
  and x-height fixes): 3/5, defects: size_inconsistent, ink_weight_uneven,
  "many illegible words." Review 6 (2026-04-09, x-height reverted): 3/5,
  "letters malformed in several words." Rating holds at 3/5 across 4
  consecutive reviews.
- **Applies to:** reforge/model/generator.py (long word quality),
  reforge/config.py (PRESET_FAST candidates)
- **Code changes:** Spacing fix improved rating 2/5->3/5. Gray box cluster
  filter fix preserves punctuated word fragments. OCR threshold raised to 0.4.
  X-height chunk normalization. None of these moved composition past 3/5.
  The 3/5 ceiling appears to be DiffusionPen's per-word generation quality,
  not addressable through postprocessing or composition changes.

## Graduated Findings

_None yet._
