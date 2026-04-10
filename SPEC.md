## Spec -- 2026-04-10 -- Objective alignment and convergence discipline

**Goal:** Stop the loop from chasing proxies that do not track human preference. Measure which metrics correlate with human composition ratings, elevate those as primary gates, recognize plateaued problems so they stop consuming iteration budget, and define a concrete "done" target grounded in what is achievable on frozen DiffusionPen weights. This turn addresses convergence discipline, not handwriting quality directly.

### Acceptance Criteria

#### A. Metric-human correlation analysis

Three of four candidate reviews disagreed with the metric pick. Composition quality has oscillated 2/5 to 4/5 while metrics stayed flat. The current QUALITY_WEIGHTS were not empirically derived from human preference. Before tuning weights further, measure which metrics actually correlate with human composition ratings.

- [ ] A1. Add `scripts/metric_correlation.py` that loads every `reviews/human/*.json` file with a non-skipped `composition` rating and computes Spearman rank correlation between each metric in `cv_metrics` and the human composition rating. Metrics with zero variance across the dataset (e.g., `gray_boxes` always 1.0) must be reported as "constant, no correlation" rather than crashing or producing NaN. Output is a sorted table printed to stdout.
- [ ] A2. Commit the script's output as `docs/metric_correlation.md` (timestamp, dataset size, sorted correlation table, constant metrics called out). This is the empirical basis for the primary-metric selection in B1 and any future QUALITY_WEIGHTS changes.
- [ ] A3. The correlation analysis must also compute, per metric, the agreement rate with human candidate picks from the `candidate` eval type (currently 4 data points, 1 agreement). Report the sample size alongside the rate so its weakness is visible. The script must not fail when the candidate sample is small; it must report "insufficient data (n<10)" when appropriate.
- [ ] A4. `make test-quick` passes. Add a unit test that exercises the correlation script against a tiny synthetic dataset (2-3 fake reviews) and asserts constant metrics are flagged correctly.

#### B. Primary metric hierarchy and gating

The quality regression test currently gates on 9 tracked metrics. Improving one while another flatlines can look like progress when the user-visible output is unchanged, and the codereview already found a case where stroke_width_score was effectively zero for every candidate (ranking preserved, escaping detection). Elevate a small set of primary metrics, demote the rest to diagnostics.

- [ ] B1. Based on A2 results, pick at most 3 primary metrics as those with the strongest positive rank correlation with human composition rating across the reviews dataset. If fewer than 3 clear the bar (|rho| >= 0.2 and p < 0.3 given small N), pick only those that do. Document the selection with rationale in `docs/metric_correlation.md`.
- [ ] B2. Define `PRIMARY_METRICS` list in `reforge/config.py`. The quality regression test (`tests/medium/test_quality_regression.py`) must gate only on PRIMARY_METRICS and the existing OCR min gate; all other TRACKED_METRICS become diagnostics that are printed but do not fail the build. Update `REGRESSION_TOLERANCE` handling so diagnostic regressions are logged but non-fatal.
- [ ] B3. Disable automatic baseline updates in `test_quality_regression.py`. The current code auto-updates when all metrics are non-regressing and one improved; this normalizes drift. The baseline must only update via explicit `--update-baseline` flag. Codereview WARN #3 from 2026-04-09 acknowledged the risk; this closes it.
- [ ] B4. `make test-regression` passes after B2-B3 changes. The primary-metric-only gate must still catch a deliberate regression: add a test that mutates one primary metric downward and confirms the gate fires.

#### C. Multi-seed regression

The current regression uses one fixed seed. Changes can hill-climb that specific seed's output without generalizing. Add multi-seed evaluation so promotion requires stability across seeds, not a lucky local optimum.

- [ ] C1. Extend `test_quality_regression.py` (or add a sibling test) to run the baseline words list at 3 seeds (e.g., 42, 137, 2718). Each seed produces independent metric scores. The gate passes only when every primary metric is non-regressing across all 3 seeds. Ledger records per-seed results.
- [ ] C2. Generation time must stay within acceptable bounds for the pre-push hook: `make test-regression` total runtime should remain under 60 seconds (current ~14s, 3-seed adds roughly 2x). If the budget is tight, run seeds in parallel or reuse cached style features; do not add runtime by loading models three times.
- [ ] C3. Multi-seed baseline file format: either 3 separate baselines keyed by seed, or one baseline with per-seed entries. Prior single-seed `quality_baseline.json` must be migrated or re-bootstrapped via `--update-baseline`. Document the format in a comment at the top of the JSON or in `TESTING.md`.

#### D. Plateau recognition

The sizing finding has survived 6 reviews and 4 code changes (3 post-generation normalization approaches plus height-aware candidate selection) without moving past 2/5. Further iteration on the same intervention layer is unlikely to help. Recognize this explicitly so iteration budget stops being spent on base-model-limited problems.

- [ ] D1. Add a **Plateaued** finding status to `reviews/human/FINDINGS.md` with a defined promotion rule: a finding moves to Plateaued after 3+ code changes and 3+ reviews without the rating moving by at least 1 point. Plateaued findings require a design-level change to leave that status (retraining, different architecture, different intervention layer, or user accepting the limitation).
- [ ] D2. Move the "Word sizing is inconsistent" finding to Plateaued status based on existing evidence (6 reviews, 4 code changes, no movement past 2/5). Document the decision: this is a DiffusionPen-level limitation on single-character word generation that cannot be fixed at the wrapper layer, and the next intervention (if any) would require training.
- [ ] D3. Update `CLAUDE.md` (in the "Finding-driven iteration pattern" section) to reference the Plateaued status and instruct agents to skip Plateaued findings when selecting the next work target.

#### E. Define "done" for the project

The critique's structural point: the project may be converging toward the ceiling of the wrong system. Without a concrete quality target calibrated to what is achievable on frozen DiffusionPen weights, the loop will never declare victory. Write the target now.

- [ ] E1. Add a **Quality Target** section to `CLAUDE.md` with specific numerical goals for PRIMARY_METRICS (from B1), a minimum human composition rating (e.g., "median composition rating >= 4/5 across the last 5 reviews"), and a multi-seed stability requirement. Target numbers should be at or slightly above current best observed performance (composition 4/5 was "easily our best so far"), not aspirational.
- [ ] E2. Explicitly acknowledge scope limits: sizing at 2/5 is base-model-limited and not part of the target. The target is "the best achievable wrapper around frozen DiffusionPen," not "indistinguishable from real handwriting." This prevents endless chasing of problems that retraining would solve.
- [ ] E3. `make test-quick` and `make test-regression` still pass after all spec work. `make test-full` runs (though the demo output itself is expected to be unchanged; this spec is methodology, not quality).

### Context

**Why this spec is all methodology, no handwriting quality.** The external review landed a clear diagnosis: the loop is a competent hill-climber but not a convergence machine because its proxies are misaligned, its benchmarks are narrow, and plateaus are not recognized. Three of the last four candidate reviews showed metric-human disagreement. The composition score oscillates 2/5 to 4/5 while tracked metrics stay flat. A turn focused on "one more sizing fix" would prove the critique's point. Instead, this turn installs the infrastructure to make future quality turns honest.

**Dataset size constraint.** There are 19 human review files total. 17 have composition ratings. Only 4 have candidate A/B picks. Spearman correlation with N=17 is weak but not useless; report it with confidence caveats. The candidate-pick sample is too small to drive decisions (A3 must report it as insufficient). Both signals grow with every future `make test-human` run, so the infrastructure is permanent even if today's numbers are thin.

**Why not multi-style in this turn.** The project ships with exactly one style image. Adding a second requires either acquiring real handwriting samples, extracting from IAM, or using a synthetic reference. That is a real task and worth its own turn. Multi-seed discipline (C) captures most of the "narrow benchmark" risk at lower cost.

**Why disable baseline auto-update.** TESTING.md flagged this as acceptable but risky. Codereview 2026-04-09 also flagged it. With PRIMARY_METRICS reducing the gate to 3 signals, any ratchet upward of the baseline must be a deliberate promotion, not a side effect of a passing test run. This is the "champion/challenger" discipline the critique asked for, scoped to the baseline file rather than a new subsystem.

**Sizing as test case for plateau recognition.** Six reviews, four code changes, no movement past 2/5. The FINDINGS entry itself already says "appears to be a fundamental DiffusionPen limitation." Moving it to Plateaued is low-risk and demonstrates the rule. If a later turn finds a successful training-adjacent workaround, it can be reopened.

**What this spec does not do.** No new handwriting-quality fixes. No reweighting of QUALITY_WEIGHTS (that requires the correlation data from A first). No multi-style eval. No retraining. No human-gate-as-commit-gate (too strong a change for one turn; revisit after A/B data grows).

**Reference from the critique (actionable items carried forward to future turns, not this one):**
- Multi-style benchmark set (requires acquiring a second style image).
- Human-preference-gated promotion (requires rethinking the commit/push flow).
- Learned quality model (trained on reviews/human/ data once there are 50+ entries).
- Champion/challenger split beyond baseline file (frozen benchmark, separate promotion step).

---
*Prior spec (2026-04-10): Word sizing consistency and human eval baseline (11/11 criteria met). Height-aware candidate selection, human eval data collection across candidate/baseline/sizing/composition, prior spec cleanup. Sizing held at 2/5 after all interventions, confirming a plateau; this spec responds.*

<!-- SPEC_META: {"date":"2026-04-10","title":"Objective alignment and convergence discipline","criteria_total":17,"criteria_met":0} -->
