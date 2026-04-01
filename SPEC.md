## Spec -- 2026-04-01 -- Baseline alignment fix and test automation

**Goal:** Two independent improvements. (A) Fix the baseline alignment regression: `word_height_ratio` is 0.24 and `baseline_alignment` is 0.38, both indicating that words on the same line have wildly different sizes and vertical positions. Words like "Quick" (with a descender on Q) and "high" (with an ascender) should sit on a shared baseline, not bounce around. (B) Add automatic test execution so quick tests run on every commit without manual invocation, and medium tests are easy to trigger.

### Acceptance Criteria

#### A. Baseline alignment and word height consistency

- [ ] After the fix, the quality regression test baseline shows `baseline_alignment >= 0.55` (currently 0.38). The metric measures per-line standard deviation of word bottom positions; 0.55 corresponds to roughly 4-5px std dev, which is visually acceptable.
- [ ] After the fix, the quality regression test baseline shows `word_height_ratio >= 0.40` (currently 0.24). This metric scores max/min ink height ratio across words; 0.40 corresponds to a ratio under 1.6x, meaning the tallest word is at most 60% taller than the shortest.
- [ ] The fix does not regress OCR accuracy. Average per-word OCR in the medium test must remain above 0.6 and no single word below 0.3.
- [ ] The fix does not reintroduce gray-box artifacts. Quick tests must pass without modification.
- [ ] demo.sh output is visually inspected and words on the same line sit on a consistent baseline, with no word more than ~2x the height of its neighbors.

#### B. Automatic test execution

- [ ] A git pre-commit hook runs `pytest tests/quick/ -x -q` and blocks the commit if quick tests fail. The hook must be installed automatically (not require manual setup) via a mechanism documented in CLAUDE.md.
- [ ] A `make test` target (or equivalent simple command) runs the full medium test suite including GPU tests. A `make test-quick` target runs only quick tests.
- [ ] The Makefile (or equivalent) is documented in CLAUDE.md and README.md.

### Context

**Alignment regression.** The `baseline_alignment` metric dropped from 0.75 to 0.38 between quality baseline recordings. The `word_height_ratio` is 0.24 (max/min ratio around 4:1). `check_baseline_alignment()` measures the standard deviation of word bottom positions per line; 10px std dev scores 0.0. The composition system detects baselines per word via top-down density scanning and aligns words on a shared per-line baseline, but if words have very different heights (due to weak font normalization), the alignment suffers because the baseline detection gives different results for different-height words.

The likely root cause chain: font normalization is too conservative (scale clamped to [0.3, 1.2], area target 350 px^2/char) -> some words are much taller than others -> height harmonization only scales down outliers above 115% of median -> words with 50-80% of median height are left small -> composition aligns baselines but the height difference makes the std dev of bottom positions large.

Investigation should start with the font normalization parameters (`LONG_WORD_AREA_TARGET`, `SHORT_WORD_HEIGHT_TARGET`, `HEIGHT_OUTLIER_THRESHOLD`) and height harmonization logic in `harmonize.py`. The diagnostic instrument can help trace which words have extreme height ratios.

**Test automation.** Currently tests only run when manually invoked. TESTING.md flags this as a WARN. A pre-commit hook for quick tests adds sub-second feedback on every commit. A Makefile provides discoverable entry points for the medium and full tiers. This is straightforward infrastructure work.

**Coding practices (from zat.env).** Alignment fix: change one parameter at a time, run medium tests after each change, revert on regression. Two failed attempts means stop and re-evaluate. Automation: keep it simple, no external dependencies beyond make and git hooks.

---
*Prior spec (2026-04-01): Word clipping: diagnose and fix truncated characters (7/7 criteria met).*

<!-- SPEC_META: {"date":"2026-04-01","title":"Baseline alignment fix and test automation","criteria_total":8,"criteria_met":0} -->
