## Test Strategy Review -- 2026-04-01

**Summary:** Three-tier test strategy (quick/medium/full) with a DAG: running a higher tier automatically includes all lower tiers. 40 quick tests (CPU-only, <1s), 6 medium tests (GPU, A/B quality assertions), 1 full e2e test (GPU, pipeline + CV assertions). Total: 47 tests. Medium tests assert quality improvement (CFG effectiveness, postprocessing defense, harmonization consistency), not just crash-freedom.

**Test infrastructure found:** pytest 8.x, pytest.ini with 4 custom markers, root conftest.py implementing tier DAG, session-scoped GPU fixtures in tests/medium/conftest.py, A/B experiment harness (`experiments/ab_harness.py`), CV evaluation module for autonomous quality scoring. No CI, no pre-commit hooks.

### Findings

```
[WARN] automatic-test-execution -- No mechanism runs tests automatically
  Current state: No CI pipeline (.github/workflows/ absent), no pre-commit hooks
    (only sample hooks in .git/hooks/), no Makefile with test targets, no tox/nox.
    Tests run only when manually invoked via `python -m pytest`.
  Recommendation: Add a pre-commit hook that runs `pytest tests/quick/ -x -q`
    (sub-second, no friction). If the project moves to a remote, add a CI workflow
    that runs quick tests on push and medium/full on GPU runners.
```

```
[FIXED] medium-tier-coverage -- Medium tier now has 6 tests with quality assertions
  Fixed 2026-04-01: Expanded from 1 test to 6 across three test classes:
    - TestCFGQuality (2): asserts CFG=3.0 improves ink contrast over CFG=1.0,
      and produces clean backgrounds.
    - TestPostprocessingEffectiveness (2): asserts postprocessing improves background
      cleanliness, and eliminates gray box artifacts on short words.
    - TestHarmonizationEffectiveness (2): asserts harmonization improves stroke weight
      consistency, and produces reasonable word height ratios.
  Session-scoped fixtures in tests/medium/conftest.py avoid reloading models per test.
```

```
[NOTE] fixtures-directory-empty -- tests/fixtures/ exists but is empty
  Current state: All test data is created inline as synthetic numpy arrays. This works
    and is self-contained, but means each test reconstructs similar word-like images
    independently.
  Recommendation: Extract common synthetic image builders (e.g., "word image with ink
    region," "sentence image with N words") into a conftest.py or a shared fixture
    module. This reduces duplication and makes tests easier to read. Not urgent since
    the inline approach is working.
```

```
[NOTE] coverage-tracking -- No coverage measurement configured
  Current state: No .coveragerc, no [tool.coverage] in any config file, no coverage
    reporting in any command documented in CLAUDE.md.
  Recommendation: Add `pytest-cov` and a coverage target for the quick tier. This is
    not critical at this stage, but becomes useful once the module count grows. The
    quick tests cover the main CPU modules (preprocess, quality, evaluate, compose,
    validation, config) but gaps are hard to see without measurement.
```

```
[FIXED] e2e-test-quality-assertions -- Full e2e test now includes CV quality assertions
  Fixed 2026-04-01: Added assertions for check_gray_boxes (must be False),
    check_ink_contrast (> 0.3), and check_background_cleanliness (> 0.3) to the
    e2e pipeline test.
```

```
[NEW] test-tier-dag -- Higher tiers automatically include lower tiers
  Added 2026-04-01: Root conftest.py implements a tier DAG via pytest_configure.
    `pytest tests/medium/` collects quick + medium tests (46 total).
    `pytest tests/full/` collects quick + medium + full tests (47 total).
    `pytest tests/quick/` collects only quick tests (40 total).
    This ensures regressions in lower tiers are always caught when running higher tiers.
```

### Status of Prior Recommendations

Initial review was 2026-03-31. Two WARN findings fixed 2026-04-01, one NOTE fixed, one new feature added.

---

<!-- TESTING_META: {"date":"2026-04-01","commit":"8787490","block":0,"warn":1,"note":2,"fixed":3} -->
