# Human Review Findings

Durable quality principles extracted from human evaluation reviews. Each finding
includes the reviews that support it and any code changes it motivated.

## Status Summary

| Status | Count |
|--------|-------|
| Active | 6 |
| In Progress | 1 |
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

- **Status:** In Progress
- **Reviews:** 2026-04-03_021330.json
- **Principle:** The stitching problem is not visible seams at the overlap boundary.
  The problem is that chunks render at different heights, making them look like two
  separate words ("under" "standing") rather than one. Varying STITCH_OVERLAP_PX
  makes no visible difference because the overlap blending works fine; the height
  normalization before stitching does not.
- **Evidence:** Human could not pick a preferred overlap ("They all look the same,
  and they're all terrible"). Described the issue as height mismatch, not seam.
- **Applies to:** reforge/model/generator.py (stitch_chunks height normalization)
- **Contradicts config?** The current stitch_chunks normalizes to median height,
  but the chunks may have very different ink distributions that make the median
  misleading. Needs investigation.
- **Code changes:** (1) Replaced bounding-box height normalization with ink-height
  alignment. Each chunk's ink region is measured and scaled to match median ink
  height, then chunks are baseline-aligned by ink bottom. (2) Added horizontal
  tight-crop of each chunk before stitching to eliminate whitespace gap.
- **Review 2026-04-03_162051:** All overlap variants identical, "all terrible
  (huge gap)." The gap was caused by whitespace padding, not overlap blending.
- **Review 2026-04-03_164243:** After tight-crop fix, human picked 8px overlap
  and rated it "looks very good." Remaining issue: second chunk ("tanding") is
  visibly smaller than first chunk, which is an x-height mismatch (letter body
  size) not captured by total ink-height normalization.

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

- **Status:** Active
- **Reviews:** 2026-04-03_021330.json
- **Principle:** Comparing STROKE_WEIGHT_SHIFT_STRENGTH 0.92 vs 0.70 produced
  no visible difference to the human reviewer. Both variants had "equally
  inconsistent ink weight." The harmonization may be operating on the wrong
  signal (ink brightness median) rather than what humans perceive as
  weight inconsistency (stroke width, density).
- **Evidence:** Human could not pick a preferred variant, noted "no difference."
- **Applies to:** reforge/quality/harmonize.py (harmonize_stroke_weight)
- **Contradicts config?** STROKE_WEIGHT_SHIFT_STRENGTH may be irrelevant.
  The stroke width harmonization (harmonize_stroke_width) or a different
  approach may be needed.
- **Code changes:** None yet.

### Hard words show gray box artifacts

- **Status:** Active
- **Reviews:** 2026-04-03_012736.json, 2026-04-03_021330.json
- **Principle:** Gray box artifacts appear on hard words at the fast preset.
  The 5-layer gray box defense works for typical words but fails on short
  and punctuated words. can't, than, and impossible were flagged unreadable
  across both reviews.
- **Evidence:** Review 1: 5/8 flagged unreadable, gray boxes noted.
  Review 2: 3/8 flagged unreadable (can't, than, impossible), "gray boxes
  appear on all of the words." Rating improved from 1/5 to 2/5.
- **Applies to:** reforge/model/generator.py (postprocess_word defense layers),
  reforge/config.py (gray box thresholds)
- **Code changes:** None yet.

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
- **Reviews:** 2026-04-03_021330.json
- **Principle:** Short/medium/long word sizing ("I", "quick", "something")
  rated 3/5. The height normalization produces acceptable but not natural
  relative sizes.
- **Evidence:** Human rated 3/5 with no specific complaints.
- **Applies to:** reforge/quality/font_scale.py, reforge/config.py
  (HEIGHT_OUTLIER_THRESHOLD, SHORT_WORD_HEIGHT_TARGET)
- **Code changes:** None yet. Lower priority than spacing and stitching.

### Composition has persistent illegibility at fast preset

- **Status:** Active
- **Reviews:** 2026-04-03_012736.json, 2026-04-03_021330.json, 2026-04-03_024039.json
- **Principle:** Full composition output at the fast preset has illegible words.
  After spacing fix, rating improved from 2/5 to 3/5 and spacing_loose is no
  longer the dominant complaint. Remaining issues: specific words like
  "croissants" are unreadable, likely due to word length and chunking.
- **Evidence:** Reviews 1-2: 4 defect flags, "illegible." Review 3 (post-fix):
  3/5, "words like croissants still look horrible, but this is improved."
  Review 4 (quality preset, 2026-04-03_162051): 3/5, "punctuation is quite bad,
  some words still illegible (breakfast)." Defects: size_inconsistent,
  ink_weight_uneven, letter_malformed. Suggests adding "some words unreadable"
  defect flag.
- **Applies to:** reforge/model/generator.py (long word quality),
  reforge/config.py (PRESET_FAST candidates)
- **Code changes:** Spacing fix improved rating. Remaining illegibility is
  per-word generation quality, not layout. Quality preset (50 steps, 3
  candidates) did not improve the 3/5 rating over fast preset.

## Graduated Findings

_None yet._
