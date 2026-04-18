## Review -- 2026-04-18 (commit: 0a5c1cf)

**Review scope:** Refresh review. Focus: 11 files (and 1 pre-existing
unstaged file on `.claude/settings.local.json`) changed since prior review
commit 278b61f. The focus set covers the Turn 2a-2d plan
`soft-shimmying-parnas` work across 8 commits: `41add16` (contraction
diagnosis script), `fe12a7b` / `7d55f9c` (full-word + overlay path,
reverted by `0a5c1cf`), `5bfeca5` (OFL Caveat font replaces Bezier for
trailing marks), `accc455` (backlog register), `c2282f1` (deterministic
multi-seed composition eval), `42379d1` (findings refresh), `fad07a2`
(prior CODEREVIEW refresh). Net code delta is Turn 2d + Turn 2e + Turn 1
(determinism) + docs; Turn 2b/2c were reverted in-place.

**Summary:** Full review of the surviving changes from plan
`soft-shimmying-parnas`. New `reforge/model/font_glyph.py` rasterizes
OFL Caveat glyphs for trailing punctuation; `_render_trailing_mark_or_fallback`
in `generator.py` wraps it with a safe fallback chain (None disables,
missing file warns, rasterization error falls back to Bezier).
`CONTRACTION_RIGHT_SIDE_WIDTH` hook unchanged. `generate_composition_eval`
in `scripts/human_eval.py` now scopes cudnn determinism and runs 3 seeds,
selecting the median-`overall` seed for display and archiving all three.
Two throwaway experiment scripts added under `experiments/`. CLAUDE.md
gained a pointer to the new `docs/BACKLOG.md` deferral register. 297 quick
tests pass (up from 287; seven new `test_font_glyph.py` cases added).

**External reviewers:**
[openai] API call failed (network error), skipping
[qwen] Qwen/Qwen2.5-Coder-14B-Instruct-AWQ -- 20313 in / 5 out -- 42s
[qwen] No issues found.

### Findings

No BLOCK or WARN findings.

Refresh-review verification notes:
- `_render_trailing_mark_or_fallback` (generator.py:349-394) uses a
  3-layer safe-fallback chain: config=None disables; relative path is
  resolved against repo root via `os.path.dirname` chain; missing-file
  and rasterization-error paths both log a warning and call
  `make_synthetic_mark`. `from reforge.config import ...` is performed
  inside the function so `monkeypatch.setattr` in tests correctly
  overrides the module attribute. Fonts directory present
  (`fonts/Caveat-VariableFont_wght.ttf` 403 KB + `fonts/OFL.txt`).
- `_generate_punctuated_word` (generator.py:1392-1466) is the sole live
  caller of the new helper (line 1458). `strip_and_reattach_punctuation`
  (line 1346) still uses `make_synthetic_mark` directly; confirmed it
  is only imported from `tests/quick/test_synthetic_marks.py`, so the
  divergence is intentional (tests pin Bezier-path behavior).
- `font_glyph.py::render_trailing_mark` handles edge cases: single-char
  input guard (raises ValueError), `body_height = max(4, ...)`,
  `ink_intensity` clamped to [0, 255], tight horizontal crop with
  padding, trailing-ascent trim that preserves descender extent for
  comma/semicolon and collapses to body-height for period/exclamation/
  question. Bbox-anchored draw coordinate math (`horizontal_padding_px
  - bbox[0]`) is correct given PIL's logical-top anchor convention.
- `generate_composition_eval` (human_eval.py:533-621) snapshots
  `torch.backends.cudnn.{benchmark,deterministic}` before the eval
  loop, flips to deterministic, and restores in a `finally` block.
  Median selection via `sorted(..., key=lambda e: e["cv_metrics"]
  .get("overall", 0.0))[len // 2]` correctly picks the middle entry
  for N=3. New `per_seed_cv` and `selected_seed` fields in the
  returned dict; downstream `save_review` handles both defensively
  with `.get()` (human_eval.py:917-921, 934-937). The `cv_metrics`
  backwards-compat field is still populated with the selected seed's
  metrics.
- `result["quality_scores"]` from `pipeline.run()` always contains an
  `"overall"` key (visual.py:707); the `.get("overall", 0.0)` default
  in the sort key is defensive but unneeded.
- `.claude/settings.local.json`: permission add-lines for font-download
  curls, one-shot `-sI` heads, and a `pkill -f qpeek` helper. All local
  to the dev machine; no secrets or shared-state changes.
- `experiments/diagnose_contraction.py` and `experiments/smoke_caveat_marks.py`:
  offline CLI drivers writing under `experiments/output/`. No shell
  invocation, no unsanitized input paths, no network. Mirror the live
  `_gen_part` canvas-width math including the `CONTRACTION_RIGHT_SIDE_WIDTH`
  override (lines 107-111 of diagnose_contraction.py); round-to-multiple-of-16
  and clamp to `[WIDTH_MULTIPLE * 4, MAX_CANVAS_WIDTH]` is equivalent to
  the live logic.
- Security scan (8 files, re-run from SECURITY_META commit 278b61f):
  0 issues. SECURITY.md refreshed to commit 0a5c1cf with `scanned_files`
  covering every non-doc file touched since the prior scan.
- 297 quick tests pass in 4.98s (up from 287; 7 new `test_font_glyph.py`
  cases plus 3 `TestFallbackHelper` cases).

### Fixes Applied

None. No BLOCK or WARN findings.

### Accepted Risks

None.

Informational observations (carried forward, not findings):
- The candidate-logging informational note from the prior review still
  applies: candidate logging is wired in the main `_generate_chunk`
  loop only, not in `_generate_contraction._gen_part` or
  `_generate_punctuated_word`. Spec D1 targets the singular best-of-N
  path and the `EVAL=candidate` fixture uses a non-contraction word,
  so the documented join key is covered.
- `strip_and_reattach_punctuation` (generator.py:1346) is a test-only
  helper that still uses the Bezier `make_synthetic_mark` directly.
  Intentional: the tests that import it pin Bezier behavior. Keeping
  the divergence is fine unless a future spec retires the Bezier path
  entirely, at which point both this helper and its tests should be
  updated together.

---
*Prior review (2026-04-17, commit 278b61f): Refresh review with no code
changes since the 3a710b3 + uncommitted state. 0 BLOCK / 0 WARN / 0 NOTE.
Security scan of two new experiment drivers: 0 issues.*

<!-- REVIEW_META: {"date":"2026-04-18","commit":"0a5c1cf","reviewed_up_to":"0a5c1cfa0421992c911e95ea8a55a29522d93749","base":"origin/main","tier":"refresh","block":0,"warn":0,"note":0} -->
