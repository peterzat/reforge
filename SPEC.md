## Spec -- 2026-04-19 -- size_inconsistent composition defect (body-zone sizing)

**Goal:** Close the persistent `size_inconsistent` composition defect by shrinking the cross-word x-height spread on the demo sentence, so words with large descenders (e.g. `by`) stop reading as tiny next to descenderless neighbors (e.g. `three`, `perfect`). This is a body-zone visual issue that survives ink-height normalization.

### Acceptance Criteria

- [ ] 1. A diagnostic utility at `scripts/measure_word_sizing.py` generates the demo.sh two-paragraph sentence on a single deterministic seed (42) and prints per-word (word, ink_height_px, x_height_px) in paste-friendly plain text to stdout. Re-runnable; no file writes required.
- [ ] 2. Define `x_height_spread = max(x_heights) / min(x_heights)` across all alphabetic word tokens in the demo sentence (exclude contractions' right chunks and single-char tokens). Capture the pre-fix baseline value in a new `docs/sizing_diagnostic.md`, commit the baseline, then land a code change that reduces the spread by at least 15% OR reaches `<= 1.4` on the same seed. If the pre-fix baseline is already `<= 1.4`, escape to documenting that finding in `docs/sizing_diagnostic.md` and marking the criterion met -- the defect is not x-height-spread in that case and this spec ends without a generation change.
- [ ] 3. `make test-regression` passes on seeds 42/137/2718 (`height_outlier_score >= 0.90`, `ocr_min >= 0.30`). The fix must not regress either primary gate.
- [ ] 4. `make test-quick` passes.
- [ ] 5. Human review: `make test-human EVAL=sizing,composition` is run once after the code change lands. The session's review JSON is saved. If the composition rating on the default seed is `< 3/5` OR the sizing A/B prefers the pre-fix variant, revert before commit. Otherwise, the criterion is met -- this is an execute-and-record criterion, not a lift gate.
- [ ] 6. A1 lesson preserved: `HEIGHT_OUTLIER_THRESHOLD` (1.10) and `HEIGHT_UNDERSIZE_THRESHOLD` (0.88) in `reforge/config.py` remain unchanged. Any body-zone fix lands in `font_scale.py` (`normalize_font_size`, `equalize_body_zones`) or a new post-font-normalize pass -- NOT by retuning the pass-1 harmonize thresholds.

### Context

**Defect evidence:**

- Review `2026-04-14_143735`: `"by" is tiny`.
- Review `2026-04-14_154117`: `"by" is still super small`.
- Review `2026-04-14_212810`: `"by" is tiny, punctuation is completely invisible`.
- Review `2026-04-16_011718`: `"by" is slightly bigger but still too small`.
- Reviews `2026-04-18_213857` / `_154757` / `2026-04-19_021632` / `_154926` / `_173130` / `_181354`: composition defects include `size_inconsistent` in 5 of the last 5 (5/5 pattern = Plateau hypothesis ruled out in prior spec; this spec attacks the generation-side lever).

**Why the current pipeline can miss this:**

- `reforge/quality/font_scale.py` normalize_font_size scales each word to a target ink-height (26px for 1-2 char words, 28px for 3+).
- "by" has a large descender (`y`), so its total ink-height is body + descender. After normalize, body (x-height) is disproportionately small.
- `equalize_body_zones` only scales DOWN words with oversized x-height (>105% of median). It does not scale UP undersized x-heights, so "by" stays small while "three" gets shrunk.
- Primary gate `height_outlier_score` is measured on ink-height, not x-height, so the defect sits outside the CV gate.

**Relevant files:**

- `reforge/quality/font_scale.py` -- `normalize_font_size`, `equalize_body_zones`, `_effective_x_height`.
- `reforge/quality/harmonize.py` -- `harmonize_heights`, `harmonize_heights_pass2` (pass-1 is A1-locked, see criterion 6).
- `reforge/quality/ink_metrics.py` -- `compute_x_height`, `compute_ink_height`.
- `reforge/config.py` -- `HEIGHT_OUTLIER_THRESHOLD`, `HEIGHT_UNDERSIZE_THRESHOLD`, `SHORT_WORD_HEIGHT_TARGET=26`.

**Design tension (not a constraint, but worth acknowledging):**

Scaling UP undersized x-heights inflates ascender/descender extents. Mitigation options:

- Cap scale-up at a small ratio (e.g. 1.3x) and skip if total ink height would exceed `1.10 * median` (would re-trigger `height_outlier_score`).
- Or use x-height as the primary normalization signal in `normalize_font_size`, leaving total ink-heights variable.

Either is a valid implementation path; the criteria gate on the measurable outcome, not the approach.

**Out of scope (tracked in BACKLOG.md, do not bundle):**

- `"by" descender clipping` (peaks of `y` cut off at composition time) -- separate BACKLOG entry; layout/render issue, not sizing.
- Alternate apostrophe shapes (proposal direction #4) -- separate turn.
- Side-channel 0-10 granular eval (proposal direction #3) -- methodology, separate turn.

**Failure protocol:**

- Criterion 2 escape (baseline already <= 1.4): commit `docs/sizing_diagnostic.md` showing the finding, mark criteria 2/3/4/6 met, skip criterion 5 (no code change), close spec. Add a BACKLOG entry noting size_inconsistent is not x-height-spread and requires a different diagnostic.
- Criterion 3 fails post-fix: revert the code change, keep the diagnostic script and `docs/sizing_diagnostic.md` (they are independently useful).
- Criterion 5 fails (human eval shows regression): revert before commit.

**zat.env practices carried in:**

- Smallest change that attacks the measurable defect. Don't refactor the harmonization pipeline.
- Write a diagnostic before the fix so the fix has a measurable target, and so reviewers can verify the claim.
- No push without explicit ask.
- If two consecutive fix attempts at the body-zone layer fail, stop and escape to documenting why x-height-spread is not the right lever.

---
*Prior spec (2026-04-19, Composition rating window): SHIPPED 6/6. All window medians = 3 on the 33-review corpus; CLAUDE.md target stays at last-5; FINDINGS.md gets a Methodology notes section recording the ruling.*

<!-- SPEC_META: {"date":"2026-04-19","title":"size_inconsistent composition defect (body-zone sizing)","criteria_total":6,"criteria_met":0} -->
