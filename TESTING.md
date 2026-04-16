## Test Strategy Review -- 2026-04-14

**Summary:** Three-tier test strategy (quick/medium/full) with 283 quick tests (CPU-only, 1.23s measured), 37 medium tests (GPU, A/B quality, regression, OCR, parameter optimality, hard words, diagnostics), and 5 full e2e tests. Total: 325 tests collected. Pre-commit gates on quick tests; pre-push gates on quality regression. SPEC.md B1-B4 criteria have direct unit-test coverage in test_synthetic_marks.py; C1-C3 are integration-verified through regression; D1-D2 are analysis scripts, not runtime code. B5 and E3 are human-eval gated by design. Test strategy is appropriate for this project's current stage.

**Test infrastructure found:** pytest 8.x, pytest.ini with 4 custom markers (quick/medium/full/gpu), root conftest.py implementing tier DAG (medium includes quick, full includes both), session-scoped GPU fixtures in tests/medium/conftest.py (device, style_features, unet, vae, tokenizer, uncond_context), pre-commit hook (.githooks/pre-commit running quick tests), pre-push hook (.githooks/pre-push running regression test), Makefile with 10 test targets (test-quick/test-regression/test-ocr/test-medium/test-full/test-hard/test-tuning/test-human/review/setup-hooks), A/B experiment harness (experiments/ab_harness.py), CV evaluation module for autonomous quality scoring, quality regression baseline (tests/medium/quality_baseline.json), SSIM reference images (tests/medium/reference_output.png, tests/full/demo_reference.png), quality ledger (tests/medium/quality_ledger.jsonl), hard words ledger (tests/medium/hard_words_ledger.jsonl), human evaluation system (scripts/human_eval.py with 9 eval types). No CI, no coverage tooling.

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
  Current state: No .coveragerc, no [tool.coverage], no pytest-cov. The 283 quick
    tests cover all CPU modules (preprocess, quality, evaluate, compose, validation,
    config, OCR scoring, height selection, descender padding, contraction splitting,
    synthetic marks, x-height normalization) but coverage gaps are invisible without
    measurement.
  Recommendation: Add pytest-cov and a coverage target for the quick tier when the
    module count grows beyond current size. Not urgent.
```

```
[NOTE] diagnostic-tests-no-assertions -- Two medium tests use soft assertions
  Current state: tests/medium/test_descender_diagnostic.py uses `assert True` in
    its final assertion, and tests/medium/test_word_clipping_diagnostic.py asserts
    only that 10+ words were analyzed (no quality gate). Both consume GPU time
    (~10-15s combined) without providing regression protection. Consistent with
    their stated purpose ("diagnostic: no hard assertion, just record findings")
    but they run on every `make test-medium` invocation.
  Recommendation: Either (a) move them out of the medium tier into an explicit
    diagnostic target (`make test-diagnostic`) so they don't run during routine
    medium-tier validation, or (b) add a real assertion based on the stdout findings
    once the diagnostic stabilizes. Not urgent; they don't break anything.
```

```
[NOTE] fixtures-directory-empty -- tests/fixtures/ exists but contains no files
  Current state: The directory is listed in the Architecture section of CLAUDE.md
    as holding "Synthetic test images" but is empty. Quick tests generate synthetic
    data inline using numpy helper functions (e.g., _word_img() in
    test_height_selection.py). This approach works and keeps tests self-contained,
    but the empty directory is misleading documentation.
  Recommendation: Either populate with shared fixtures that reduce inline setup
    duplication, or remove the directory and update CLAUDE.md to reflect that
    test data is generated inline. Low priority.
```

### Status of Prior Recommendations

From the 2026-04-10 review:
- **OPEN** (carried forward): ci-pipeline. Still no CI. Appropriate for single-developer stage.
- **OPEN** (carried forward): coverage-tracking. Still no coverage tooling.
- **RESOLVED**: quality-baseline-isolation. Spec 2026-04-10 B3 disabled auto-update. Remains resolved.
- **OPEN** (carried forward): diagnostic-tests-no-assertions. Still present; GPU time consumed without gating value.
- **NEW**: fixtures-directory-empty. Empty tests/fixtures/ directory contradicts CLAUDE.md documentation.

---
*Prior review (2026-04-10): Three-tier strategy with 220 tests. One WARN (no CI) and three NOTEs (no coverage, resolved baseline isolation, diagnostic tests without assertions).*

<!-- TESTING_META: {"date":"2026-04-14","commit":"bb5230e","block":0,"warn":1,"note":3} -->
