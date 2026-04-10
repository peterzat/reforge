## Test Strategy Review -- 2026-04-10

**Summary:** Three-tier test strategy (quick/medium/full) with 179 quick tests (CPU-only, 0.90s measured), 36 medium tests (GPU, A/B quality, regression, OCR, parameter optimality, hard words), and 5 full e2e tests. Total: 220 tests collected. Pre-commit gates on quick tests; pre-push gates on quality regression (12.9s measured). Module-level caching eliminates duplicate GPU work in regression tests. SPEC.md A1-A5 criteria have direct unit-test coverage in test_height_selection.py; B1-B4 are human-eval gated by design. Test strategy is appropriate for this project's current stage.

**Test infrastructure found:** pytest 8.x, pytest.ini with 4 custom markers (quick/medium/full/gpu), root conftest.py implementing tier DAG (medium includes quick, full includes both), session-scoped GPU fixtures in tests/medium/conftest.py, pre-commit hook (.githooks/pre-commit running quick tests), pre-push hook (.githooks/pre-push running regression test), Makefile with test-quick/test-regression/test-ocr/test-medium/test-full/test-hard/test-tuning/test-human/review targets, A/B experiment harness (experiments/ab_harness.py), CV evaluation module for autonomous quality scoring, quality regression baseline (tests/medium/quality_baseline.json), SSIM reference images (tests/medium/reference_output.png, tests/full/demo_reference.png), quality ledger (tests/medium/quality_ledger.jsonl), hard words ledger (tests/medium/hard_words_ledger.jsonl), human evaluation system (scripts/human_eval.py). No CI, no coverage tooling.

### Findings

```
[WARN] ci-pipeline -- No CI pipeline for remote collaboration
  Current state: No .github/workflows/, .gitlab-ci.yml, or equivalent CI config.
    Tests run locally via pre-commit hook (quick tier), pre-push hook (regression),
    and manual Makefile targets. Appropriate while single-developer.
  Recommendation: Defer until the project is pushed to a remote with collaborators.
    At that point, add a CI workflow that runs quick tests on every push and medium
    tests on GPU runners for PRs. No action needed now.
```

```
[NOTE] coverage-tracking -- No coverage measurement configured
  Current state: No .coveragerc, no [tool.coverage], no pytest-cov. The 179 quick
    tests cover all CPU modules (preprocess, quality, evaluate, compose, validation,
    config, OCR scoring, height selection, descender padding) but coverage gaps are
    invisible without measurement.
  Recommendation: Add pytest-cov and a coverage target for the quick tier when the
    module count grows beyond current size. Not urgent.
```

```
[NOTE] quality-baseline-isolation -- RESOLVED (spec 2026-04-10 B3)
  Prior state: tests/medium/quality_baseline.json auto-updated on any run where
    all metrics were non-regressing and one improved, ratcheting the baseline
    upward without human review.
  Current state: Auto-update is disabled. Baseline updates require
    `pytest --update-baseline`. Improvements are printed but not promoted.
  Baseline file format (spec 2026-04-10 C3): top-level "seeds" dict keyed by
    seed string, each containing a "metrics" sub-dict. Example:
      {
        "words": [...], "num_steps": 20, "guidance_scale": 3.0,
        "updated_at": "<iso>", "update_reason": "manual --update-baseline",
        "seeds": {
          "42":   {"metrics": {...}},
          "137":  {"metrics": {...}},
          "2718": {"metrics": {...}}
        }
      }
    Legacy single-seed baselines with a top-level "metrics" key are read only
    for seed 42; other seeds return None and the test prompts for a rebootstrap.
```

```
[NOTE] diagnostic-tests-no-assertions -- Two medium tests use assert True only
  Current state: tests/medium/test_descender_diagnostic.py uses `assert True` in its
    final assertion (CODEREVIEW NOTE #6 carried forward), and
    tests/medium/test_word_clipping_diagnostic.py is a similar diagnostic. Both
    consume GPU time (~10-15s combined) without providing regression protection.
    Consistent with their stated purpose ("diagnostic: no hard assertion, just
    record findings") but they run on every `make test-medium` invocation.
  Recommendation: Either (a) move them out of the medium tier into an explicit
    diagnostic target (`make test-diagnostic`) so they don't run during routine
    medium-tier validation, or (b) add a real assertion based on the stdout findings
    once the diagnostic stabilizes. Not urgent; they don't break anything.
```

### Status of Prior Recommendations

From the 2026-04-09 review:
- **OPEN** (carried forward): ci-pipeline. Still no CI. Appropriate for single-developer stage.
- **OPEN** (carried forward): coverage-tracking. Still no coverage tooling.
- **RESOLVED**: quality-baseline-isolation. Spec 2026-04-10 B3 disabled auto-update; baseline only moves on explicit `--update-baseline`.
- **NEW**: diagnostic-tests-no-assertions. Surfaced from CODEREVIEW NOTE #6 (refresh review on commit 7a19459); two diagnostic tests in the medium tier consume GPU time without assertions.

---
*Prior review (2026-04-09): Three-tier strategy with 191 tests. One WARN (no CI) and two NOTEs (no coverage, baseline mutability). Prior review's "duplicate-gpu-generation" and "diagnostic-results-not-gitignored" findings were resolved via module-level caching and `git rm` plus .gitignore entry.*

<!-- TESTING_META: {"date":"2026-04-10","commit":"e242118","block":0,"warn":1,"note":3} -->
