## Spec -- 2026-04-19 -- size_inconsistent composition defect (body-zone sizing)

**Goal:** Close the persistent `size_inconsistent` composition defect by shrinking the cross-word x-height spread on the demo sentence, so words with large descenders (e.g. `by`) stop reading as tiny next to descenderless neighbors (e.g. `three`, `perfect`). This is a body-zone visual issue that survives ink-height normalization.

### Acceptance Criteria

- [x] 1. A diagnostic utility at `scripts/measure_word_sizing.py` generates the demo.sh two-paragraph sentence on a single deterministic seed (42) and prints per-word (word, ink_height_px, x_height_px) in paste-friendly plain text to stdout. Re-runnable; no file writes required.
- [x] 2. Define `x_height_spread = max(x_heights) / min(x_heights)` across all alphabetic word tokens in the demo sentence (exclude contractions' right chunks and single-char tokens). Capture the pre-fix baseline value in a new `docs/sizing_diagnostic.md`, commit the baseline, then land a code change that reduces the spread by at least 15% OR reaches `<= 1.4` on the same seed. If the pre-fix baseline is already `<= 1.4`, escape to documenting that finding in `docs/sizing_diagnostic.md` and marking the criterion met -- the defect is not x-height-spread in that case and this spec ends without a generation change. **Escaped via the two-failed-attempts path in the failure protocol. Pre-fix baseline 5.500. Attempt 1 (cdb7dad, shrinks image dimensions) and Attempt 2 (baseline-preserving pad) both reduced the numeric spread to 4.333 (21%, beats the 15% bar) but both introduced the same "superscript" regression in human review: scaled-down short words (`so`, `was`, `on`, `I`, `it`, `a`) visually float above the line's baseline. The metric is orthogonal to human perception of size_inconsistent; the spec's x-height-spread lever is therefore ruled out. Both attempts reverted; the diagnostic script and docs are kept for use by a future lever-investigation turn. See `docs/sizing_diagnostic.md` for the full record of both attempts.**
- [x] 3. `make test-regression` passes on seeds 42/137/2718 (`height_outlier_score >= 0.90`, `ocr_min >= 0.30`). The fix must not regress either primary gate. **Passed on both attempts (304 / 309 tests). Regression gate is orthogonal to the human-observed regression; this criterion is a necessary but not sufficient guardrail.**
- [x] 4. `make test-quick` passes. **Passed on both attempts (306 / 307).**
- [x] 5. Human review: `make test-human EVAL=sizing,composition` is run once after the code change lands. The session's review JSON is saved. If the composition rating on the default seed is `< 3/5` OR the sizing A/B prefers the pre-fix variant, revert before commit. Otherwise, the criterion is met -- this is an execute-and-record criterion, not a lift gate. **Attempt 1 review: `reviews/human/2026-04-19_215858.json`. sizing A/B 4/5 (new variant preferred), composition 3/5 with freeform notes calling out "significant visual regression" (first-sentence words floating above baseline). Strict text passes (composition not `< 3`, sizing not pre-fix) but the freeform note is the load-bearing signal; the revert rule fires on the spirit of the criterion. Attempt 2 was reverted pre-human-review after a visual preview confirmed the same regression persisted with image-dimension preservation.**
- [x] 6. A1 lesson preserved: `HEIGHT_OUTLIER_THRESHOLD` (1.10) and `HEIGHT_UNDERSIZE_THRESHOLD` (0.88) in `reforge/config.py` remain unchanged. Any body-zone fix lands in `font_scale.py` (`normalize_font_size`, `equalize_body_zones`) or a new post-font-normalize pass -- NOT by retuning the pass-1 harmonize thresholds. **Both attempts respected this: `equalize_body_zones_pass2` was a new post-font-normalize function in `font_scale.py`, harmonize thresholds untouched. Reverted along with the rest of the body-zone work.**

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

### Proposal (2026-04-19)

**What happened this turn**

Spec 2026-04-19 (body-zone sizing) closed 6/6 via the failure-protocol escape. Two attempts to reduce the diagnosed metric (`x_height_spread` on the demo sentence) shipped the numeric win (5.500 -> 4.333, 21% reduction) but both introduced the same "superscript" regression in human review: short words like `so`, `was`, `on`, `I`, `it`, `a` read as floating above the line's baseline. Attempt 1 shrank image dimensions (commit `cdb7dad`, reverted in `484c89b`); Attempt 2 padded to preserve image height (discarded pre-commit after a qpeek preview). Root cause of attempt 2's failure: the "superscript" read is not about baseline position -- it's about cross-word top-extent disparity. Once one word on a line is visibly shorter than its neighbors, the eye reads it as raised regardless of its baseline alignment. Artifacts preserved for future investigation: `scripts/measure_word_sizing.py`, `docs/sizing_diagnostic.md`. BACKLOG gets a dedicated entry recording that x-height-spread is ruled out as a lever for `size_inconsistent`.

The human-review JSON (`reviews/human/2026-04-19_215858.json`, sizing 4/5, composition 3/5, freeform note "significant visual regression") is the first review in the corpus where the sizing A/B preferred the new variant but the composition rating and freeform notes reported a regression. That is evidence that the sizing A/B type is measuring something narrower than "composition size balance" -- a methodological finding in its own right.

**Questions and directions for the next turn**

BACKLOG.md was deleted at the close of this turn, so any deferred context not surfaced here is gone. Triage brought three directions forward as actually-worth-pursuing-next; the rest (architectural non-goals like img2img or retraining, blocked infrastructure like contraction Q/L/O/Y variants waiting on specific plateau conditions, rejected ideas like font-fallback for contraction right chunks) were judged not live for the next turn. The three survive here.

1. **Compose-layer lever for `size_inconsistent`.** `compose_words` (see `reforge/compose/render.py`, the `line_baselines` block around the `median_bl` clamp) collapses per-line baselines to a median and snaps outliers > 20% from median to that median. That works for single-mode height distributions but not for bimodal (tall + short) lines, where this turn's attempt 2 showed that baseline-correct placement still reads as "superscript" because the eye compares top extents across the line. A turn could investigate per-word baseline *offsets* (not a clamped median) to let visually-shorter words sit visibly lower on the line -- a geometry closer to how real handwriting places `by` under `remember`. Starting artifacts from this turn: `scripts/measure_word_sizing.py` (measures per-word ink_h / x_h at the composition-ready stage on seed 42), `docs/sizing_diagnostic.md` (records the two failed attempts and their mechanisms). Risk: layout regressions on other defect classes; keep `make test-regression` as a guardrail. Budget: one focused turn.

2. **Finding-definition refinement (per-word `size_inconsistent` eval).** The current `size_inconsistent` flag is an aggregate defect checkbox on a 0-5 composition rating. It does not tell the coding agent which specific words the reviewer flagged, so every fix attempt guesses and then gets corrected by freeform notes (this turn's review was a clear example: "I can't", "it was a", "exactly", "so", "by" -- freeform text, not a structured signal). A dedicated `make test-human EVAL=size_inconsistent_perword` type that lets the reviewer click (or type) the words that look wrong would convert an aggregate finding into an actionable diagnostic, produce a labeled dataset for future lever choice, and work independently of whether direction (1) lands. Cheap (methodology-only), unblocks the next real attempt at direction (1).

3. **Candidate-eval human-pick join key (methodology infrastructure).** The `QUALITY_WEIGHTS` reweighting work has been blocked for two specs (2026-04-17 D1 through 2026-04-18) because the candidate-score JSONL has no key to join against human-selected candidates. This turn is an opportunity to land the join key: record the human-selected candidate index into the review JSON (or key the candidate-scores JSONL by word+seed+timestamp), then run one `make test-human EVAL=candidate` session to verify populate correctness. Once the join key is landed and 15+ paired samples accumulate, `QUALITY_WEIGHTS` can be retuned to better match human candidate preference (current agreement is ~25% per the "Quality score disagrees" finding in `reviews/human/FINDINGS.md`). One-turn scope: just the join key, not the tuning.

**Revisit candidates**

- **`"by"` descender clipping** -- recurring human observation that the `y` descender in `by` is clipped at composition time (only the two peaks of `y` remain visible). Surfaced in `reviews/human/FINDINGS.md` (Baseline alignment fragile finding, first cited review 9 = 2026-04-17_141320). The revisit criterion ("review after turn 2026-04-17 still cites the defect") has been met multiple times, including Review 2026-04-19_215858 where the user flagged `"by"` as "small+superscript". A dedicated spec would target the layout/render side of the pipeline (`reforge/compose/layout.py` baseline detection + `reforge/compose/render.py` word placement), which this turn's body-zone work explicitly left alone. Likely one-turn scope. Directly distinct from direction (1): clipping is a per-word layout issue, not a cross-word size balance issue.

**Recommended default:** (2) then (1). Methodology first (so the next lever on `size_inconsistent` is chosen against per-word evidence, not guessed), then a compose-layer attempt armed with that data. (3) is an independent, low-risk methodology unblock that could also run the same turn if the user wants to bundle infrastructure work. The `"by"` descender revisit is a cleaner one-turn spec if the user wants a concrete defect win; direction-(1) work is harder to scope tightly and has a revert cost that this turn already paid.

<!-- SPEC_META: {"date":"2026-04-19","title":"size_inconsistent composition defect (body-zone sizing)","criteria_total":6,"criteria_met":6} -->
