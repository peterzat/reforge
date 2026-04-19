## Spec -- 2026-04-19 -- Composition rating window: data-driven decision

**Goal:** Resolve whether the persistent composition 3/5 median across the last 5 reviews reflects a true quality plateau or is the 5-window dragging on older sub-3 ratings (reviews 9-12 are all 3/5, but reviews 7-8 were 2/5). Compute the composition median at multiple window sizes on the existing review corpus, decide whether to widen the CLAUDE.md target window, and record the decision so the rating-window question doesn't keep re-surfacing as a live hypothesis.

### Acceptance Criteria

- [x] 1. A utility at `scripts/compute_rating_window.py` (or equivalent) reads every `reviews/human/*.json` file, extracts per-review composition ratings, and prints medians at window sizes {3, 5, 7, 10, all}. Output is plain stdout and deterministic (sorted by review timestamp). Re-runnable at any time.
- [x] 2. The utility's current output is captured verbatim in a new `docs/rating_window_analysis.md` (or appended to `reviews/human/FINDINGS.md`), alongside the decision reached in criterion 3.
- [x] 3. Based on the data from criterion 1, make a decision: (a) if median at last-10 is >= 0.5 higher than median at last-5, widen `CLAUDE.md`'s Human-preference target window to 10 and update the two references to "last 5" in `CLAUDE.md` (lines ~51 and ~75 at current HEAD); (b) otherwise, leave the window at 5 and mark the rating-window hypothesis as ruled out in FINDINGS. Either branch is valid; the criterion is met by executing one. **Branch (b) executed:** all window medians equal 3 (delta = 0, below 0.5 threshold). CLAUDE.md unchanged; FINDINGS.md has a new "Methodology notes" section recording the ruling.
- [x] 4. If the decision is (a) (widen), the new target (last-10 median >= 4/5) must be plausible against current data: last-10 median is either already >= 4/5 or within 1 point. If the wider window still shows <= 3/5 median, fall through to (b) rather than setting an unreachable target. **Not activated** (branch b executed).
- [x] 5. `make test-quick` passes. (302 passed, 5.20s.)
- [x] 6. No code regression: `make test-regression` passes on seeds 42/137/2718. (304 passed, 16.36s.)

### Context

**Prior-turn carryover:**

- Four specs shipped today (commit `1a6e03e` + uncommitted duplicate-letter work) moved baseline 3/5 → 4/5, punctuation None/5 → 3/5, hard_words 2/5 → 3/5. Composition held at 3/5 across Reviews 9, 10, 11, 12, 8 (chronological: `2026-04-18_213857`, `_233350`, `2026-04-19_021632`, `_154926`, `_173130`, `_181354`).
- Human Review 12 and Review 8 both gave positive freeform notes ("punctuation is improved", "every word + punctuation improved over prior runs") while the composition number did not tick. This spec tests whether that mismatch is a window-lag artifact (older reviews 2/5 dragging the rolling median) versus a genuine quality ceiling.
- The duplicate-letter spec's write-up is uncommitted in the tree (`SPEC.md`, `reforge/data/hard_words.json`, `tests/medium/test_duplicate_letter_hallucinations.py`, `reviews/human/FINDINGS.md`). Committing is NOT in this spec's scope; it's a hygiene step that should happen before or after independently.

**Project target references to update (if criterion 3 branch-a):**

- `CLAUDE.md` line ~51: "Current median across the last 5 is 3/5"
- `CLAUDE.md` line ~75: "the last 5 human composition ratings is >= 4/5"

These are the two references the grep turned up; there may be more in `docs/`. The utility in criterion 1 is the source of truth on which windows to consider.

**Evidence the hypothesis is worth testing:**

The 6 most-recent reviews (chronological):
- Review 7 `2026-04-18_233350`: 3/5
- Review 6 `2026-04-19_021632`: 3/5 (Caveat dilate + baseline alignment landing)
- Review 11 `2026-04-19_154926`: 3/5 (short-word baseline fix)
- Review 12 `2026-04-19_173130`: 3/5 (contraction sizing + Caveat 1.15×)
- Review 8 `2026-04-19_181354`: 3/5 (duplicate-letter gate expansion)

Five consecutive 3/5 ratings in 24 hours, plus a 2/5 from Review 5 at `2026-04-18_213857` (Option E failure, reverted). The 5-window median is 3/5. A 10-window pulls in reviews going back to mid-April; whether those were 2/5 or 4/5 determines the picture.

**Failure protocol:**

- Criterion 4 fails (widening would set an unreachable target): fall through to criterion 3 branch-b; document as "rating-window hypothesis ruled out, plateau is real" in FINDINGS.
- Criterion 6 fails: revert. This spec shouldn't touch code paths under CV gates.
- Do not bundle: no new generation/compose/quality code changes in this spec.

**Out of scope (tracked in BACKLOG.md, do not bundle):**

- Review rubric update for `scripts/human_eval.py` (the proposal's direction #2 — separate methodology concern).
- QUALITY_WEIGHTS reweighting (blocked).
- New generation-side fixes for composition defects.

**zat.env practices carried in:**

- Smallest change that addresses the hypothesis. A utility that reads existing JSON is enough; do not build an elaborate analysis framework.
- Write the decision down (criterion 2) so the question doesn't resurface.
- No push without explicit ask.

---
*Prior spec (2026-04-19, Duplicate-letter hallucination class): SHIPPED 6/6 criteria (uncommitted). `mornings` / `something` / `really` added to curated hard_words; multi-seed test added. No generation-side code change needed — today's tree already generates these correctly. Hard_words eval 2/5 → 3/5.*

<!-- SPEC_META: {"date":"2026-04-19","title":"Composition rating window: data-driven decision","criteria_total":6,"criteria_met":6} -->
