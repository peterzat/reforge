## Spec -- 2026-04-17 -- Contraction right-side, punctuation CV metric, variance check

**Goal:** The dominant remaining composition defect is the contraction right-side (single-character "'t", "'s", "'d"), which shares a root cause with Plateaued single-char sizing but is addressable as a punctuation-path problem rather than a sizing-path one. Intervene there (P1 experiment). Add a CV metric for trailing-punctuation visibility so regressions are caught automatically instead of waiting for human eval. Validate that the prior turn's `_reinforce_thin_strokes()` change was a net positive by comparing distributions across seeds. Close the two trivial codereview NOTEs and unblock candidate-score tuning by starting the data log (tuning itself waits for N>=15 samples).

### Acceptance Criteria

#### A. Reinforcement variance check

- [ ] A1. Generate the composition eval text on seed set {42, 137, 2718} plus two additional seeds (pick any deterministic values; record them in results) on current HEAD. Record per-seed: `height_outlier_score`, `baseline_alignment`, `ocr_min`, and the strong-ink-pixel count (pixels with value < 80) in the leading single-character "I" region of the output.
- [ ] A2. Repeat A1 on a branch (or with a guard) where `_reinforce_thin_strokes()` is replaced with an early return (no-op). Report both distributions side by side (mean, min, max per metric).
- [ ] A3. Decide: keep, tune, or revert `_reinforce_thin_strokes()`. Keep if strong-ink-pixel count on "I" is >=25% higher with reinforcement AND no CV metric regresses >=5% across the seed set. Revert if both conditions fail. Tune (adjust the 0.65x scalar and/or the `< 0.6` scale gate) if one condition passes and the other fails. Document the decision in the "Single-character 'I' loses ink" finding (promote to Resolved / Acceptable / Plateaued accordingly).

#### B. Punctuation visibility CV metric

- [ ] B1. Add `check_punctuation_visibility(composite_img, intended_text, word_positions) -> float` to `reforge/evaluate/visual.py`. For each trailing punctuation character in `intended_text`, measure ink coverage in the expected tail region of the corresponding word (e.g., last ~10% of the word's bounding box, height-extended below the baseline for comma/semicolon). Return the fraction of expected marks producing non-trivial ink (>=5 ink pixels with value < 128). Range [0.0, 1.0].
- [ ] B2. Wire the metric into `overall_quality_score` as a diagnostic field under a distinct key (e.g., `punctuation_visibility`). It prints in `make test-regression` output but does not gate the regression pass/fail decision (CLAUDE.md: primary gates are `height_outlier_score` and `ocr_min`; this is an added diagnostic, not a new gate).
- [ ] B3. `tests/quick/` covers the function with two fixtures: one where all expected marks are present (score close to 1.0) and one where all expected marks are absent (score close to 0.0). `make test-quick` passes.

#### C. Contraction right-side experiment (P1)

- [ ] C1. In the contraction-handling path of `reforge/model/generator.py`, add a configurable right-side canvas width (e.g., `CONTRACTION_RIGHT_SIDE_WIDTH` in `reforge/config.py`, defaulting to the current value). The configured width applies only to 1-2 char right-side parts (e.g., "t", "s", "d", "ll", "re", "ve", "m"). The UNet is fully convolutional in width (multiple of 16) per CLAUDE.md; verify the narrower width does not violate that constraint.
- [ ] C2. Generate the punctuation eval at the current width and at one narrower candidate (e.g., 128px), across seeds {42, 137, 2718}. Record OCR accuracy per contraction word and the composition CV metrics (`height_outlier_score`, `baseline_alignment`, `ocr_min`, plus `punctuation_visibility` from B).
- [ ] C3. Accept the narrower width as the new default only if it improves the multi-seed mean OCR accuracy on contractions by >=10% AND does not regress `punctuation_visibility` or any primary CV gate. Otherwise, leave the default unchanged and document the flat or negative response in the "Apostrophe rendering" finding. Do not run more than two width candidates this turn; if the first narrower candidate is a clear regression, stop.

#### D. Candidate-score logging

- [ ] D1. In the best-of-N selection path in `reforge/model/generator.py`, emit one JSONL line per generated word to `experiments/output/candidate_scores.jsonl` (create the file on first write). Fields: `word`, `seed`, `timestamp`, `candidates` (list of `{index, sub_scores: {...all individual score components...}, total}`), `selected_index`. Append-only; no rotation logic.
- [ ] D2. Logging is gated on env var `REFORGE_LOG_CANDIDATES=1` and off by default. `make test-regression` runtime is unchanged (within 1s of current baseline). `make test-human EVAL=candidate` sets the env var when invoked.
- [ ] D3. The candidate eval records the human-picked candidate index into a field (in the review JSON or the same JSONL) that can be joined against the logged word+seed+timestamp. Verify by running one `make test-human EVAL=candidate` review and confirming the join key is populated.

#### E. Codereview housekeeping (carried from 2026-04-16 NOTEs)

- [ ] E1. Remove the stale `Bash(kill 897414)` permission from `.claude/settings.local.json` (line 69 in that file as of commit d6afb40). `grep "897414" .claude/` returns nothing afterward.
- [ ] E2. Fix the comment/math mismatch at `reforge/quality/font_scale.py:75`. The comment claims "map [80, 200] toward [40, 140]" but `* 0.65` produces [52, 130]. Either correct the comment to match the math or adjust the scalar to match the comment. Prefer correcting the comment unless the [40, 140] range is intentional and testable.

#### F. Integration gates

- [ ] F1. `make test-quick` passes.
- [ ] F2. `make test-regression` passes on all 3 seeds (`height_outlier_score >= 0.90`, `ocr_min >= 0.30`).
- [ ] F3. `make test-human EVAL=composition,punctuation` runs. Composition rating >= 3/5 (no regression from current 3/5). Punctuation rating improves by >=1 point over the most recent prior punctuation review, OR documentation explaining why the proposed intervention did not move the rating.
- [ ] F4. Last-5 composition rating median advances back to >= 4/5. Aspirational: generation variance may prevent this even when the code is correct. If not reached, FINDINGS.md records the distance and the next-best candidate intervention.

### Context

**Prior turn (2026-04-16, spec "Stabilize composition at 4/5, close stale findings", 12/14 criteria met):** Found and fixed the "I" ink-loss root cause in font normalization via `_reinforce_thin_strokes()` (font_scale.py). Un-suspended and Resolved the stitch eval (cross-correlation alignment confirmed). Investigated "by" short-word sizing (93% of median ink height, no action needed; the perceived smallness is a DiffusionPen letter-proportion characteristic). FINDINGS.md housekeeping. Two small codereview NOTEs left unaddressed (carried into E above). Composition median regressed 4/5 -> 3/5 in the post-change eval; within the long-run 2/5-4/5 variance range, but A tests whether reinforcement is inert or a mild regression.

**Why punctuation now:** Three of the five In Progress findings share a single-char canvas-fill root cause (apostrophe right-side, trailing punctuation on contractions, "I" ink loss). "I" is addressed in A. The contraction right-side is the remaining high-leverage wrapper-layer intervention before the single-char problem is Plateaued end-to-end. P1 (narrower right-side canvas) is a falsifiable experiment with a clear accept/reject criterion (C3).

**Why a CV metric for punctuation (B) and not P3/P4:** Punctuation visibility has swung across reviews without reliable early warning. Adding a numeric diagnostic catches obvious regressions in `make test-regression` without waiting for human eval. P3 (mark proportionality sweep) and P4 (vertical placement audit) are deferred; they are pure tuning on top of a metric that doesn't yet exist, and P3 requires a human A/B eval per step which is too much for one turn without B already in place.

**Why candidate logging (D) now:** The `quality_score_disagrees` finding has been Active across 8+ reviews with ~25% human-metric agreement, blocked on data. This turn delivers only the log infrastructure; tuning waits for N>=15 samples.

**Out of scope:**
- **P2 (fully synthetic contraction suffix).** Larger design change. Gated on C's outcome; revisit next turn if C is a flat response.
- **P3 (mark proportionality sweep), P4 (mark vertical placement audit).** Tuning / diagnostic work that should follow B, not precede it.
- **Gate-window widening (last-5 -> last-7/-10).** Methodology tweak only. Defer until the data shows the current window is measuring the wrong thing.
- **`QUALITY_WEIGHTS` reweighting.** Blocked on the candidate log from D.
- **Plateaued single-char sizing.** Requires retraining or architecture change per CLAUDE.md; the contraction-path angle in C does not reopen the Plateaued finding, it works around it.

**zat.env practices carried in:**
- Work in small committable increments. Suggested order: E (housekeeping, cheapest) -> B (CV metric) -> D (logging) -> A (variance check) -> C (experiment, largest) -> F (gates). Commit after each group.
- Before GPU work, run `~/src/qwen-2.5-localreview/gpu-release` to free the warm server's VRAM.
- Run GPU tests aggressively; `make test-regression` (~14s) is the inner-loop gate after generation/quality code changes.
- When a new change causes previously passing tests to fail, revert the change rather than modify the tests.
- If two consecutive fix attempts fail on C, stop, document the negative result in FINDINGS, and do not escalate to P2 in the same turn.
- Do not push to the remote unless explicitly asked.

---
*Prior spec (2026-04-16): Stabilize composition at 4/5 and close stale findings (12/14 criteria met).*

<!-- SPEC_META: {"date":"2026-04-17","title":"Contraction right-side, punctuation CV metric, variance check","criteria_total":18,"criteria_met":0} -->
