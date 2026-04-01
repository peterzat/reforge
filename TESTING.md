## Test Strategy Review -- 2026-04-01

**Summary:** Three-tier test strategy (quick/medium/full) with 102 quick tests (CPU-only, 0.89s measured), 30 medium tests (GPU, A/B quality + regression + OCR), and 3 full e2e tests. Total: 135 tests collected. Quick tests cover all CPU-side logic with synthetic data. Medium tests assert quality improvement via CV metrics and regression baselines. A pre-commit hook runs quick tests on every commit. A Makefile provides discoverable entry points for all tiers plus targeted inner-loop targets (test-regression, test-ocr). The current SPEC.md (test reliability and loop cadence) has all 7 criteria met. Test strategy is appropriate for this project's current stage.

**Test infrastructure found:** pytest 8.x, pytest.ini with 4 custom markers (quick/medium/full/gpu), root conftest.py implementing tier DAG (medium includes quick, full includes both), session-scoped GPU fixtures in tests/medium/conftest.py, pre-commit hook (.githooks/pre-commit via core.hooksPath), Makefile with test-quick/test-regression/test-ocr/test-medium/test-full targets, A/B experiment harness (experiments/ab_harness.py), CV evaluation module for autonomous quality scoring, quality regression baseline (tests/medium/quality_baseline.json). No CI, no coverage tooling.

### Findings

```
[WARN] ci-pipeline -- No CI pipeline for remote collaboration
  Current state: No .github/workflows/, .gitlab-ci.yml, or equivalent CI config.
    Tests run locally via pre-commit hook (quick tier) and manual Makefile targets.
    This is appropriate while the project is single-developer, but would become
    a gap if the project gains collaborators or is pushed to a shared remote.
  Recommendation: Defer until the project is pushed to a remote. At that point,
    add a CI workflow that runs quick tests on every push and medium tests on
    GPU runners for PRs. No action needed now.
```

```
[WARN] diagnostic-test-runtime -- test_word_clipping_diagnostic.py generates 12 words individually
  Current state: tests/medium/test_word_clipping_diagnostic.py generates 12 words
    individually with no best-of-N selection via direct ddim_sample + postprocess_word
    calls (not generate_word). This is the slowest medium test by a wide margin.
    The test is diagnostic (always passes if 10+ words are analyzed) and writes
    results to diagnostic_results.json. Not a correctness issue, but contributes
    disproportionate runtime to the medium tier.
  Recommendation: Low priority. The diagnostic test is run infrequently and its
    runtime is acceptable for its purpose (root-cause analysis).
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
  Current state: tests/medium/quality_baseline.json is committed to git and is updated
    in-place by test_quality_regression.py when the overall score improves (ratchet
    upward). This means running the medium test suite can produce a dirty working tree
    even when all tests pass. The file is intentionally committed (it records the
    quality floor), but the auto-update behavior means the test has a side effect
    on the working tree.
  Recommendation: Acceptable for the current workflow where the developer reviews
    and commits baseline updates. If this becomes friction, separate the "update
    baseline" action into a distinct command (e.g., make update-baseline) rather
    than having it happen as a side effect of test execution.
```

```
[NOTE] diagnostic-test-writes-to-source-tree -- test_word_clipping_diagnostic.py writes results to tests/medium/
  Current state: test_word_clipping_diagnostic.py writes diagnostic_results.json to
    tests/medium/ (line 116). This file is not gitignored (confirmed: git check-ignore
    returns exit 1). The test always passes (it is diagnostic, not assertive beyond
    word count), so it silently pollutes the working tree.
  Recommendation: Add tests/medium/diagnostic_results.json to .gitignore, or write
    to tests/medium/output/ which is already covered by the tests/*/output/ gitignore
    pattern.
```

### Status of Prior Recommendations

From the prior 2026-04-01 review:
- **OPEN** (carried forward): ci-pipeline. Still no CI. Appropriate for single-developer stage.
- **REVISED**: diagnostic-test-model-duplication renamed to diagnostic-test-runtime. Prior concern about duplicate model loading was resolved (test uses shared session fixtures). Restated as a runtime observation.
- **OPEN** (carried forward): coverage-tracking. Still no coverage tooling.
- **OPEN** (carried forward): quality-baseline-isolation. Still auto-updates on test run.
- **OPEN** (carried forward): diagnostic-test-writes-to-source-tree. diagnostic_results.json still not gitignored.

---
*Prior review (2026-04-01): Three-tier strategy with 135 tests. Two WARNs (no CI, diagnostic test runtime). Four NOTEs (no coverage, baseline mutability, diagnostic writes to source tree, spec criteria bookkeeping).*

<!-- TESTING_META: {"date":"2026-04-01","commit":"12e887f","block":0,"warn":2,"note":3} -->
