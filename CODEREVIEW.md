## Review -- 2026-04-14 (commit: 1fc02ad)

**Summary:** Refresh review of uncommitted changes implementing spec 2026-04-13 (punctuation defense and eval test fixes). Focus set: 7 code files (+497/-60 lines). Three features: (1) contraction splitting in `generator.py` (bypasses DiffusionPen for apostrophes via synthetic glyph + stitching, 4 new functions + `_generate_contraction` helper, ~170 new lines), (2) character-aware baseline detection in `layout.py` (descender letter set raises body threshold from 35% to 25%), (3) eval redesigns in `human_eval.py` (sizing: multi-char primary + Plateaued secondary, stitch: height-normalized chunks with annotations). New test file `test_contraction.py` (17 tests) and expanded `test_baseline.py` (5 descender tests) and `test_hard_words.py` (punctuation OCR test). Quick tests: 231/231 pass. Security: no issues (9 files scanned).

**External reviewers:**
None configured.

### Findings

[NOTE] reforge/model/generator.py:822 -- Unused import: `compute_ink_height` is imported alongside `compute_x_height` in `_generate_contraction`, but only `compute_x_height` is used (line 867). Dead import.
  Evidence: `from reforge.quality.ink_metrics import compute_ink_height, compute_x_height` -- no reference to `compute_ink_height` anywhere else in the function.
  Suggested fix: Remove `compute_ink_height` from the import.

[NOTE] tests/quick/test_baseline.py:74-82 -- `test_fences_baseline_with_word` docstring claims to test "f has a tail" via the new descender-aware code path, but "fences" contains no letters in `DESCENDER_LETTERS` (g, j, p, q, y), so the default (non-descender) path runs. The test passes correctly (the default scanner handles the synthetic image), but it does not exercise the B1 character-aware feature for f-tailed words. The other 3 descender tests (gray, jumping, quickly) do exercise the new code path. Not a correctness issue; the spec (B2) requires 4 descender test words, and 3 of 4 test the new feature while 1 tests the existing behavior. The docstring is misleading about which code path is exercised.
  Evidence: `DESCENDER_LETTERS = set("gjpqy")` -- 'f' is not included.
  Suggested fix: Either add 'f' to DESCENDER_LETTERS if f-tail detection is desired, or update the docstring to clarify this tests the default path behavior on an f-tail word.

### Fixes Applied

None.

### Accepted Risks

None.

---
*Prior review (2026-04-13, commit 525e903): Full review of 3 unpushed commits implementing convergence discipline, multi-seed baseline migration, primary-metric gating, and documentation updates. No issues found.*

<!-- REVIEW_META: {"date":"2026-04-14","commit":"1fc02ad","reviewed_up_to":"1fc02ad95d6bdd818b795f089a26fd01f128c7ef","base":"origin/main","tier":"refresh","block":0,"warn":0,"note":2} -->
