## Review -- 2026-04-19 (commit: d0c3276)

**Review scope:** Refresh review against prior review commit `2005408`.
Focus: 17 file(s) changed since prior review. 2 already-reviewed file(s)
(`.claude/settings.local.json`, `tests/quick/test_contraction.py`) checked
for interactions only. Tier: refresh. The prior review's REVIEW_META
pinned `reviewed_up_to: 2005408` but the review body also evaluated the
uncommitted diff that became commit `1a6e03e` (baseline alignment,
contraction sizing `_match_chunk_to_reference`, Caveat 1.15x). Treating
`1a6e03e` as part of the focus set here, but the contraction + Caveat
work in it got a full-depth pass in the prior review. New-to-this-review
content: the entire spec 2026-04-19 "size_inconsistent" turn (commits
`09affec` through `d0c3276`), which consists of a diagnostic script +
doc + two body-zone-fix attempts that were both reverted after human
review showed a superscript regression, plus the rating-window analysis
and duplicate-letter hard-words promotion.

**Summary:** The spec 2026-04-19 "size_inconsistent" body-zone turn
correctly escaped via the failure-protocol path after two attempts at
shrinking `x_height_spread` both introduced the documented "superscript"
regression. Attempt 1 (`cdb7dad`) landed then reverted (`484c89b`) —
the revert is clean (5 files, 6 insertions / 209 deletions) and the
ledger `tests/medium/quality_baseline.json` is unchanged in this window.
Attempt 2 was reverted pre-commit per `docs/sizing_diagnostic.md`. The
diagnostic script `scripts/measure_word_sizing.py` and
`docs/sizing_diagnostic.md` survive as preserved artifacts for a future
lever-investigation turn, which is the spec's stated plan.

The rating-window analysis commit (`500b2d3`) is analysis-only: a new
`scripts/compute_rating_window.py` utility computes composition rating
medians across windows {3, 5, 7, 10, all}, yielding all = 3 on the
33-review corpus. Last-5 stays in CLAUDE.md per the decision rule. The
utility is well-scoped (no side effects, ascending-timestamp sort,
deterministic output) and the finding is recorded in
`reviews/human/FINDINGS.md` under a new "Methodology notes" section.

The duplicate-letter hallucination commit (`5c18d1b`) adds three words
(`mornings`, `something`, `really`) to `reforge/data/hard_words.json`'s
curated list and a new multi-seed medium test
`tests/medium/test_duplicate_letter_hallucinations.py` that asserts each
word scores OCR >= 0.5 on at least 2 of 3 seeds. No generation-side code
change. Test ran clean in my verification pass (303 passed).

New code in scope that was not in the prior review's body:
`scripts/compute_rating_window.py` (analysis),
`scripts/measure_word_sizing.py` (diagnostic),
`tests/medium/test_duplicate_letter_hallucinations.py` (regression),
and the stat-type annotation mismatch noted below.

Verification: 302 quick tests pass; 303 tests pass when the new
contraction sizing medium test is included; 303 pass when the duplicate-
letter medium test is included; 304 pass when the quality regression
test is included. Primary gates (`height_outlier_score >= 0.90`,
`ocr_min >= 0.30`) hold across all 3 seeds per test-regression.

**External reviewers:**
[qwen] Qwen/Qwen2.5-Coder-14B-Instruct-AWQ -- 28685 in / 5 out -- 52s
[qwen] No issues found.

No openai findings in this run (openai provider did not emit output).

### Findings

[NOTE] reforge/compose/layout.py:155 -- walkback uses
`BASELINE_BODY_DENSITY` (0.35) instead of the just-computed
`body_threshold` (0.25 for descender words / 0.35 otherwise). For
descender words whose peak body density falls between 0.25 and 0.35,
the walkback would find `found=True` if it used `body_threshold`,
skipping the descender fallback entirely. Carried forward from the
prior review's NOTE (same file, same pattern, not in Accepted Risks).
  Evidence: line 123 computes `body_threshold = 0.25 if has_descender
  else BASELINE_BODY_DENSITY`; line 144 (has_body_below check) uses it;
  line 155 (walkback) does not.
  Suggested fix: change line 155 to `if row_density[rb] >= body_threshold`
  for consistency. The `has_descender` fallback at line 159 can then be
  tightened (or removed) since walkback will succeed for the cases it
  was patching around. Not a bug at current test tolerances: the 6
  baseline tests pass within 3 px; the fallback path catches the
  `jump`/`by`/`py`/`gp` cases the NOTE flags.

Refresh-review verification notes:
- Security scan ran on 9 changed code-like files
  (`reforge/compose/layout.py`, `reforge/model/font_glyph.py`,
  `reforge/model/generator.py`, `scripts/compute_rating_window.py`,
  `scripts/measure_word_sizing.py`, `tests/medium/test_contraction_sizing.py`,
  `tests/medium/test_duplicate_letter_hallucinations.py`,
  `tests/quick/test_baseline.py`, `tests/quick/test_font_glyph.py`);
  0 findings. SECURITY.md updated to commit `d0c3276`, scope `paths`.
- `_match_chunk_to_reference` (generator.py:370-469): function new to
  the full-depth review (was present in `1a6e03e` but contraction-sizing
  criteria were verified by the prior review via other means). Read-
  through: bounded by `CHUNK_MAX_UPSCALE=1.8` and
  `CHUNK_MAX_DILATE_ITER=6`; for/else loop at line 452-460 falls back
  to 5x5 kernel for 2 more iterations after 6x 3x3 iterations don't
  reach the target; double-shift of ink intensity brackets the dilation
  step, which is documented by the step-2/step-4 comments (pre-shift
  so erode operates on intensity-matched pixels, post-shift because
  erode's min-filter drifts the median darker). Asymmetric: only
  handles adj-shorter-than-ref (the spec's contraction right-side case).
  Test coverage in `tests/medium/test_contraction_sizing.py` asserts
  stroke ratio >= 0.85, ink-height delta <= 15%, ink-median delta
  <= 20% across 24 cases (4 words x 3 seeds); ran clean.
- Diagnostic inconsistencies (non-findings, noted for record):
  - `tests/medium/test_contraction_sizing.py:12` docstring says
    `CHUNK_MAX_DILATE_ITER=4`, but `reforge/model/generator.py:367`
    defines it as `6`. Documentation drift; assertions are phrased
    via the real constant, so the test is still valid.
  - `tests/medium/test_duplicate_letter_hallucinations.py:35` has a
    type annotation `dict[str, list[tuple[int, float, str]]]` but the
    code appends `(seed, acc)` (2-tuple) and unpacks
    `for seed, acc in entries`. The 3-tuple type hint is vestigial.
    Test behavior is correct.
  - `_match_chunk_to_reference._stroke` (generator.py:401) uses
    `np.mean` over distances while the parallel function
    `_median_stroke_width_px` (font_glyph.py:54) uses `np.median`.
    Not a functional bug: the comparison within
    `_match_chunk_to_reference` is self-consistent (both ref and adj
    are measured with mean), but a future caller reading
    `_median_stroke_width_px` from font_glyph and reasoning about
    it against numbers from `_stroke` in generator would get slightly
    different values for the same image.
  None of these three rise to NOTE severity.
- The `1a6e03e` spec-2 commit bundles three specs (baseline alignment,
  contraction sizing, Caveat 1.15x). Not spaghetti: the commit message
  documents the bundling ("Two specs closed in one commit since the
  first was uncommitted when the second layered on top"), and each
  spec's criteria are independently verified via tests.
- Failed-attempt commits (`cdb7dad`, `484c89b`) are a symmetric
  land-then-revert pair. Examined the revert diff: 5 files,
  6 insertions / 209 deletions, exactly inverts `cdb7dad`. No orphaned
  helpers. `docs/sizing_diagnostic.md` keeps the attempt 1 record as
  part of the preserved diagnostic artifact (spec's stated intent).
- Hard-words additions (`mornings`, `something`, `really`) in
  `reforge/data/hard_words.json::curated` include `category` =
  `duplicate_letter_hallucination` (new category, two-word precedent
  is not set but the string is self-descriptive). Reviewed reason
  strings; they cite review timestamps that correspond to real
  `reviews/human/*.json` filenames.
- `.claude/settings.local.json` delta is 6 new allowed Bash commands,
  all for Caveat font download + `pkill qpeek`. Reasonable scope,
  low-risk.

### Fixes Applied

None. No BLOCK or WARN findings.

### Accepted Risks

None.

Informational observations (carried forward, not findings):
- `_attach_mark_to_word` parity: the walkback-threshold inconsistency
  in detect_baseline (NOTE above) is analogous to a general "two
  related thresholds, only one is parametrized on has_descender"
  pattern. Worth a cleanup pass in a dedicated spec along with the
  related suspect-list items the prior spec author deliberately
  deferred (20% clamp tolerance; median pull from bad detections).
  None are currently producing human-visible regressions.
- `strip_and_reattach_punctuation` (generator.py:1409) remains a
  test-only helper that wires through the mark/word kwargs; behavior
  preserved; no action.
- Type annotation drift in
  `tests/medium/test_duplicate_letter_hallucinations.py:35` and the
  `CHUNK_MAX_DILATE_ITER` docstring mismatch in
  `tests/medium/test_contraction_sizing.py:12` are documentation-only
  drift and do not change behavior; if either test file is touched
  again, fix in place.

---
*Prior review (2026-04-19, commit 2005408): Refresh review of spec
2026-04-19 Caveat dilate + baseline alignment + Option W contraction
split. 0 BLOCK / 0 WARN / 1 NOTE (walkback threshold consistency in
detect_baseline). External reviewers: openai o3 (high) plus qwen; one
openai BLOCK rejected after verification.*

<!-- REVIEW_META: {"date":"2026-04-19","commit":"d0c3276","reviewed_up_to":"d0c32762c1c6683a69d597bcefcfa784c013345a","base":"origin/main","tier":"refresh","block":0,"warn":0,"note":1} -->
