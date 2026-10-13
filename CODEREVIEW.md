## Review -- 2026-10-13 (commit: d43de13)

**Review scope:** Full review against `origin/main`. The prior review's
`reviewed_up_to` (`5b1c24a`) is no longer an ancestor of HEAD (the README
fixup rebase rewrote it), so refresh conditions did not hold. 18 commits,
82 files.

**Summary:** Audit 2026-10-13 work: zone sizing with a single resample,
word-aware baseline detection and clampless placement, contraction stitch on
detected baselines, punctuated words routed through the full generation path,
seeded runs with a run manifest, gate switched to `x_height_consistency`,
CLAUDE.md split into rules plus `docs/`. Tests at review start:
`make test-quick` 328 passed; `make test-regression` 330 passed. After one
fix cycle: `make test-quick` 332 passed, `make test-regression` 334 passed
(4 new tests, no regressions). Post-fix /security re-check of the two changed
files found nothing new (0 BLOCK / 0 WARN / 5 NOTE overall).

**External reviewers:**
None configured.

**Built-in review:**
`/code-review high`: 10 findings, 9 kept after Step 6 (1 refuted by probe;
5 merged with Claude findings).

### Findings

[WARN, FIXED] reforge/quality/font_scale.py:113 -- Zone sizing undersizes words
without ascenders that end in `!` or `?`: "so?", "now!", "was?" come out at
0.77-0.81x the x-height of the same word without the mark.
  Evidence: `generate_word` attaches synthetic marks before
  `postprocess_words` sizes the word. `zone_class` strips trailing marks, so
  "so?" is class (0, 0) with prior 1.21, but `compute_ink_height` in
  `estimate_x_height` (line 124) measures the attached mark too. `!` and `?`
  are rendered 1.4-1.6x the base word's x-height on the word's baseline
  (`_render_trailing_mark_or_fallback`, body_h 12-30), so they stick up above
  an all-body word and raise its ink height by ~1.3x. Probe with the real
  `_attach_trailing_marks` and `plan_zone_scales` on a 30px all-body word:
  "so" scale 0.500; "so?" 0.405 (0.81x); "so!", "now!", "was!", "so?!" 0.384
  (0.77x). `.`, `,` and `;` leave ink height and scale unchanged; weak and
  strong ascender words ("it?", "three?") are unaffected (0.98-1.00x).
  This is the `size_inconsistent` defect in the other direction, on the policy
  that was adopted to fix it. No test covers punctuated words under zone
  sizing, and the gate words have no punctuation. `x_height_consistency`
  barely moves (0.983 to 0.954 in the probe) because it also measures ink
  height including the mark.
  Suggested fix: make `estimate_x_height` measure the base word's ink height
  when the word ends in synthetic marks (`SYNTHETIC_MARKS`), for example by
  dropping the rightmost `len(marks)` ink column runs (marks are attached
  after a tight crop plus a 1px gap, so each mark is its own column run)
  before calling `compute_ink_height` / `compute_x_height`. Keep the
  behavior unchanged for words without trailing marks (gate words, base
  words passed from `_attach_trailing_marks`). Add quick tests: "so?",
  "now!" and a descender word such as "gray?" get a zone scale within 3% of
  the unpunctuated word, built with the real `_attach_trailing_marks`.

[WARN, OPEN: human decision] reforge/evaluate/visual.py:567 --
`x_height_consistency` still cannot see mis-sizing of short all-body words,
and it moves in whole-pixel steps at the gate's tolerance. DO NOT AUTO-FIX:
changing the gating metric or its baseline requires explicit human approval
(CLAUDE.md "The evaluator is the human's"). (also claude-code; related
/security NOTE)
  Evidence: `cd7ee60` gave the evaluator its own `ALL_BODY_INK_PER_X_HEIGHT`,
  so editing `config.ZONE_HEIGHT_RATIOS` now moves the metric (fixed part of
  the prior WARN). The value is still the same measurement (1.21) the sizing
  policy uses. Zone sizing scales every all-body word of 3 or fewer letters
  so that `ink_h / 1.21 == ZONE_X_HEIGHT_TARGET` (blend weight 0 in
  `estimate_x_height`), and the metric's body group is `ink_h / 1.21`, so
  that half of the ratio equals the target by construction, whatever the
  generated pixels look like. If 1.21 is wrong for a hand, sizing and metric
  are wrong together. The long-word side uses `compute_x_height`, which zone
  sizing already weights 50-75% for 5+ letter words. The score is quantized:
  baseline 0.9536 on all seeds, and a 1px change in either median moves it
  0.05-0.07. /security adds that the constant is unprotected: no ask rule
  covers `visual.py`, value 1.29 passes a 20% oversize, and the new tripwire
  test still passes at 1.45.
  Suggested fix (human decision): measure the all-body group with a
  pixel-based x-height that does not use a sizing ratio (with a
  minimum-width guard), or calibrate the ratio on a held-out hand; use means
  or sub-pixel measurements to reduce quantization; move the constant into
  the protected `regression_gate.py`. Re-baseline with approval.

[NOTE] reforge/quality/font_scale.py:114 -- `_TRAILING_MARKS` (added by the
fix above) is a hand-copied literal of `generator.SYNTHETIC_MARKS`, kept local
to avoid importing torch. If the two drift, punctuated words are measured with
or without their marks inconsistently. Also raised by /security post-fix as a
non-security observation.
  Suggested fix: move `SYNTHETIC_MARKS` to `config.py` and import it in both
  modules.

[NOTE] reforge/model/generator.py:1319 -- `strip_trailing_punctuation` and
`strip_and_reattach_punctuation` (line 1448) are dead in production and still
tested. They keep the old one-mark, Bezier, raw-`compute_x_height` semantics
("what?!" -> ("what?", "!")) while production uses `split_trailing_marks` /
`_attach_trailing_marks`, so `test_synthetic_marks.py` tests partly cover a
path production no longer runs. (claude-code)
  Suggested fix: delete both helpers and their tests, or point the tests at
  `_attach_trailing_marks`.

[NOTE] reforge/pipeline.py:271 -- `run(seed=...)` calls `np.random.seed(seed)`,
which resets the caller's global numpy RNG. Nothing in `reforge/` draws from
the global numpy RNG (layout and render use their own `RandomState`), so the
call only adds the side effect. (claude-code)
  Suggested fix: remove it.

[NOTE] reforge/pipeline.py:75 -- `json.dump(default=float)` writes `np.bool_`
values as 1.0/0.0. `gate_details` holds `np.bool_` whenever the metric is a
numpy float, so the manifest records `"ink_contrast": 1.0` instead of `true`
(confirmed by probe). (claude-code)
  Suggested fix: a `default` that maps `np.bool_` to `bool` and other numpy
  scalars via `.item()`.

[NOTE] tests/medium/test_quality_regression.py:113 -- The gate seeds torch
once for the whole word list and runs without TF32, where `run()` seeds per
word (`seed * 1_000_003 + idx`) and sets matmul precision "high". The
"same stage graph as production" comment holds for post-processing only; a
TF32-only regression, or an extra RNG draw in an early word, behaves
differently in the gate. (claude-code)
  Suggested fix: reuse `run()`'s per-word seeding and numerics scope in the
  gate, or say in the comment that generation differs.

[NOTE] tests/medium/test_quality_thresholds.py:189 -- Unmodified medium tests
and experiment harnesses still hand-wire `normalize_font_size` +
`harmonize_words` (heights=True), the legacy chain production no longer runs:
`test_quality_thresholds.py:189,270,307`, `test_generation.py:141`,
`test_ocr_quality.py:33`, `test_hard_words.py:59`,
`test_duplicate_letter_hallucinations.py:49`, `experiments/sweep_*.py`,
`experiments/ab_harness.py`. CLAUDE.md now forbids this. Some are component
tests of the legacy functions and are fine. (carried; also claude-code)
  Suggested fix: move OCR, hard-word and generation tests to
  `postprocess_words`.

[NOTE] scripts/archive-output.sh:95 -- The archived metrics list records the
demoted `height_outlier_score` but not `x_height_consistency`, the gating
metric. (carried; also claude-code)
  Suggested fix: add `x_height_consistency` to `tracked`.

[NOTE] reforge/pipeline.py:73 -- `_write_manifest` writes `<output stem>.json`
next to any output and silently overwrites an existing file of that name
(`--output config.png` replaces `config.json`). (carried)
  Suggested fix: document it in `--output` help, or use `<stem>.manifest.json`.

[NOTE] tests/quick/test_run_manifest.py:36 -- `test_cli_accepts_seed`
assigns `sys.argv` directly (the `monkeypatch` fixture is unused), so the
value leaks to later tests, and it loads `reforge.py` by a cwd-relative path.
(carried; also claude-code)
  Suggested fix: `monkeypatch.setattr(sys, "argv", [...])` and resolve
  `reforge.py` from `__file__`.

[NOTE] reforge/compose/render.py:141 -- With the 20% clamp removed, per-word
y offsets are bounded only by baseline-row differences within a line, while
lines advance by max canvas height plus 12px. A word with an unusually low
detected baseline could intrude into the previous line. Not reproduced.
(carried)
  Suggested fix: a two-line compose test with extreme baseline rows.

[NOTE] reforge/quality/font_scale.py:236 -- `_reinforce_thin_strokes` still
applies only to single-character words, while zone sizing shrinks short
all-body words to ~0.2x in one INTER_AREA step. (carried)
  Suggested fix: measure stroke width of zone-sized short words before
  extending reinforcement.

[NOTE] reforge/model/generator.py:1341 -- `split_trailing_marks` returns a
mark-only token ("...", "?!") unsplit, so it goes to DiffusionPen, which
renders trailing marks invisibly. (carried)
  Suggested fix: render mark-only tokens synthetically at a body height from
  `ZONE_X_HEIGHT_TARGET`.

[NOTE] scripts/human_eval.py:927 -- `_worktree_dirty` runs `git status`
without `cwd=PROJECT_ROOT`, and it duplicates `pipeline._git_state()` added
in the same diff (same command and error handling), so review JSONs and run
manifests can drift on what "dirty" means. (carried; also claude-code)
  Suggested fix: use `pipeline._git_state()["dirty"]`.

Security NOTEs (from /security, 0 BLOCK / 0 WARN / 5 NOTE):

[NOTE] reforge/evaluate/visual.py:567 -- `ALL_BODY_INK_PER_X_HEIGHT` half-sets
the only gating metric but has no ask rule (see the WARN above).

[NOTE] .claude/settings.json:4 -- Evaluator ask rules are bypassable via
interpreter writes and do not cover most gate-defining files. (carried)

[NOTE] tests/medium/test_quality_regression.py:248 -- The push gate fails
open on a missing baseline/reference or hidden CUDA. (carried)

[NOTE] reforge/model/generator.py:1170 -- User words that fail OCR are
recorded in the tracked `reforge/data/hard_words.json`. (carried)

[NOTE] .claude/settings.local.json:56 -- Personal permissions file is tracked
in the public repo. (carried, outside this diff)

Built-in finding refuted by probe (dropped): `generator.py:1361`, that a
second mark after `,` or `;` ("so,.", "so;!") is placed below the baseline
because `detect_baseline` on the composite returns the comma tail. With the
real renderer the final mark's bottom lands on the word's baseline (offset 0)
in both cases; the synthetic tails do not extend below the word's ink
bottom.

### Fixes Applied

- [WARN] reforge/quality/font_scale.py:113 -- Added
  `_drop_trailing_mark_runs()`, called at the top of `estimate_x_height`:
  for a word ending in synthetic marks it crops off the rightmost ink column
  run per mark, so only the base word is measured. Words without trailing
  marks and mark-only tokens are unchanged, so the gate words and the
  `_attach_trailing_marks` call are unaffected. Verified: "so?", "so!",
  "now!", "so?!" now size at 1.00x of the bare word (was 0.77-0.81x); every
  rendered mark (`. , ; ! ?`, body heights 6-40) is a single column run, so
  the crop removes exactly the marks. New parametrized quick test
  `TestZoneSizing::test_trailing_marks_do_not_change_zone_scale` ("so?",
  "now!", "so?!", "gray?"); the three no-ascender cases fail without the fix.

### Accepted Risks

None.

---
*Prior review (2026-10-13, commit 5b1c24a): refresh review of the same audit
work before the rebase; 1 BLOCK (corrupted README, fixed and folded into the
original commit), 2 WARN fixed (seed range, human evals on production
sizing), 1 WARN open for human decision (x_height_consistency), 1 WARN user
action (README blob in history, resolved by the rebase), 12 NOTEs.*

<!-- REVIEW_META: {"date":"2026-10-13","commit":"d43de13","reviewed_up_to":"d43de134964b854b2118f478368aa47f6d7df6be","base":"origin/main","tier":"full","block":0,"warn":2,"note":18} -->
