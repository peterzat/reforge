## Review -- 2026-10-13 (commit: 5b1c24a)

**Review scope:** Refresh review against `origin/main`. The prior review
(`ab25600`, light tier) is an ancestor of `origin/main`, so the focus set is
the entire unpushed diff: 14 commits, 82 files (code, tests, CLAUDE.md, docs,
40 newly tracked human review JSONs). All files reviewed at full depth.

**Summary:** Audit 2026-10-13 work: zone sizing with a single resample,
word-aware baseline detection and clampless placement, contraction stitch on
detected baselines, punctuated words routed through the full generation path,
seeded runs with a run manifest, gate switched from `height_outlier_score` to
`x_height_consistency`, CLAUDE.md split into rules plus `docs/` references.
Tests at review start: `make test-quick` 327 passed; `make test-regression`
329 passed (quick + regression gate). After the fix cycle: `make test-quick`
327 passed, `make test-regression` 329 passed (stable). One fix cycle;
post-fix /security re-check of `reforge/pipeline.py` and
`scripts/human_eval.py` found nothing new (0 BLOCK / 0 WARN / 4 NOTE overall).

**External reviewers:**
None configured.

**Built-in review:**
`/code-review high`: 10 findings, 8 kept after Step 6 (2 refuted by probe;
3 merged with Claude findings).

### Findings

[BLOCK, FIXED in working tree] README.md:1 -- README.md is corrupted: 225 lines / 16.8 KB became
37,045 lines / 14.3 MB in commit `aefea28`. (also claude-code; also flagged
by /security as a non-security issue)
  Evidence: The new "Quality regression test" paragraph plus "\n\n" (a
  778-char block) was inserted before and after every character of the
  intended README, the signature of `str.replace("", new)`. Splitting the
  file on that block yields 18,407 single-character fragments whose
  concatenation is the intended pre-replace README (18,406 chars). That text
  still contains the old regression paragraph (line 191) and all the other
  intended edits from `aefea28` (section 6 "Sizing and harmonization",
  baseline bullets, "Metrics, and their limits", test-tier table).
  Suggested fix (deterministic recovery, verified):
  ```python
  cur = open("README.md").read()
  S = cur[:cur.index("#**Quality")]       # inserted block: new paragraph + "\n\n"
  rec = "".join(cur.split(S))              # intended README before the bad replace
  old_para = next(l for l in rec.splitlines()
                  if l.startswith("**Quality regression test**"))
  fixed = rec.replace(old_para, S.rstrip("\n"), 1)
  open("README.md", "w").write(fixed)
  ```
  Then check: about 18.4 KB, exactly one "**Quality regression test**" line
  (the new text: "Generates the five style words plus short words..."), and
  `git diff aefea28~1 -- README.md` shows only the intended section edits.
  History note for the user: a fix committed on top still pushes the 14 MB
  blob in `aefea28`. To keep it out of public history, fold the fix into
  `aefea28` (fixup + autosquash rebase onto `origin/main`) before pushing.
  That is a history rewrite of local commits and is left to the user.

[WARN, OPEN: human decision] reforge/evaluate/visual.py:589 -- The gating metric
`x_height_consistency` cannot detect the defect it gates for all-body words.
DO NOT AUTO-FIX: changing the gating metric or its baseline requires explicit
human approval (CLAUDE.md "The evaluator is the human's").
  Evidence: zone sizing scales an all-body word so `ink_h / ZONE_HEIGHT_RATIOS[(0, 0)]`
  equals `ZONE_X_HEIGHT_TARGET` (3-letter words get blend weight 0, so the
  estimate is the prior alone; `font_scale.py:124-129`). The metric then
  measures those words as `ink_h / ZONE_HEIGHT_RATIOS[(0, 0)]`
  (`visual.py:589`), the same constant, so the numerator is fixed by
  construction. Probes with the real functions:
  - Raw all-body words 18px, 30px and 45px tall (a 2.5x spread, which is the
    `size_inconsistent` defect) all size to 15-16px ink, and the metric does
    not change.
  - Setting `ZONE_HEIGHT_RATIOS[(0, 0)] = 2.0` makes all-body words 25-26px
    against a 13px long-word x-height (about 2x, exactly the defect) and the
    metric reports 1.0000. `config.py` is not covered by the
    `.claude/settings.json` ask rules, so this edit is unprotected.
  - The metric is also quantized by integer pixel heights: the baseline is
    0.9536 on all three seeds (15/1.21/13). A 1px shift in the median
    long-word x-height (13 to 14) gives 0.885, which fails the 0.05
    tolerance; 13 to 12 gives 0.968, which passes.
  In effect the gate checks long-word `compute_x_height` against the
  target, and that a policy other than zone is not in use.
  Suggested fix (human decision): measure all-body words with an instrument
  independent of the sizing constants, for example a frozen measured ratio
  defined in `visual.py` (not imported from config), or a pixel x-height
  with a minimum-word-width guard; add a quick test that perturbing
  `ZONE_HEIGHT_RATIOS[(0, 0)]` moves the metric; consider a half-pixel
  tolerance or a larger long-word set to reduce quantization. Re-baseline
  with approval. Until then, CLAUDE.md's "measures the size_inconsistent
  defect directly" overstates what the gate can see.

[WARN, FIXED] scripts/human_eval.py:406 -- The `sizing`, `baseline`, `spacing` and
`ink_weight` human evals still hand-wire the legacy sizing chain, so human
reviewers rate a stage graph production no longer runs. (also claude-code,
which raised the same pattern in unmodified tests and experiments)
  Evidence: `_generate_words` (line 226) applies `normalize_font_size` per
  word, then each eval calls `harmonize_words(word_images)` with the default
  `heights=True` (lines 418, 441, 465, 516). That is the `total_height`
  policy with chained resamples. Production now runs
  `pipeline.postprocess_words` (zone sizing, one resample,
  `harmonize_words(heights=False)`). The `sizing` eval exists to judge
  short vs. long word size consistency, the property this push changed.
  CLAUDE.md added in this diff: "Do NOT hand-wire the sizing/harmonization
  passes in tests or evals; call `pipeline.postprocess_words`."
  Suggested fix: have these evals generate raw word images (no
  `normalize_font_size`) and call `postprocess_words(images, words)`. For
  `ink_weight`, keep the `STROKE_WEIGHT_SHIFT_STRENGTH` patch around the
  `postprocess_words` call. Leave `_generate_words` callers outside these
  four evals unchanged unless they also feed composition.

[WARN, FIXED] reforge/pipeline.py:266 -- `--seed` values outside [0, 2**32) crash
after model loading and leak the global torch numerics this change set out
to scope. (also claude-code)
  Evidence: `np.random.seed(seed)` runs after
  `torch.set_float32_matmul_precision("high")` and the cuDNN flag changes
  (lines 257-264) but before the `try:`. `np.random.seed(-1)` raises
  ValueError, so the `finally` that restores the settings never runs. The
  global numpy RNG is not used anywhere in `reforge/` (layout and render use
  their own `RandomState`), so the call only adds the crash path.
  `reforge.py` accepts any int for `--seed`. Very large seeds also overflow
  `torch.manual_seed(seed * 1_000_003 + word_idx)`.
  Suggested fix: validate the seed at the top of `run()` (before model
  loading) and reject values outside [0, 2**32); move any remaining seeding
  inside the `try`. Optionally constrain `--seed` in `reforge.py`.

[WARN, OPEN: user action] README.md (history, commit `aefea28`) -- The
working-tree README is repaired, but the 14.3 MB corrupted blob is still in
commit `aefea28`. Committing the fix on top and pushing publishes that blob
in the public repo's history permanently.
  Evidence: `git show aefea28:README.md | wc -c` is 14,339,052 bytes;
  `aefea28` is unpushed (`origin/main..HEAD`).
  Suggested fix: commit the README repair as a fixup of `aefea28`
  (`git commit --fixup=aefea28 README.md`) and autosquash-rebase onto
  `origin/main`, then push. This rewrites local, unpushed commits only.
  The push marker stays valid because the final tree is unchanged.

[NOTE] scripts/archive-output.sh:95 -- The archived metrics list records the
demoted `height_outlier_score` but not `x_height_consistency`, the gating
metric. (also claude-code)
  Suggested fix: add `x_height_consistency` to `tracked`.

[NOTE] reforge/pipeline.py:73 -- `_write_manifest` writes
`<output stem>.json` next to any output and silently overwrites an existing
file of that name (`--output config.png` replaces `config.json`). Also
raised by /security as a non-security observation.
  Suggested fix: document it in `--output` help, or use a less collision-prone
  name such as `<stem>.manifest.json`.

[NOTE] tests/quick/test_run_manifest.py:36 -- `test_cli_accepts_seed`
assigns `sys.argv` directly (the `monkeypatch` fixture is requested but not
used for it), so the value leaks to later tests, and it loads `reforge.py`
by a cwd-relative path.
  Suggested fix: `monkeypatch.setattr(sys, "argv", [...])` and resolve
  `reforge.py` from the test file's location.

[NOTE] reforge/compose/render.py:141 -- With the 20% clamp removed, per-word
y offsets are bounded only by baseline-row differences within a line, while
`compute_word_positions` advances lines by max canvas height plus 12px.
A word with an unusually low detected baseline could intrude into the
previous line's band. Not reproduced; the archived demo shows no overlap.
(claude-code, medium-low confidence)
  Suggested fix: add a test that composes a two-line page with extreme
  baseline rows and asserts no ink overlap between lines.

[NOTE] reforge/quality/font_scale.py:236 -- Zone sizing shrinks all-body
words to about 0.23x in one INTER_AREA step, but `_reinforce_thin_strokes`
still applies only to single-character words. Short words may come out
lighter and thinner; `stroke_weight_consistency` dropped from 0.91 to
0.79-0.85 in the new baseline, which is consistent with this. The human A/B
still preferred zone 3/3. (claude-code, medium confidence)
  Suggested fix: measure stroke width of zone-sized short words against
  neighbors before deciding whether to extend reinforcement.

[NOTE] reforge/model/generator.py:1341 -- `split_trailing_marks` returns a
token made only of marks ("...", "?!") unsplit, so it goes to DiffusionPen,
which renders trailing marks invisibly. The old `strip_trailing_punctuation`
path produced at least one synthetic mark for such tokens. Intentional per
the docstring and test, but the result is likely a blank word.
(claude-code, medium confidence)
  Suggested fix: render mark-only tokens synthetically at a default body
  height derived from `ZONE_X_HEIGHT_TARGET`.

[NOTE] scripts/human_eval.py:939 -- `_worktree_dirty` runs `git status`
without `cwd=PROJECT_ROOT`, unlike the script's other git calls (lines 111,
873). The script already assumes cwd is the repo root (`REVIEW_DIR` is
relative), so impact is limited. (claude-code, low confidence)
  Suggested fix: pass `cwd=PROJECT_ROOT`.

[NOTE] tests/medium/test_ab_harness.py:164 -- Unmodified medium tests
(`test_ab_harness.py`, `test_generation.py`, `test_quality_thresholds.py`)
and `experiments/sweep_*.py`, `experiments/ab_harness.py`,
`scripts/measure_word_sizing.py` still use the legacy
`normalize_font_size` + `harmonize_words` chain. Some are component tests of
`harmonize_words` and are fine; the experiment harnesses would A/B a stage
graph production no longer runs. (claude-code)
  Suggested fix: move experiment harnesses to `postprocess_words` when next
  used.

Security NOTEs (from /security, 0 BLOCK / 0 WARN / 4 NOTE):

[NOTE] .claude/settings.json:4 -- The evaluator ask rules cover only built-in
edits to `quality_baseline.json` and `regression_gate.py` plus the two
`--update-*` flags. Python writes via the allowed `.venv/bin/python` bypass
them, and `PRIMARY_METRICS`, tolerance, SSIM threshold, the word list,
`reference_output.png`, `tests/medium/conftest.py` and the metric code in
`visual.py` have no rule. (Relates to the gate WARN above:
`ZONE_HEIGHT_RATIOS` is also part of the evaluator.)

[NOTE] tests/medium/test_quality_regression.py:248 -- The push gate fails
open: a missing baseline or reference is recorded fresh and passes, and
`CUDA_VISIBLE_DEVICES= git push` skips the class with exit 0.

[NOTE] reforge/model/generator.py:1170 -- Words from user text that fail OCR
retries are appended with a timestamp to the tracked
`reforge/data/hard_words.json`; punctuated words now reach that path too.

[NOTE] .claude/settings.local.json:56 -- Personal permissions file is tracked
in the public repo (pre-existing, outside this diff).

Prior-review NOTEs: all three resolved. `layout.py` walkback now uses a
peak-relative `walkback_threshold`; `docs/output-history/20260419-161539.png`
still exists, so the `test_contraction_sizing.py:8` pointer resolves;
SECURITY.md now cites `scripts/human_eval.py:558`, which is correct.

Built-in findings refuted by probe (dropped): the claims that a trailing
`,`/`;` tail inflates ink height under zone sizing (`font_scale.py:101`) and
misplaces a following mark (`generator.py:1361`). Attaching `,` `;` and `,.`
to body words 12-60px tall left ink height unchanged in every case; the
synthetic comma does not extend below the word's ink bottom.

### Fixes Applied

- [BLOCK] README.md:1 -- Recovered the intended README with the documented
  split-and-rejoin procedure and swapped in the new regression paragraph.
  18,503 bytes, one "Quality regression test" line; `git diff aefea28~1 --
  README.md` shows only the intended edits (31+/25-).
- [WARN] reforge/pipeline.py:139 -- `run()` rejects seeds outside [0, 2**32)
  before model loading; `np.random.seed` moved inside the `try` so the
  `finally` always restores torch numerics. Verified: seeds -1, 2**32 raise
  ValueError with global settings untouched.
- [WARN] scripts/human_eval.py:226 -- `_generate_words` returns raw images;
  the sizing, baseline, spacing and ink_weight evals call
  `postprocess_words` (ink_weight keeps its strength patch around it).

### Accepted Risks

None.

---
*Prior review (2026-04-20, commit ab25600): light review of docs/image
archival; 0 BLOCK / 0 WARN / 5 NOTE (output-history docstring pointer,
bundled add/remove, baseline-derived archive metrics, SECURITY.md line
pointer, layout.py walkback threshold).*

<!-- REVIEW_META: {"date":"2026-10-13","commit":"5b1c24a","reviewed_up_to":"5b1c24a121d39d94e2e878ef9513741f5935228e","base":"origin/main","tier":"refresh","block":0,"warn":2,"note":12} -->
