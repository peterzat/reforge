## Review -- 2026-04-10 (commit: 2ab52b6)

**Summary:** Refresh review of spec 2026-04-10 ("Objective alignment and convergence discipline") covering A1-A5, B1-B4, C1-C3, D1-D3, E1-E3. All 17 criteria marked met. The change set includes two new source files (`reforge/evaluate/regression_gate.py`, `scripts/metric_correlation.py`), two new quick test files (30 tests, all pass), a format migration of `quality_baseline.json` to per-seed entries, a rewrite of `test_quality_regression.py` for multi-seed gating via `PRIMARY_METRICS`, disable of auto-update-on-improvement per B3, and doc updates (CLAUDE.md Quality Target, FINDINGS.md Plateaued status, TESTING.md, `docs/metric_correlation.md`). Prior review (7a19459) is an ancestor of HEAD; commits e242118 and 2ab52b6 plus the uncommitted changes are in the focus set.

**Review scope:** Refresh review. Focus: 25+ files changed since prior review 7a19459. Already-reviewed set: none. Found two BLOCK issues from the baseline format migration that silently broke external consumers (archive script, A/B harness floor test), three WARNs (broken drift detector after multi-seed, stale README, CLAUDE.md wording error), and two NOTEs. All BLOCK and WARN findings auto-fixed via codefix. Quick tests: 209/209 pass before and after fixes.

**External reviewers:** Not configured.

### Findings

1. [BLOCK] scripts/archive-output.sh:75-117 -- Baseline format migration (spec C3) changed `quality_baseline.json` from a flat top-level `metrics` key to a nested `seeds.<seed>.metrics` structure, but the archive script still read `data.get('metrics', {})`. After the migration, every `make test-full` run silently wrote "metrics unavailable (empty baseline)" into `docs/OUTPUT_HISTORY.md`, losing all metric metadata in the historical archive. **Fixed.** Script now reads `data.get('seeds', {}).get('42', {}).get('metrics')` with a fallback to the legacy `data.get('metrics', {})` for backward compatibility. Verified by running the script, which produced a new 20260410-143302 entry with valid metric values for overall, composition_score, stroke_weight_consistency, word_height_ratio, ocr_accuracy, style_fidelity, ink_contrast, and background_cleanliness.

2. [BLOCK] tests/medium/test_ab_harness.py:27-36 -- `_baseline_floor()` also read the pre-migration flat `data["metrics"]`, so after C3 it silently returned `None` for every metric. The floor assertion at `test_harmonization_improves_stroke_consistency` (`if floor is not None: assert score_after >= floor`) became a no-op. The test still enforced `score_after >= score_before` but the absolute-floor guard against harmonization quality eroding over time was gone, with no CI signal. **Fixed.** Function now reads `data["seeds"]["42"]["metrics"]` with a legacy fallback matching the pattern used in test_quality_regression.py::_seed_baseline_metrics.

3. [WARN] tests/medium/test_quality_regression.py:315-325 + reforge/evaluate/ledger.py:72 -- The drift-check comment at line 315 said "runs on the reference seed only to keep the ledger view uncluttered," but `detect_drift(LEDGER_PATH, metric)` had no seed filter. The ledger now contains interleaved per-seed entries, so `window=5` spanned at most 2 full runs and mixed all 3 seeds. Cross-seed baseline variance (up to 0.0714 on `height_outlier_score`, near the 0.08 drift threshold) would produce spurious drift warnings. **Fixed.** Added a backward-compatible `context_filter` keyword to `detect_drift` that substring-filters ledger entries. The test now calls `detect_drift(..., context_filter=f"regression test seed={REFERENCE_SEED}")`. All 43 existing tests in `test_evaluate.py` pass unchanged (positional-arg callers are unaffected).

4. [WARN] README.md:185 -- Stale documentation. The paragraph described `test_quality_regression.py` as using "a fixed seed" (now 3 seeds: 42, 137, 2718), claimed "Any metric that drops by more than 0.05 fails the test" (now only PRIMARY_METRICS fail; the rest are diagnostics), and stated "baseline auto-ratchets upward" (removed per spec B3). All three claims were materially wrong after this spec. **Fixed.** Rewrote to describe the new behavior: 3 fixed seeds, per-seed baseline, primary-metric gating with reference to `docs/metric_correlation.md`, and manual `--update-baseline` only.

5. [WARN] CLAUDE.md:74 -- Quality Target conclusion said "When all three primary gate targets hold on all 3 seeds..." but the section above lists only two (`height_outlier_score >= 0.90` and `ocr_min >= 0.30`). Likely an artifact from an earlier draft that envisioned 3 correlated metrics clearing the B1 bar. **Fixed.** Changed to "all primary gate targets" (robust to future list-size changes).

6. [NOTE] reforge/evaluate/regression_gate.py -- New helper module is well-isolated from GPU code and covered by `tests/quick/test_regression_gate.py` (TestPrimaryMetricsConfig, TestGateFiresOnPrimaryRegression, TestDiagnosticsDoNotGate, TestInvertedMetric, TestOcrMinGate). Clean extraction from the medium test. No issue.

7. [NOTE] scripts/metric_correlation.py:40 -- The script imports `scipy.stats.spearmanr` at module level AND carries a hand-rolled `spearman()` helper (lines 119-139) with a stated motivation (lines 33-39) of keeping unit tests dependency-free. The test `test_scipy_wrapper_matches_pure_python_rho` pins both implementations to the same rho. This dual-implementation is a small maintenance cost; consider whether to drop the pure-python version once scipy is guaranteed in all test environments. Not urgent.

### Fixes Applied

1. **BLOCK #1:** Updated `scripts/archive-output.sh` to read `seeds.42.metrics` with a legacy-format fallback. Verified by running the script.
2. **BLOCK #2:** Updated `tests/medium/test_ab_harness.py::_baseline_floor()` to read `seeds.42.metrics` with a legacy-format fallback.
3. **WARN #3:** Added `context_filter` kwarg to `reforge.evaluate.ledger.detect_drift` and called it with `f"regression test seed={REFERENCE_SEED}"` from the regression test. Backward-compatible: all existing `detect_drift` callers (tests/quick/test_evaluate.py, 43 tests) use positional args and are unaffected.
4. **WARN #4:** Rewrote README.md:185 to describe the 3-seed primary-metric gating and manual baseline updates.
5. **WARN #5:** Corrected CLAUDE.md:74 from "all three primary gate targets" to "all primary gate targets."

Post-fix verification: 209/209 quick tests pass. Medium regression tests were not re-run (GPU-bound, outside preliminary review scope); the logic changes are backward-compatible and the critical paths are exercised by quick tests plus the archive-script dry-run.

### Accepted Risks

None.

---
*Prior review (2026-04-10, commit 7a19459): Refresh review of 17 unpushed commits implementing SPEC criteria A1-A5, B1-B4, C1-C2 for height-aware candidate selection and human eval. 3 WARN (stroke width reference scale mismatch partially fixed, stale SHORT_WORD_HEIGHT_TARGET comment fixed, dead imports in test_descender_diagnostic.py fixed) and 3 NOTE. All fixes applied.*

<!-- REVIEW_META: {"date":"2026-04-10","commit":"2ab52b6","reviewed_up_to":"2ab52b6d9473e4244b14db4ccddea63a1e40ad5d","base":"origin/main","tier":"refresh","block":2,"warn":3,"note":2} -->
