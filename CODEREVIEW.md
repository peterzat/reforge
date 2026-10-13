## Review -- 2026-10-13 (commit: 90302fe)

**Review scope:** Refresh review. Focus: 32 file(s) changed since prior review
(commit 9630e08), i.e. all six unpushed commits (8fc2f82..90302fe). 1
already-reviewed file (`.claude/settings.local.json`, uncommitted) checked for
interactions only.

**Summary:** Six commits: zone-sizing class changes ("f" descender, "i" dot
weak ascender), trailing-mark cropping and a body-band cross-check in
`detect_baseline`, a pixel-only sub-pixel `x_height_consistency` with an
approved re-baseline, an opt-in VLM OCR backend, two placement diagnostics,
offline-first TrOCR loading, replay and benchmark tooling, and docs plus a
demo output refresh. Tests at review start: `make test-quick` 345 passed,
`make test-regression` 347 passed. After one fix cycle: 346 and 348 passed
(one new quick test). Three WARNs were fixed (uncommitted); one WARN stays
open for a human decision. A GPU probe (origin/main vs HEAD detector, seeds
42/137/2718) backs the open WARN.

**External reviewers:**
None configured.

**Built-in review:**
`/code-review high`: 10 findings, 10 kept after Step 6 (7 merged with Claude
or /security findings).

### Findings

[WARN, FIXED] reforge/evaluate/ocr.py:50 -- `REFORGE_OCR_BACKEND=vlm` also
switched production generation (best-of-N selection and the OCR retry loop
via `generator._get_ocr_fn()`), the configuration the experiment log recorded
as falsified. (also claude-code; related /security NOTE on the push gate)
  Fixed: `ocr_read` / `ocr_accuracy` take an optional `backend`;
  `_get_ocr_fn()` pins `backend="trocr"`; new quick test
  `test_generation_ocr_ignores_vlm_backend_env`. Evaluation callers still
  follow the env var (see the post-fix NOTE on `pipeline.py:324`).

[WARN, FIXED] CLAUDE.md:26 -- The gate description said "baseline 0.954 on all
seeds"; 8fc2f82 re-baselined to 0.978 / 0.957 / 0.941. (also claude-code)
  Fixed: per-seed baselines and the reason stated in that sentence only.

[WARN, FIXED] reforge/evaluate/visual.py:126 -- `check_baseline_consistency`
reuses compose's `detect_baseline` on the same crops, so it measures only
placement arithmetic (on real pages, the +/-1px compose jitter) and is blind
to detection errors, while `docs/cv-instruments.md` presented it as the
baseline placement instrument. (also claude-code)
  Fixed (documentation only): the docstring and the cv-instruments row state
  the limitation and point to the golden test and contact sheets for
  detection errors. The metric's computation is unchanged.

[WARN, OPEN: human decision, DO NOT AUTO-FIX] reforge/compose/layout.py:228 --
The body-band cross-check is trusted whenever it disagrees with the scan,
including its documented failure (the band ends high on a thin round bottom
under a dense f crossbar). The original synthetic "for" fixture now fails and
was replaced in the same commit. (also claude-code)
  Evidence: the pre-change fixture of
  `test_for_lower_body_rows_below_absolute_threshold` (f stem, dense
  crossbar, thin o bottom) returns 14 on HEAD vs 20 on origin/main; the test
  expects 20 +/- 1. 8fc2f82 replaced that fixture with a measured density
  profile that passes, without mention in the commit message (global
  CLAUDE.md: do not modify tests to accommodate a regression). GPU probe
  (hw-sample, PRESET_FAST, seeds 42/137/2718, origin/main vs HEAD detector):
  at raw 64px scale, which `_attach_mark_to_word` (generator.py:1407) and
  `stitch_contraction` (generator.py:506) use, the band puts the baseline
  mid-"o" for 2718 "for" (46 -> 36) and "off" (44 -> 34); rendered marks are
  visibly raised on 2 of 15 f-word cases ("for." seed 137, "of," seed 2718).
  The same probe shows the change is a clear net gain elsewhere:
  descender-word marks ("gym.", "pay,") moved from the descender tip to the
  baseline on 6 of 6 cases, and at zone-sized scale (compose placement)
  every differing word (gym, jog, pay, say, away, up, going, off, for) was
  correct on HEAD and wrong on origin/main. The golden fixture covers sized
  crops only. Not auto-fixed: reverting would bring back the 16/30
  short-word failures, and a better heuristic needs contact-sheet validation
  at both scales.
  Suggested fix (human decision): keep the cross-check but make the band
  robust to a crossbar-dominated peak (for example, take the peak from the
  lower half of the ink, or do not let the band override the scan's
  walk-back row when the only descender-capable letter is "f"); restore the
  original synthetic "for" fixture as an additional test rather than a
  replacement; add raw-scale f-word and mark cases to the golden fixture.

[NOTE] reforge/pipeline.py:324 -- Post-fix: the end-of-run scoring in
`pipeline.run()` still follows `REFORGE_OCR_BACKEND` (by design for
evaluation callers). With the variable exported and no server, `vlm.ask`
raises `URLError` after the PNG is saved and before the run manifest is
written, and the manifest never records which reader produced its OCR
metrics. (/security post-fix)
  Suggested fix: record the OCR backend in the manifest, and have
  `_compute_ocr_scores` return None (OCR unavailable) on `URLError`.

[NOTE] reforge/quality/ink_metrics.py:65 -- `drop_trailing_mark_runs` now
drives compose placement (`detect_baseline`) and the gate metric, not only the
sizing estimate. If a mark merges with the last letter after the
down-resample, the crop removes a real letter's column run. (also
claude-code; carried low-ink NOTE)
  Evidence: on the 12 real zone-sized punctuated crops in
  `tests/quick/fixtures/descender_baselines.npz` the crop removed 5-9 px
  (the mark) every time and the baseline matched the label; no merge was
  observed. Separately, `detect_baseline` recurses with
  `word.rstrip(TRAILING_MARKS)` while the crop counts marks on
  `word.strip()`, so a word with trailing whitespace is cropped repeatedly;
  pipeline words never carry whitespace. The prior low-ink case (69 of
  3,280 synthetic cases, mark has no pixel below 180) still applies.
  Suggested fix: skip the crop when the removed run is wider than a mark
  could be (about 0.5 x-height); recurse with `word.strip().rstrip(...)`.

[NOTE] experiments/replay_cache.py:77 -- `generate` does not set
`torch.set_float32_matmul_precision("high")` (or `np.random.seed`) as
`pipeline.run` does, so a cache is not pixel-identical to `reforge.py --seed`
despite "Seeding matches pipeline.run". It also duplicates ~40 lines of
`run()` setup. Both A/B arms read the same cache, so A/B validity is
unaffected. (also claude-code)
  Suggested fix: set TF32 in `generate`, or factor `run()`'s model/style
  setup into a helper both use.

[NOTE] reforge/evaluate/visual.py:181 -- `check_word_gap_ratio` hard-codes
compose's 2px right pad; when a word's ink is within 2px of its canvas edge
the gap is overstated by up to 2px. `_placed_word_crops` already knows the
exact last ink column. (also claude-code)
  Suggested fix: return the right padding from `_placed_word_crops` as it
  does the left.

[NOTE] reforge/evaluate/visual.py:688 -- `check_x_height_consistency` selects
its all-body group with `font_scale.zone_class`, the sizing policy's
classifier (changed in this push), while the docstring says "Nothing here is
shared with the sizing policy". A future `zone_class` change silently changes
which words the gate measures. Gate words ("was", "so", "on") are unaffected
today. Evaluator change, human decision. (claude-code)
  Suggested fix (human decision): a local letter-set classifier in the
  evaluator, or correct the docstring.

[NOTE] 8fc2f82 -- One commit bundles zone-sizing class changes, the baseline
detector change and the gate-metric replacement with a single re-baseline, so
no gate run shows the "f" sizing change (which failed the old gate on seed
137) under a stable metric. All three were user-approved follow-ups (audit
round 2); noted for attribution, no history rewrite proposed.

[NOTE] reforge/quality/ink_metrics.py:62 -- `TRAILING_MARKS` is a hand-copied
literal of `generator.SYNTHETIC_MARKS` (moved here from font_scale.py).
(carried)
  Suggested fix: move `SYNTHETIC_MARKS` to `config.py` and import it in both.

[NOTE] reforge/model/generator.py:1325 -- `strip_trailing_punctuation` and
`strip_and_reattach_punctuation` are dead in production, still tested.
(carried)

[NOTE] reforge/pipeline.py:271 -- `run(seed=...)` calls `np.random.seed(seed)`,
resetting the caller's global numpy RNG; nothing in `reforge/` draws from it.
(carried)

[NOTE] reforge/pipeline.py:75 -- `json.dump(default=float)` writes `np.bool_`
as 1.0/0.0 in the run manifest. (carried)

[NOTE] tests/medium/test_quality_regression.py:113 -- The gate seeds torch once
for the whole word list and runs without TF32, unlike `run()`. (carried)

[NOTE] tests/medium/test_quality_thresholds.py:189 -- Medium tests, the A/B
harness and sweeps still hand-wire `normalize_font_size` + `harmonize_words`
instead of `postprocess_words`. (carried)

[NOTE] scripts/archive-output.sh:95 -- The archived metrics list records
`height_outlier_score` but not the gating `x_height_consistency` (the new
OUTPUT_HISTORY entry shows this). (carried)

[NOTE] reforge/pipeline.py:59 -- `_write_manifest` silently overwrites
`<output stem>.json`. (carried)

[NOTE] tests/quick/test_run_manifest.py:36 -- `test_cli_accepts_seed` assigns
`sys.argv` directly and loads `reforge.py` by a cwd-relative path. (carried)

[NOTE] reforge/compose/render.py:141 -- Per-word y offsets are bounded only by
baseline-row differences; a word with an unusual baseline row could intrude
into an adjacent line. Not reproduced. (carried)

[NOTE] reforge/quality/font_scale.py:63 -- `_reinforce_thin_strokes` applies
only to single-character words while zone sizing shrinks short all-body
words to ~0.2x. (carried)

[NOTE] reforge/model/generator.py:1338 -- `split_trailing_marks` returns a
mark-only token ("...", "?!") unsplit, so DiffusionPen renders it invisibly.
(carried)

[NOTE] scripts/human_eval.py:927 -- `_worktree_dirty` runs `git status`
without `cwd=PROJECT_ROOT`. (carried)

Security NOTEs (from /security, 0 BLOCK / 0 WARN / 7 NOTE; post-fix re-check
found nothing new):

[NOTE] experiments/replay_cache.py:103, experiments/cv_bench/canaries.py:45 --
Caches load with `allow_pickle=True`; a crafted `.npz` runs code. Store the
word list as JSON text instead. Local caches only today.

[NOTE] experiments/cv_bench/canaries.py:126 -- `key.json` is written next to
the pair images the blind judge reads, contrary to the docstring ("kept apart
from the judge").

[NOTE] reforge/evaluate/visual.py:650 -- The new gate constants
(`BODY_BAND_FRAC`, `LONG_BAND_FRAC`, `BODY_BAND_CALIBRATION`) have no ask
rule and are not listed in CLAUDE.md:102; changing `BODY_BAND_FRAC` to 0.45
flips the gate while all quick tests pass.

[NOTE] tests/medium/test_quality_regression.py:249 -- The push gate fails open
on a missing baseline/reference, hidden CUDA or an unreadable reference
image, and inherits `REFORGE_OCR_BACKEND` (with a running VLM server the OCR
floor is scored by the VLM). Pinning the gate's reader is a human decision.

[NOTE] .claude/settings.local.json:56 -- Personal permissions file tracked in
the public repo; the uncommitted line-75 rule adds nothing beyond line 42's
`Bash(.venv/bin/python:*)` but would be published if committed. (also
claude-code)

[NOTE] .claude/settings.json:4 -- Evaluator ask rules are narrow. (carried)

[NOTE] reforge/model/generator.py:1239 -- User words that fail OCR are recorded
in the tracked `reforge/data/hard_words.json`.

Resolved since the prior review: the "f" sizing WARN (`_DESCENDERS` now
includes "f", re-baseline approved), the `x_height_consistency` WARN
(pixel-only, sub-pixel, means), the punctuated all-body metric NOTE, and the
"it," baseline NOTE.

### Fixes Applied

All uncommitted in the working tree; commit them before pushing.

- [WARN] reforge/evaluate/ocr.py:32, reforge/model/generator.py:1179 --
  optional `backend` on `ocr_read` / `ocr_accuracy`; generation's
  `_get_ocr_fn()` pins TrOCR; quick test
  `tests/quick/test_vlm_client.py::test_generation_ocr_ignores_vlm_backend_env`.
  (also claude-code)
- [WARN] CLAUDE.md:26 -- gate baselines updated to 0.978 / 0.957 / 0.941.
  (also claude-code)
- [WARN] reforge/evaluate/visual.py:126, docs/cv-instruments.md:17 --
  `baseline_consistency` limitation documented. (also claude-code)

Post-fix: `make test-quick` 346 passed, `make test-regression` 348 passed;
/security post-fix re-check found nothing new.

### Accepted Risks

None.

---
*Prior review (2026-10-13, commit 9630e08): refresh review of the trailing-mark
sizing crop; 0 BLOCK, 2 WARN open (short "f" words undersized; the gate metric
blind to all-body mis-sizing), 21 NOTEs; one fix attempt reverted after
failing the gate.*

<!-- REVIEW_META: {"date":"2026-10-13","commit":"90302fe","reviewed_up_to":"90302fe7cffcede172ef1af386e55a0ddde6f433","base":"origin/main","tier":"refresh","block":0,"warn":4,"note":26} -->
