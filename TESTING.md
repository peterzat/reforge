## Test Strategy Review -- 2026-04-02

**Summary:** Three-tier test strategy (quick/medium/full) with 133 quick tests (CPU-only, 0.86s measured), 31 medium tests (GPU, A/B quality + regression + OCR + diagnostic), and 3 full e2e tests. Total: 167 tests collected. Quick tests cover all CPU-side logic with synthetic data. Medium tests assert quality improvement via CV metrics, regression baselines, SSIM reference comparison, and OCR accuracy. Pre-commit hook gates on quick tests; pre-push hook gates on quality regression. A Makefile provides discoverable entry points for all tiers plus targeted inner-loop targets (test-regression, test-ocr). The current SPEC.md (QA trust and scoring accuracy, 23 criteria, 0 met) is new work, not yet reflected in tests, which is expected. Test strategy is appropriate for this project's current stage.

**Test infrastructure found:** pytest 8.x, pytest.ini with 4 custom markers (quick/medium/full/gpu), root conftest.py implementing tier DAG (medium includes quick, full includes both), session-scoped GPU fixtures in tests/medium/conftest.py, pre-commit hook (.githooks/pre-commit via core.hooksPath), pre-push hook (.githooks/pre-push running regression test), Makefile with test-quick/test-regression/test-ocr/test-medium/test-full/review targets, A/B experiment harness (experiments/ab_harness.py), CV evaluation module for autonomous quality scoring, quality regression baseline (tests/medium/quality_baseline.json), SSIM reference image (tests/medium/reference_output.png), quality ledger (tests/medium/quality_ledger.jsonl). No CI, no coverage tooling.

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
[WARN] duplicate-gpu-generation -- test_quality_regression.py generates 5 words twice
  Current state: test_no_metric_regression and test_pixel_level_regression both call
    _generate_test_words() independently, each generating 5 words on GPU with
    identical seed. The output is deterministic, so the second call duplicates ~7s
    of GPU work. The CODEREVIEW.md (2026-04-02) also flagged this. A class-scoped
    fixture or module-level cache sharing the result would halve regression test
    runtime (~14s down to ~7s).
  Recommendation: Extract _generate_test_words result into a class-scoped fixture.
    This is the highest-value test performance improvement available.
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
    in-place by test_quality_regression.py when the overall score improves (ratchet
    upward). Running the medium suite can produce a dirty working tree even when all
    tests pass. Acceptable for the current workflow where the developer reviews and
    commits baseline updates.
  Recommendation: If this becomes friction, separate "update baseline" into a
    distinct command (e.g., make update-baseline).
```

```
[NOTE] diagnostic-results-not-gitignored -- diagnostic_results.json written to source tree
  Current state: test_word_clipping_diagnostic.py writes diagnostic_results.json to
    tests/medium/ (line 116). git check-ignore confirms this file is NOT gitignored
    (exit code 1), despite being added to .gitignore in a prior session. The
    .gitignore entry exists (line 12: tests/medium/diagnostic_results.json) but
    git check-ignore still returns exit 1, suggesting the entry is not matching
    correctly or the file is already tracked. The test always passes (diagnostic,
    not assertive beyond word count), so it silently pollutes the working tree.
  Recommendation: Verify the .gitignore entry is working. If the file is already
    tracked, run git rm --cached to untrack it.
```

### Status of Prior Recommendations

From the prior 2026-04-01 review:
- **OPEN** (carried forward): ci-pipeline. Still no CI. Appropriate for single-developer stage.
- **REVISED**: diagnostic-test-runtime renamed to duplicate-gpu-generation. The prior concern about diagnostic test runtime is less important than the duplicate GPU work in the regression test itself, which is now also flagged by CODEREVIEW.md. The diagnostic test runtime is acceptable for its purpose.
- **OPEN** (carried forward): coverage-tracking. Still no coverage tooling.
- **OPEN** (carried forward): quality-baseline-isolation. Still auto-updates on test run.
- **OPEN** (refined): diagnostic-test-writes-to-source-tree. The .gitignore entry exists but git check-ignore reports it is not effective. Needs investigation.

---
*Prior review (2026-04-01): Three-tier strategy with 135 tests. Two WARNs (no CI, diagnostic test runtime). Three NOTEs (no coverage, baseline mutability, diagnostic writes to source tree).*

<!-- TESTING_META: {"date":"2026-04-02","commit":"99cbfce","block":0,"warn":2,"note":3} -->
