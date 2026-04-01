## Spec -- 2026-04-01 -- Test reliability and loop cadence

**Goal:** Make the test suite reliable for autonomous iteration and document which tests to run at each stage of the spec/implement/test loop. Fix the one flaky test, add targeted Makefile targets for the inner tuning loop, and document cadence in CLAUDE.md.

### Acceptance Criteria

#### A. Fix flaky test

- [x] `test_cfg_produces_clean_background` passes reliably when run from the full tier (`make test-full`). Currently fails intermittently due to nondeterministic generation with a single candidate and a tight threshold (0.2). Fix by using `num_candidates=2` so best-of-2 selection reduces variance.
- [x] `make test-full` passes twice in a row (consecutive runs, no code changes between them). This confirms no order-dependent or nondeterministic failures remain.

#### B. Targeted Makefile targets for inner loop

- [x] `make test-regression` runs only `test_quality_regression.py` (~14s including model load). This is the inner-loop test for parameter tuning: change a config value, run this, check if the baseline improved.
- [x] `make test-ocr` runs only `test_ocr_quality.py` (~14s). For verifying OCR accuracy after changes that affect generation or postprocessing.
- [x] All new targets are added to the `.PHONY` declaration.

#### C. Document loop cadence in CLAUDE.md

- [x] CLAUDE.md Commands section includes a "Development loop" subsection documenting which tests to run when, with measured timings:
  - Inner loop (editing code): `make test-quick` (0.8s)
  - Parameter tuning: `make test-regression` (~14s)
  - Feature complete: `make test` (2 min)
  - Pre-commit gate: `make test-full` (4.5 min, includes demo.sh + visual output)
- [x] The cadence section is concise (a table or short list, not paragraphs).

### Context

**Flaky test.** `test_cfg_produces_clean_background` in `tests/medium/test_ab_harness.py` generates "World" with `num_candidates=1` and asserts `check_background_cleanliness > 0.2`. With no seed and a single candidate, the result varies enough to occasionally fail. The failure is order-dependent: it reproduces when medium tests run after full e2e tests via the tier DAG. The fix is `num_candidates=2`, which matches other tests in the same file that already use multiple candidates for robustness.

**Loop cadence.** Measured timings show that the full medium suite (2 min) is too slow for rapid parameter iteration, but a single regression test (~14s) gives fast feedback on quality changes. The current Makefile only exposes coarse-grained targets (quick/medium/full). Adding `test-regression` and `test-ocr` enables a faster inner loop without running all 30 medium tests.

**Timing budget for autonomous coding.** The loop cadence is:
1. Edit code (seconds)
2. `make test-quick` to catch syntax/logic errors (0.8s)
3. `make test-regression` to check quality impact (14s)
4. If good, `make test` for full validation (2 min)
5. If good, commit (pre-commit hook re-runs quick tests)
6. Periodically, `make test-full` for visual regression check (4.5 min)

Total cycle time for a parameter change: ~15s (steps 1-3). Full validation: ~2.5 min. This supports rapid autonomous iteration.

---
*Prior spec (2026-04-01): Baseline alignment fix and test automation (8/8 criteria met).*

<!-- SPEC_META: {"date":"2026-04-01","title":"Test reliability and loop cadence","criteria_total":7,"criteria_met":7} -->
