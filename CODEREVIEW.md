## Review -- 2026-10-13 (commit: 9630e08)

**Review scope:** Refresh review. Focus: 6 file(s) changed since prior review
(commit d43de13): `reforge/quality/font_scale.py`,
`tests/quick/test_xheight_normalization.py`, `docs/OUTPUT_HISTORY.md`,
`docs/best-output.png`, and the archived output PNGs. 76 already-reviewed
file(s) checked for interactions only.

**Summary:** Two commits since the prior review: `8b876bf` (zone sizing crops
synthetic trailing-mark column runs before measuring x-height, plus four quick
tests) and `9630e08` (demo output refreshed from the final code). The crop is
sound: rendered marks never split into two column runs and always sit behind
at least 2 white columns. The archived PNG and `best-output.png` are
byte-identical, and OUTPUT_HISTORY has one new entry relative to
`origin/main`. Tests at review start: `make test-quick` 332 passed;
`make test-regression` 334 passed. One fix cycle was attempted and reverted
(see Fixes Applied), so the code is unchanged and tests are stable at 332.

**External reviewers:**
None configured.

**Built-in review:**
`/code-review high`: 10 findings, 10 kept after Step 6 (8 merged with Claude
or carried findings).

### Findings

[WARN, OPEN: requires manual intervention] reforge/quality/font_scale.py:98 --
`zone_class` treats `f` only as a
strong ascender, but a cursive `f` in this hand descends below the baseline
(`layout.DESCENDER_CAPABLE` already says so). Short `f` words are sized with
the (2, 0) ratio 2.26 when their ink is closer to the (2, 1) ratio 2.85, so
"for", "of", "if", "off" come out undersized: the `size_inconsistent` defect
in the other direction, on the policy adopted to fix it. (claude-code)
  Evidence: GPU probe, hw-sample style, PRESET_FAST, seeds 42/137/2718,
  production `postprocess_words`. Ink below the detected baseline is 25-34%
  of ink height for "for" (3/3 seeds), "if" (3/3), "off" (3/3); a
  side-by-side render confirms the `f` tail in "for", "of", "off". Measured
  ink/x-height on the raw images: "for" 2.91-4.00, "of" 2.78-4.27, "off"
  2.29-2.86 (median about 2.8). After sizing, compute_x_height of "for" is
  8, 9, 10 px against target 12.39, while same-class control "had" is 13,
  13, 13. Words of 3 or fewer letters use the prior alone (blend weight 0
  in `estimate_x_height`), so nothing corrects it. `zone_class` is used by
  the evaluator only to select (0, 0) words, and `f` words are never (0, 0),
  so the metric definition is unaffected.
  Suggested fix: in `zone_class`, set the descender flag for `f` as well
  (for example, check `_DESCENDERS | {"f"}` or add `f` to `_DESCENDERS`),
  keeping its ascender class at 2. Do not change `ZONE_HEIGHT_RATIOS`, the
  evaluator (`reforge/evaluate/`), the gate word list, or any baseline file.
  Add quick tests: `zone_class("for") == (2, 1)`, `zone_class("of") ==
  (2, 1)`, `zone_class("off") == (2, 1)`, and existing classes unchanged.
  Note the gate word "foxes" becomes (2, 1) and, at 5 letters (50% prior),
  sizes about 12% larger; run `make test-quick` and `make test-regression`.
  If the regression gate fails, revert the change and report back: do not
  re-baseline (CLAUDE.md, "The evaluator is the human's").
  Fix attempt (cycle 1, reverted): `_DESCENDERS = set("gjpqyf")` passed
  `make test-quick` (333) but failed `make test-regression` on seed 137:
  `x_height_consistency` 0.8855 < baseline 0.9536 (delta -0.0681, beyond
  the 0.05 tolerance). Diagnostics also moved: seed 42 `overall`
  0.7653 -> 0.6742 and `ocr_accuracy` 0.9000 -> 0.8286; seed 2718
  `composition_score` 0.6514 -> 0.5696, `baseline_alignment` 0.6521 ->
  0.7185. The likely driver is gate word "foxes" sizing ~12% larger and
  shifting the long-group median of a metric that moves in whole-pixel
  steps (see the next WARN). Options for the human: re-measure
  `ZONE_HEIGHT_RATIOS` with `f` words classed as descenders and
  re-baseline with approval; limit the `f` descender flag to words sized
  from the prior alone (3 or fewer letters), which leaves "foxes"
  unchanged (check this is not gate-gaming before adopting it); or accept
  the undersizing of short `f` words.

[WARN, OPEN: human decision] reforge/evaluate/visual.py:567 --
`x_height_consistency` still cannot see mis-sizing of short all-body words,
and it moves in whole-pixel steps at the gate's tolerance. DO NOT AUTO-FIX:
changing the gating metric or its baseline requires explicit human approval
(CLAUDE.md "The evaluator is the human's"). (carried; also claude-code;
related /security NOTE)
  Evidence: the all-body half of the metric is `ink_h / 1.21`, the same
  ratio zone sizing uses (blend weight 0 for 3 or fewer letters), so that
  half equals the target by construction. Score quantized: baseline 0.9536
  on all seeds; a 1px change in either median moves it 0.05-0.07. The
  constant has no ask rule and a 20% oversize passes at value 1.29.
  Suggested fix (human decision): measure the all-body group with a
  pixel-based x-height that does not use a sizing ratio, or calibrate the
  ratio on a held-out hand; use means or sub-pixel measurement; move the
  constant into the protected `regression_gate.py`. Re-baseline with
  approval.

[NOTE] reforge/evaluate/visual.py:597 -- After `8b876bf`, sizing and the
evaluator measure punctuated all-body words differently. Sizing crops
synthetic trailing marks (`_drop_trailing_mark_runs`); `check_x_height_
consistency` uses `compute_ink_height(img)` on the full image, so "so?",
"now!", "so," are read 20-40% oversized by the metric after being sized
correctly. Gate words have no punctuation, so the gate is unaffected; the
demo's only all-body punctuated word is "noon." (period, no extent above or
below), so demo numbers are unaffected today. It skews `overall` and the run
manifest on other text. Evaluator change, human decision. (also claude-code)
  Suggested fix (human decision): apply the same crop in the metric's
  all-body branch.

[NOTE] reforge/compose/layout.py:125 -- The ink-bottom early return is skipped
for any word containing `,` or `;` (both in `DESCENDER_CAPABLE`). A word
without descender letters then runs the strict density scan, which brings
back the crossbar misdetection the early return fixed for "it". Confirmed by
probe on the `test_it_with_crossbar_returns_ink_bottom` fixture with the real
`_attach_trailing_marks`: bare "it" -> 27 (ink bottom); "it," -> 23 against
the word's ink bottom at 36 in the composite (13 px high, at the crossbar);
"it;" -> 36, "it." -> 31, "it?" -> 32 (correct). Compose would place "it,"
raised. Already-reviewed file with no interaction with the new changes, so
NOTE under the refresh rule, but it is a real defect worth a follow-up.
(claude-code)
  Suggested fix: when the only descender-capable characters are trailing
  synthetic marks, run the early-return check on the base word (strip
  trailing marks first) and take the baseline as the base word's ink bottom.

[NOTE] reforge/quality/font_scale.py:128 -- `_drop_trailing_mark_runs`
assumes each mark yields one ink column run at `< 180`. Probe over `. , ; ! ?`,
body heights 4-44, ink 20-179, font and Bezier renderers: marks never split
into two runs and always have at least 2 white columns on the left, so the
crop boundary is robust. In 69 of 3,280 cases (font path, ink >= 170, body
height <= 13) the mark has no pixel below 180, and the crop then removes the
base word's last column run instead. Production ink medians are far darker
(postprocess blanks gray not adjacent to ink < 128), and the mark itself is
invisible in that case. Low confidence that this occurs.
  Suggested fix: none needed now; if it matters, skip the crop when the
  removed run is wider than the expected mark width.

[NOTE] reforge/quality/font_scale.py:114 -- `_TRAILING_MARKS` is a hand-copied
literal of `generator.SYNTHETIC_MARKS`, kept local to avoid importing torch.
(carried)
  Suggested fix: move `SYNTHETIC_MARKS` to `config.py` and import it in both
  modules.

[NOTE] reforge/model/generator.py:1319 -- `strip_trailing_punctuation` and
`strip_and_reattach_punctuation` (line 1448) are dead in production, still
tested, and keep the old one-mark, Bezier, raw-`compute_x_height` semantics.
(carried; also claude-code)
  Suggested fix: delete both helpers and their tests, or point the tests at
  `_attach_trailing_marks`.

[NOTE] reforge/pipeline.py:271 -- `run(seed=...)` calls `np.random.seed(seed)`,
which resets the caller's global numpy RNG; nothing in `reforge/` draws from
it. The per-word `torch.manual_seed` is also not restored. (carried; also
claude-code)
  Suggested fix: remove the numpy seed call.

[NOTE] reforge/pipeline.py:75 -- `json.dump(default=float)` writes `np.bool_`
values as 1.0/0.0 in the run manifest. (carried)
  Suggested fix: a `default` that maps numpy scalars via `.item()`.

[NOTE] tests/medium/test_quality_regression.py:113 -- The gate seeds torch
once for the whole word list and runs without TF32, where `run()` seeds per
word and sets matmul precision "high". (carried; also claude-code)
  Suggested fix: reuse `run()`'s per-word seeding and numerics scope in the
  gate, or say in the comment that generation differs.

[NOTE] tests/medium/test_quality_thresholds.py:189 -- Medium tests, experiment
harnesses and scripts still hand-wire `normalize_font_size` +
`harmonize_words` (heights=True), the legacy chain production no longer runs:
`test_quality_thresholds.py`, `test_generation.py`, `test_ocr_quality.py`,
`test_hard_words.py`, `test_duplicate_letter_hallucinations.py`,
`experiments/ab_harness.py:98`, `experiments/sweep_*.py`,
`scripts/measure_word_sizing.py`. CLAUDE.md forbids this. (carried; also
claude-code)
  Suggested fix: move OCR, hard-word, generation tests and the A/B harness
  to `postprocess_words`.

[NOTE] scripts/archive-output.sh:95 -- The archived metrics list records the
demoted `height_outlier_score` but not `x_height_consistency`, the gating
metric. (carried; also claude-code)
  Suggested fix: add `x_height_consistency` to `tracked`.

[NOTE] reforge/pipeline.py:73 -- `_write_manifest` writes `<output stem>.json`
next to any output and silently overwrites an existing file of that name.
(carried)
  Suggested fix: document it in `--output` help, or use `<stem>.manifest.json`.

[NOTE] tests/quick/test_run_manifest.py:36 -- `test_cli_accepts_seed` assigns
`sys.argv` directly (the `monkeypatch` fixture is unused) and loads
`reforge.py` by a cwd-relative path. (carried; also claude-code)
  Suggested fix: `monkeypatch.setattr(sys, "argv", [...])` and resolve
  `reforge.py` from `__file__`.

[NOTE] reforge/compose/render.py:141 -- With the 20% clamp removed, per-word
y offsets are bounded only by baseline-row differences within a line, while
lines advance by max canvas height plus 12px; the `min_top` shift covers line
0 only. A word with an unusual baseline row could intrude into an adjacent
line. Not reproduced. (carried; also claude-code)
  Suggested fix: a two-line compose test with extreme baseline rows.

[NOTE] reforge/quality/font_scale.py:259 -- `_reinforce_thin_strokes` still
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
without `cwd=PROJECT_ROOT` and duplicates `pipeline._git_state()`. (carried)
  Suggested fix: use `pipeline._git_state()["dirty"]`.

Security NOTEs (from /security, 0 BLOCK / 0 WARN / 5 NOTE, all carried; the
scan of the 5 changed paths found nothing new):

[NOTE] reforge/evaluate/visual.py:567 -- `ALL_BODY_INK_PER_X_HEIGHT` half-sets
the only gating metric but has no ask rule (see the WARN above).

[NOTE] .claude/settings.json:4 -- Evaluator ask rules are bypassable via
interpreter writes and do not cover most gate-defining files.

[NOTE] tests/medium/test_quality_regression.py:248 -- The push gate fails
open on a missing baseline/reference or hidden CUDA.

[NOTE] reforge/model/generator.py:1170 -- User words that fail OCR are
recorded in the tracked `reforge/data/hard_words.json`.

[NOTE] .claude/settings.local.json:56 -- Personal permissions file is tracked
in the public repo (outside this diff).

### Fixes Applied

None. `/codefix` applied the suggested `zone_class` change for the `f` WARN,
it failed the regression gate on seed 137, and it was reverted without
re-baselining. The working tree's code matches the review start (verified:
no surface files changed since the pre-fix snapshot), so no post-fix
security re-check was needed.

### Accepted Risks

None.

---
*Prior review (2026-10-13, commit d43de13): full review of the audit work
(18 commits); 1 WARN fixed (punctuated all-body words undersized by tall
trailing marks, fixed as `8b876bf`), 1 WARN open for human decision
(x_height_consistency), 18 NOTEs, 0 BLOCK.*

<!-- REVIEW_META: {"date":"2026-10-13","commit":"9630e08","reviewed_up_to":"9630e0810cc045e4531c19cd469130eb7f3bbcee","base":"origin/main","tier":"refresh","block":0,"warn":2,"note":21} -->
