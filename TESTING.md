## Test Strategy Review -- 2026-04-09

**Summary:** Three-tier test strategy (quick/medium/full) with 151 quick tests (CPU-only, 0.89s measured), 35 medium tests (GPU, A/B quality, regression, OCR, parameter optimality, hard words), and 5 full e2e tests. Total: 191 tests collected. Pre-commit gates on quick tests; pre-push gates on quality regression. Module-level caching eliminates duplicate GPU work in regression tests. All SPEC.md criteria (14/14) are met and reflected in tests. Test strategy is appropriate for this project's current stage.

**Test infrastructure found:** pytest 8.x, pytest.ini with 4 custom markers (quick/medium/full/gpu), root conftest.py implementing tier DAG (medium includes quick, full includes both), session-scoped GPU fixtures in tests/medium/conftest.py, pre-commit hook (.githooks/pre-commit running quick tests), pre-push hook (.githooks/pre-push running regression test), Makefile with test-quick/test-regression/test-ocr/test-medium/test-full/test-hard/test-tuning/test-human/review targets, A/B experiment harness (experiments/ab_harness.py), CV evaluation module for autonomous quality scoring, quality regression baseline (tests/medium/quality_baseline.json), SSIM reference images (tests/medium/reference_output.png, tests/full/demo_reference.png), quality ledger (tests/medium/quality_ledger.jsonl), hard words ledger (tests/medium/hard_words_ledger.jsonl), human evaluation system (scripts/human_eval.py). No CI, no coverage tooling.

### Findings

```
[WARN] ci-pipeline -- No CI pipeline for remote collaboration
  Current state: No .github/workflows/, .gitlab-ci.yml, or equivalent CI config.
    Tests run locally via pre-commit hook (quick tier), pre-push hook (regression),
    and manual Makefile targets. Appropriate while single-developer.
  Recommendation: Defer until the project is pushed to a remote. At that point,
    add a CI workflow that runs quick tests on every push and medium tests on
    GPU runners for PRs. No action needed now.
```

```
[NOTE] coverage-tracking -- No coverage measurement configured
  Current state: No .coveragerc, no [tool.coverage], no pytest-cov. The quick tests
    cover all CPU modules (preprocess, quality, evaluate, compose, validation, config)
    but coverage gaps are invisible without measurement.
  Recommendation: Add pytest-cov and a coverage target for the quick tier when the
    module count grows beyond current size. Not urgent.
```

```
[NOTE] quality-baseline-isolation -- quality_baseline.json is a committed, mutable test artifact
  Current state: tests/medium/quality_baseline.json is committed to git and updated
    in-place by test_quality_regression.py when all metrics are non-regressing and at
    least one improves (ratchet upward). Running the medium suite can produce a dirty
    working tree even when all tests pass. Acceptable for the current workflow where
    the developer reviews and commits baseline updates.
  Recommendation: If this becomes friction, separate "update baseline" into a
    distinct command (e.g., make update-baseline).
```

### Status of Prior Recommendations

From the 2026-04-02 review:
- **RESOLVED**: duplicate-gpu-generation. Module-level `_cached_result` in test_quality_regression.py now caches GPU generation so both test methods share one inference pass.
- **RESOLVED**: diagnostic-results-not-gitignored. File is now staged for deletion (`git rm`), .gitignore entry is effective (`git check-ignore` returns 0).
- **OPEN** (carried forward): ci-pipeline. Still no CI. Appropriate for single-developer stage.
- **OPEN** (carried forward): coverage-tracking. Still no coverage tooling.
- **OPEN** (carried forward): quality-baseline-isolation. Still auto-updates on test run.

---
*Prior review (2026-04-02): Three-tier strategy with 167 tests. Two WARNs (no CI, duplicate GPU generation in regression test). Three NOTEs (no coverage, baseline mutability, diagnostic_results.json not gitignored).*

<!-- TESTING_META: {"date":"2026-04-09","commit":"485f4db","block":0,"warn":1,"note":2} -->
