# Human Review Findings

<!-- FINDINGS_LAST_PROCESSED: 2026-04-19_215858 -->

Durable quality principles extracted from human evaluation reviews. Each finding
includes the reviews that support it and any code changes it motivated.

## Status Summary

| Status | Count |
|--------|-------|
| Active | 2 |
| In Progress | 3 |
| Resolved | 4 |
| Acceptable | 1 |
| Plateaued | 1 |
| Graduated | 1 |

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

2. **Draft updates** to this document and present the diff in the terminal. The human
   confirms changes before they are committed. No qpeek -- qpeek is for images only.

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
- The principle is **stable and generalizable** (not just "we fixed bug X")

Graduated findings become permanent operational principles in CLAUDE.md. The
FINDINGS.md entry is compressed to a pointer + resolution note so future reviewers
can trace the history. The `## Graduated Findings` section at the bottom lists
pointers only.

## Methodology notes

### Rating-window hypothesis ruled out (2026-04-19)

The composition 3/5 plateau is not an artifact of the rolling 5-review
window. Medians at {3, 5, 7, 10, all} all equal 3 on the current corpus of
33 rated reviews (`scripts/compute_rating_window.py`, spec 2026-04-19
"Composition rating window: data-driven decision"). Widening the CLAUDE.md
target window would not reveal a hidden lift; the plateau is genuine across
every window we can measure. CLAUDE.md target stays at last-5; further lift
must come from work that raises the composite impression, not from window
tuning. Full analysis: `docs/rating_window_analysis.md`.

### X-height-spread is the wrong lever for size_inconsistent (2026-04-19)

Spec 2026-04-19 (body-zone sizing) attempted to close the persistent
`size_inconsistent` composition defect by reducing `x_height_spread` on
the demo sentence. Two attempts (shrunk image dimensions; baseline-
preserving pad) both reduced the metric 21% on seed 42 but produced the
same "superscript" visual regression: scaled-down short words read as
raised even when baseline-aligned, because the eye compares top extents
across the line. Metric is orthogonal to human perception of size_inconsistent.
Starting artifacts for the next attempt (different lever -- compose-layer
per-word baseline offsets, or per-word size_inconsistent human-eval type):
`scripts/measure_word_sizing.py`, `docs/sizing_diagnostic.md`.

## Findings

### Word spacing is too loose

- **Status:** Resolved (2026-04-03)
- **Reviews:** 2 (`2026-04-03_012736`, `2026-04-03_021330`)
- **Principle:** `WORD_SPACING=16` produced unnaturally wide gaps; tight-cropping
  word images horizontally (stripping up to 30px of white padding per side) was the
  dominant fix, not the spacing constant itself.
- **Applies to:** `reforge/config.py (WORD_SPACING)`, `reforge/compose/render.py`
- **Code changes:** `WORD_SPACING` reduced 16 -> 6; horizontal tight-crop added in
  `compose/render.py`.
- **Resolution:** Review `2026-04-03_024039` confirmed "spacing looks much better",
  composition rating 2/5 -> 3/5.

### Chunk stitching produces visible height mismatch, not seam artifacts

- **Status:** Graduated (2026-04-19; promoted to CLAUDE.md "Hard-won design constraints")
- **Reviews:** 6 (2026-04-03 through 2026-04-16)
- **Principle** (now in CLAUDE.md): chunk stitching must use **ink-profile
  cross-correlation alignment**, not single-point ink-bottom alignment. The original
  problem was never visible seams -- it was chunks rendering at different heights so
  "understanding" looked like "under" + "standing" (two words, not one).
- **Resolution:** cross-correlation alignment in `model/generator.py` landed
  2026-04-14; human confirmed resolution in Review 8 (`2026-04-16_020920`) with "chunks
  now correctly on the same baseline". Eval un-suspended.
- **Code changes:** (1-4) various height normalizations, insufficient.
  (5) ink-density profile cross-correlation -- the fix.
- See `CLAUDE.md` > Hard-won design constraints > Long word chunking.

### Quality score disagrees with human candidate preference

- **Status:** Active
- **Reviews:** 7+ (2026-04-03 through 2026-04-14)
- **Principle:** Human picks a candidate that differs from the `quality_score` pick
  in 7 of 8 reviews (one agreement, outlier). Suggests `QUALITY_WEIGHTS`
  (background 0.20, ink_density 0.15, edge_sharpness 0.15, height 0.25, contrast 0.25)
  do not match human perception of "good handwriting".
- **Applies to:** `reforge/quality/score.py (QUALITY_WEIGHTS)`
- **Code changes:** OCR-aware candidate scoring (40% OCR weight), stroke width scoring
  (20% weight), height-aware target-closeness scoring. None moved the human agreement
  rate reliably past ~25%.
- **Blocker:** reweighting requires joining logged candidate scores against the
  human-selected candidate index, which needs a join key in the review JSON (or
  candidate-scores JSONL keyed by word+seed+timestamp). Candidate-eval human-pick
  join key work is the unblocker. Surfaced in spec 2026-04-19's next-turn proposal
  as direction (3).

### Ink weight inconsistency across words

- **Status:** Acceptable (promoted 2026-04-14)
- **Reviews:** 6 (2026-04-03 through 2026-04-14)
- **Principle:** The real stroke-weight improvement comes from candidate selection
  (stroke width scoring during best-of-N), not post-processing harmonization. Six
  consecutive reviews with no visible A/B difference on the harmonize pass.
- **Applies to:** `reforge/quality/harmonize.py`, `reforge/quality/score.py`,
  `reforge/model/generator.py` (candidate selection)
- **Code changes:** Blended morphological stroke-width harmonization; stroke-width
  scoring in candidate selection using style images as reference.
- **Acceptance rationale:** Within-line variability remains but is a generation-level
  property wrapper harmonization cannot fix. User confirmed A/B variants look identical
  but imperfection is within each line, not between variants.

### Hard words show gray box artifacts and poor apostrophes

- **Status:** In Progress
- **Reviews:** 8+ (2026-04-03 through 2026-04-19)
- **Principle:** The 5-layer gray-box defense works for typical words but short /
  punctuated / rare words still fail. `can't`, `than`, `impossible` were the
  canonical early cases; `mornings`, `something`, `really` surfaced later as a
  duplicate-letter hallucination class. Rating trajectory: 1/5 -> 2/5 -> 3/5.
- **Applies to:** `reforge/model/generator.py` (postprocess defense layers,
  contraction splitting), `reforge/config.py` (gray-box thresholds),
  `reforge/data/hard_words.json`
- **Code changes:** isolated-cluster-filter fix; OCR rejection threshold 0.3 -> 0.4;
  contraction splitting bypasses DP for apostrophe rendering; `_match_chunk_to_reference`
  lifts right-chunk ink weight; duplicate-letter words promoted to curated.
- **Review 8 (`2026-04-19_181354`): rating 2/5 -> 3/5.** Spec 2026-04-19
  (Duplicate-letter hallucination class) added `mornings`, `something`, `really` to
  `hard_words.json::curated` alongside `impossible`. Seed-42 test-hard: all three
  >= 0.889 OCR with zero critical flags. Medium-tier multi-seed test confirms OCR
  >= 0.5 across seeds 42/137/2718. The defect was the test-gating gap, not a
  generation regression. No code change to the generator was needed.

### Baseline alignment fragile across generation runs

- **Status:** In Progress
- **Reviews:** 10+ (2026-04-03 through 2026-04-19)
- **Principle:** Per-word baseline detection is brittle when handwriting body density
  varies (thin strokes, descender shapes, short words). Line-median with outlier
  clamping is the core structure; per-word density thresholds and character-aware
  detection refine it.
- **Applies to:** `reforge/compose/render.py`, `reforge/compose/layout.py`,
  `reforge/quality/font_scale.py`
- **Trajectory:** 4/5 -> 2/5 -> 1/5 -> 4/5 -> 2/5 -> 3/5 -> 3/5 -> 4/5 -> 2/5 -> 4/5.
  Rating has moved 1+ points in both directions across ten reviews; not Plateaued.
- **Code changes:** (1) max-baseline -> median-baseline per line. (2) outlier clamp at
  20% from median. (3) character-aware `detect_baseline` (25% body-density threshold
  for descender letters). (4) `equalize_body_zones()` post-normalization x-height
  equalize. (5) short-word baseline fix: per-word relative drop threshold and
  descender-word walkback fallback in `detect_baseline` (spec 2026-04-19).
- **Review 10 (`2026-04-19_154926`): 4/5 after short-word baseline fix.** Root cause
  was the absolute `BASELINE_DENSITY_DROP = 0.15` being too high for real handwriting
  (body density ~0.12-0.28), plus walkback falling to descender-bottom when it failed
  to find a row meeting `BASELINE_BODY_DENSITY = 0.35`. Fix: per-word relative drop
  (`min(body_peak * 0.3, BASELINE_DENSITY_DROP)`) + descender-word walkback fallback
  to `r - 1`. Regression coverage in
  `tests/quick/test_baseline.py::TestBaselineOnRealisticWordShapes` and
  `TestComposedLineBaselineAlignment`.
- **Active sub-issue:** `"by"` descender clipping persists (Review `2026-04-19_215858`
  flagged `"by"` as "small+superscript"). Distinct from cross-line drift: per-word
  bounding box underestimates vertical extent so descender tails get chopped. Candidate
  causes: over-tight postprocess crop on short words, aggressive body-zone equalization
  shrinking the canvas below descender reach, or `_reinforce_thin_strokes` shifting
  per-word crop bounds. Likely a dedicated spec target.

### Word sizing is inconsistent (single-char uppercase)

- **Status:** Plateaued (promoted 2026-04-10 per spec D2)
- **Reviews:** 7 (2026-04-03 through 2026-04-13)
- **Principle:** Capital `I` fills the 64px canvas; lowercase body then appears tiny
  by comparison. Human wants "lowercase body roughly 1/2 the size of capital I".
  Fundamentally a DiffusionPen case-awareness problem: the model produces uppercase
  single-char output at full canvas regardless of candidate selection pressure.
- **Applies to:** `reforge/quality/font_scale.py`, `reforge/config.py`
- **Code changes:** X-height normalization (reverted); unified 3+ char target (no
  effect); case-aware cap-height ratio 0.72 (regressed composition, reverted);
  height-aware target-closeness candidate scoring (2/5 unchanged). Four wrapper-layer
  interventions exhausted.
- **Plateau rationale:** 7 reviews, 4 code changes, rating stuck at 2/5 (or below).
  Promotion rule met.
- **Exit criteria:** retraining/fine-tuning on case-proportional data; different
  generative model with case awareness; pre-generation case handling
  (architectural); or user accepts 2/5 as the target.

### Composition quality improving but still variable

- **Status:** Active
- **Reviews:** 19+ (2026-04-03 through 2026-04-19)
- **Principle:** Composition rating spans 2/5 to 4/5 across a trajectory of
  candidate-selection, harmonization, baseline, and punctuation improvements. The
  largest positive effects came from candidate selection (OCR + stroke width scoring)
  and baseline-detection fixes; punctuation and apostrophe fixes each added smaller
  lifts.
- **Applies to:** `reforge/compose/layout.py` (baseline),
  `reforge/quality/font_scale.py` (sizing),
  `reforge/model/generator.py` (candidate selection, contraction splitting,
  trailing punctuation)
- **Recent rating trajectory (last 10 reviews, most recent last):**
  4, 4, 3, 4, 4, 3, 2, 2, 3, 3.
- **Last 5 median:** **3/5** (target: 4/5).
- **Review 14 (`2026-04-17_141320`):** 2/5, defects size_inconsistent +
  baseline_drift + letter_malformed. `ocr_min = 0.0` (fails CLAUDE.md primary gate).
  Three specific regressions: `can't` -> "cantt" (apostrophe duplicate-letter
  artifact, now fixed by `_match_chunk_to_reference`); `by` descender clipping
  (tracked in Baseline alignment); punctuation "very bad" (now resolved by
  Caveat dilate + 1.15x target).
- **Review 15 (`2026-04-18_154757`):** 2/5, Caveat glyphs landed but visually thin
  at production scale. `ocr_min=0` on every seed. Marked as punctuation sub-issue,
  fixed in Review 17.
- **Reviews 16-18 (`_213857`, `_233350`, `2026-04-19_021632`):** Option E (full-word
  DP) attempted and reverted due to seed-variant apostrophe stacking; Option W
  (split at `'t`) landed and stabilized contractions at 3/5; Caveat dilate lifted
  punctuation from None/5 to 3/5.
- **Review 19 (`2026-04-19_173130`):** 3/5, punctuation 3/5, `_match_chunk_to_reference`
  lifted contraction OCR to 1.000 on all four common contractions. "Every word +
  punctuation improved over prior runs."
- **Review 20 (`2026-04-19_181354`):** 3/5, hard_words 2/5 -> 3/5 via duplicate-
  letter curation.
- **Review 21 (`2026-04-19_215858`):** 3/5, defects size_inconsistent + baseline.
  User flagged `"I can't"`, `"it was a"`, `"exactly"` as "superscript" + `"so"`,
  `"by"` as "small+superscript". This was the review that established size_inconsistent
  is not an x-height-spread problem -- see the Cross-word size balance finding below
  and the methodology note at the top of this file.
- **Remaining defects:** `baseline_drift` (active sub-issue on `"by"`),
  `size_inconsistent` (Cross-word size balance finding), `letter_malformed`
  (intermittent).

### Apostrophe rendering is consistently poor

- **Status:** Resolved (2026-04-19 after `_match_chunk_to_reference`)
- **Reviews:** 10 (2026-04-04 through 2026-04-19)
- **Principle:** DiffusionPen renders apostrophes as oversized malformed blobs; even
  with contraction splitting, the single-character right-side chunks (`'t`, `'s`, `'d`)
  fail IAM's `MIN_WORD_CHARS=4` filter and come out with thin ink and small glyphs.
  The fix was a layered approach: split-path (2026-04-14) -> Option W split at `'t`
  (2026-04-18) -> `_match_chunk_to_reference` right-chunk matching (2026-04-19).
- **Applies to:** `reforge/model/generator.py` (contraction splitting, synthetic
  apostrophe, `_match_chunk_to_reference`), `reforge/config.py` (charset)
- **Code changes:** (1) `is_contraction()` + `split_contraction()`. (2)
  `make_synthetic_apostrophe()`. (3) `stitch_contraction()` with baseline alignment.
  (4) Tight-crop padding 1px -> 3px for 1-2 char right parts. (5) Bezier apostrophe
  rendering. (6) Option E (full-word DP, no overlay) attempted and reverted due to
  seed-variant `can''t` stacking. (7) Option W: split at `'t` so right part renders
  as `'t` via normal word path, synthetic apostrophe generator deleted.
  (8) `_match_chunk_to_reference`: measures left-chunk ink height + stroke width +
  ink-median; adjusts right chunk (bounded scale up to 1.8x; grayscale erode; double-
  pass ink-intensity shift).
- **Resolution:** Review 10 (`2026-04-19_173130`): seed-42 test-hard contraction OCR
  went from `can't=0.4, they'd=1.0, don't=0.125 CRITICAL, it's=1.0` to all four at
  **1.000**. Medium-tier test `test_contraction_sizing.py` gates right/left stroke
  ratio >= 0.85, ink-median delta <= 20%, ink-height delta <= 15% across 24 cases
  (4 words x 3 seeds x 2 metrics). Human: "every word + punctuation improved over
  prior runs." No apostrophe-specific defects flagged in the subsequent Review 21
  (`2026-04-19_215858`).

### Trailing punctuation is invisible in generated output

- **Status:** Resolved (2026-04-19 after Caveat dilate + 1.15x target)
- **Reviews:** 7 (2026-04-14 through 2026-04-19)
- **Principle:** DiffusionPen does not produce visible ink for trailing punctuation
  (commas, periods, question marks, exclamation marks, semicolons). Fix: strip
  trailing marks before generation; attach synthetic marks afterward. Caveat TTF
  glyphs replaced Bezier rendering for natural shape; morphological dilate + 1.15x
  Bezier-equivalent stroke width target brought production-scale visibility to par.
- **Applies to:** `reforge/model/generator.py` (`strip_trailing_punctuation`,
  `_generate_punctuated_word`, `_attach_mark_to_word`),
  `reforge/model/font_glyph.py` (Caveat rasterization, `render_trailing_mark`,
  `TRAILING_MARK_TARGET_MULTIPLIER`).
- **Code changes:** (1) `make_synthetic_mark()` with cubic Bezier curves.
  (2) 3x mark scaling. (3) Caveat TTF replaces Bezier. (4) Iterative morphological
  dilate targeting measured Bezier stroke (spec 2026-04-19). (5) Baseline-aware
  attachment using `compose.layout.detect_baseline` instead of full ink bottom.
  (6) `TRAILING_MARK_TARGET_MULTIPLIER = 1.15` retargets dilation against measured
  Bezier stroke (not nominal `body_height * 0.12`).
- **Resolution:** Review 6 (`2026-04-19_021632`) rated punctuation 3/5 with "all
  significantly improved, `;`, `?`, `!` all a bit small". Review 7
  (`2026-04-19_173130`) held 3/5 with "every word + punctuation improved over prior
  runs". `TestDilateToBezierBaseline` asserts 1.15x ratio at body_heights {18, 24, 32}
  across `. , ; ! ?`. No trailing-punctuation-specific defects flagged in Review 21
  (`2026-04-19_215858`).

### Single-character "I" loses ink, appears half-missing

- **Status:** Resolved (2026-04-17 variance check)
- **Reviews:** 2 (`2026-04-14_212810`, `2026-04-16_011718`)
- **Principle:** Single-char words filling the 64px canvas get scaled to the 26px
  `SHORT_WORD_HEIGHT_TARGET` (0.41x). INTER_AREA averages the thin 2-3px stroke into
  1px of gray, washing out ink. Strong-ink pixel count drops from 500-1000 to 80-166.
- **Applies to:** `reforge/quality/font_scale.py` (`normalize_font_size`,
  `_reinforce_thin_strokes`)
- **Code change:** `_reinforce_thin_strokes()` after aggressive downscale
  (scale < 0.6) of single-char words: faint ink pixels (80-200) darkened by 35%.
- **Resolution:** Spec 2026-04-17 variance check across seeds {42, 137, 2718, 7, 2025}
  with reinforcement ON vs OFF: mean strong-ink pixels (< 80) in the "I" bbox 368.8
  vs 289 (+27.6%, clears the >= 25% gate). `height_outlier_score` identical,
  `baseline_alignment` +0.43%, `ocr_min` +16%, `punctuation_visibility` +6.25%.
  No primary-gate regression. Reinforcement kept. `REFORGE_DISABLE_REINFORCEMENT=1`
  available to short-circuit for future variance checks.

### Cross-word size balance (size_inconsistent defect)

- **Status:** In Progress
- **Reviews:** 8+ (2026-04-14 through 2026-04-19; aggregated across Composition
  finding evidence)
- **Principle:** Short words (typically 2-3 char, especially those with descenders
  like `by` or without ascenders like `so`, `was`, `on`) render visibly smaller or
  off-baseline relative to their multi-char neighbors, producing a "superscript"
  read at the composition level. This is distinct from Plateaued single-char
  uppercase sizing (which is about `I` being too tall). This finding is about the
  *cross-word visual balance* on a composed line.
- **Applies to:** `reforge/quality/font_scale.py`, `reforge/compose/render.py`,
  `reforge/compose/layout.py`
- **Code changes:** (1) `equalize_body_zones()` pre-harmonize x-height equalize.
  (2) Short-word baseline fix (spec 2026-04-19 baseline alignment).
  (3) Spec 2026-04-19 body-zone sizing: `equalize_body_zones_pass2` attempt (shrunk
  dimensions) -- reverted after superscript regression in Review 21. (4) Baseline-
  preserving padded variant -- reverted pre-commit after qpeek preview confirmed
  the same regression.
- **Ruling (2026-04-19):** the `x_height_spread` metric is orthogonal to human
  perception of size_inconsistent. Reducing the metric does not fix the defect, and
  in both attempts produced a superscript visual regression. Mechanism: a
  visibly-shorter word reads as raised even when baseline-aligned, because the eye
  compares top extents across the line. Diagnostic preserved at
  `scripts/measure_word_sizing.py`; full analysis at `docs/sizing_diagnostic.md`.
  See Methodology note above.
- **Next levers (candidates for the next turn):**
  - Compose-layer: per-word baseline offsets (not clamped median) to let visibly-
    shorter words sit visibly lower without disrupting baseline alignment.
  - Finding-definition refinement: a `make test-human EVAL=size_inconsistent_perword`
    type that elicits *which* specific words the reviewer flags. Would convert the
    aggregate defect flag into an actionable per-word signal.
  - Accept as wrapper-layer plateau (like single-char sizing): fourth attempt would
    need design-level intervention.
- **Plateau consideration:** 3+ code changes and 3+ reviews without the rating
  moving 1+ point on this specific defect (composition rating has held 3/5 while
  size_inconsistent stays flagged). The Plateau rule is met for the *x-height-spread
  lever*; other levers (compose-layer, per-word eval) have not yet been attempted,
  so the finding as a whole is In Progress rather than Plateaued.

## Graduated Findings

### Chunk stitching uses ink-profile cross-correlation alignment

- **Graduated:** 2026-04-19 to `CLAUDE.md` > Hard-won design constraints > Long
  word chunking.
- **Core principle:** chunk stitching aligns via ink-density profile cross-correlation
  between chunks, not single-point ink-bottom anchors. The original problem was
  chunks rendering at different vertical positions, making "understanding" look like
  two separate words. Single-point alignment fails when ink distribution differs
  between chunks; cross-correlation finds the vertical shift that maximizes profile
  overlap.
- **Review trajectory:** 4 reviews of "eval broken" due to severe misalignment ->
  cross-correlation fix 2026-04-14 -> Review 8 (`2026-04-16_020920`) confirmed.
- **Code:** `reforge/model/generator.py` chunk stitch alignment.
