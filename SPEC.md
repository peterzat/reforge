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

### Proposal (2026-04-19, refreshed)

**What happened**

*Spec work.* Spec 2026-04-19 (body-zone sizing) closed 6/6 via the failure-protocol escape. Two attempts to reduce `x_height_spread` on the demo sentence shipped the numeric win (5.500 -> 4.333, 21% reduction) but both introduced the same "superscript" regression: short words (`so`, `was`, `on`, `I`, `it`, `a`) read as floating above the baseline. Attempt 1 shrank image dimensions (`cdb7dad`, reverted in `484c89b`); Attempt 2 padded to preserve image height (discarded pre-commit after a qpeek preview). Root cause: the "superscript" read is about cross-word top-extent disparity, not baseline position. A visibly-shorter word reads as raised regardless of alignment. Artifacts preserved: `scripts/measure_word_sizing.py`, `docs/sizing_diagnostic.md`. Review `2026-04-19_215858` was the first in the corpus where the sizing A/B preferred the new variant but composition/freeform reported a regression -- evidence that the sizing A/B type measures something narrower than "composition size balance".

*FINDINGS automation + cleanup (5 commits after the spec closed).* Shipped a tightened findings loop so FINDINGS.md stays fresh via the `/spec` flow rather than drifting behind reviews:
- **FINDINGS.md cleanup** (`59148ef`): 837 -> 403 lines; 11 -> 12 findings. Chunk stitching graduated to `CLAUDE.md` (cross-correlation stitch alignment is now a permanent design constraint). Apostrophe rendering + Trailing punctuation moved to Resolved (contraction OCR=1.000 after `_match_chunk_to_reference`; Caveat + 1.15x target respectively). New finding: Cross-word size balance captures today's `size_inconsistent` escape.
- **`scripts/findings_sweep.py`** (`91da547`): marker-based detection (`FINDINGS_LAST_PROCESSED` at top of FINDINGS.md). Read-only; no qpeek. Exits 1 when reviews post-date the marker.
- **`/spec` loop hook** (`df77ec6`): project `CLAUDE.md` now instructs `/spec` in evolve mode to run the sweep before proposal generation, draft updates in the terminal, apply with ack, and bump the marker in the same edit. `make findings-sweep` added for ad-hoc preview. `human_eval.py` end-of-session message updated.
- **BACKLOG.md retired** (`d0c3276`). Durable deferrals that are still live sit in this proposal.

**Questions and directions for the next turn**

1. **Compose-layer lever for `size_inconsistent`.** `compose_words` (see `reforge/compose/render.py`, the `line_baselines` block around the `median_bl` clamp) collapses per-line baselines to a median and clamps outliers > 20% from median to the median. That works for single-mode height distributions but not for bimodal (tall + short) lines. A turn could investigate per-word baseline *offsets* -- not a clamped median -- to let visually-shorter words sit visibly lower on the line, closer to how real handwriting places `by` under `remember`. Starting artifacts from the escape turn: `scripts/measure_word_sizing.py`, `docs/sizing_diagnostic.md`. Guardrail: `make test-regression`. Budget: one focused turn.
2. **Per-word `size_inconsistent` eval.** The aggregate defect flag does not tell the coding agent *which* words the reviewer flagged. This turn's "I can't", "it was a", "exactly", "so", "by" complaint is verbatim freeform text, not structured signal. A dedicated `make test-human EVAL=size_inconsistent_perword` type (reviewer clicks / types the words that look wrong) would produce labeled per-word data. With the new `findings_sweep` loop, that data feeds directly into FINDINGS.md updates in the next `/spec` -- the infrastructure landed this session makes direction (2) visibly cheaper than when first proposed. Methodology-only, unblocks direction (1).
3. **Candidate-eval human-pick join key.** `QUALITY_WEIGHTS` reweighting has been blocked two specs (2026-04-17 D1, 2026-04-18) because the candidate-score JSONL has no key to join against human-selected candidates. Land the join key this turn (record human-selected index into review JSON, or key candidate-scores JSONL by word+seed+timestamp), verify via one `make test-human EVAL=candidate` session. Scope: just the key, not the tuning. Once 15+ paired samples accumulate, the "Quality score disagrees" finding (still Active, ~25% human agreement) unblocks.
4. **Graduation sweep** *(new, enabled by this session's cleanup).* The graduation rule (3+ reviews, 2+ code changes, stable + generalizable principle) is now operational and one entry (chunk stitching) has been promoted. At least three more findings sit near the bar and could be evaluated for graduation in a lightweight turn:
   - **Ink weight inconsistency** (Acceptable, 6 reviews). Principle: "stroke-weight improvement comes from candidate selection, not post-processing harmonization" -- a meta-pattern that would sharpen future feature design.
   - **Apostrophe rendering** (Resolved, 10 reviews). Principle: "asymmetric split-word stitching needs `_match_chunk_to_reference`-style matching of the short chunk to the long chunk's ink / stroke width / ink median".
   - **Trailing punctuation** (Resolved, 7 reviews). Principle: "OFL-font synthetic marks need morphological dilation targeting measured Bezier-equivalent stroke (`TRAILING_MARK_TARGET_MULTIPLIER = 1.15`) to stay visible at production body_height".

   Low risk, completes the cleanup arc; each graduation is a small CLAUDE.md edit + FINDINGS pointer. Could pair with direction (3) in the same turn (both are methodology infrastructure).
5. **Promote findings_sweep hook to the `/spec` skill itself** *(new, low priority)*. The hook currently lives in project `CLAUDE.md`. If the pattern proves valuable here, a future *zat.env* session could fold it into the skill at `~/src/zat.env/skills/spec/SKILL.md` so any project gets the behavior without per-project opt-in. Not for this project's next turn; noted so the idea isn't lost.

**Revisit candidates**

- **`"by"` descender clipping** -- recurring, most recently in review `2026-04-19_215858` ("small+superscript"). Distinct from direction (1): clipping is per-word layout bounding-box underestimate (`reforge/compose/layout.py` + `render.py`), not cross-word size balance. Dedicated spec, likely one-turn scope.

**Recommended default:** (4) + (3) as the primary next turn -- both are methodology-infrastructure work, low risk, and compound with what shipped this session. (4) closes the graduation arc; (3) unblocks `QUALITY_WEIGHTS`. (2) is the follow-on that turns per-word size_inconsistent into data. (1) waits until (2) lands so the lever is chosen against evidence rather than guessed. The "by" descender revisit is a cleaner defect-win alternative if the user wants concrete output quality progress this turn rather than infrastructure.

<!-- SPEC_META: {"date":"2026-04-19","title":"size_inconsistent composition defect (body-zone sizing)","criteria_total":6,"criteria_met":6} -->
