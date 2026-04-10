## Review -- 2026-04-10 (commit: 7a19459)

**Summary:** Refresh review of 17 unpushed commits implementing SPEC criteria A1-A5 (height-aware candidate selection), B1-B4 (human eval data collection), and C1-C2 (prior spec cleanup). Also reviews prior-spec work from commits b8e92d9 (stroke width scoring), e4ab619 (blended stroke width harmonization), 4436dcd (median baseline normalization), 987329b (unified font height target), 3bfe444 (revert cap-height normalization), 68acd5f (height-aware scoring), and 7a19459 (demo refresh). The .claude/settings.local.json unstaged change is out of scope.

**Review scope:** Refresh review. Focus: 25 file(s) changed since prior review (commit 844e31b). 0 already-reviewed file(s) checked for interactions only. Security review (paths scope, 6 files) completed and found no issues.

**External reviewers:**
[openai] o3 (high) -- 19787 in / 15099 out / 14912 reasoning -- ~$0.2796
[qwen] Qwen/Qwen2.5-Coder-14B-Instruct-AWQ -- 21157 in / 5 out -- 49s
All 4 external findings were false positives or pre-existing issues out of scope. Details:
- openai pipeline.py:148 "np not imported" -- false positive, line 7 imports `numpy as np`.
- openai generator.py:570 "_get_ocr_fn called twice wastes memory" -- false positive, `_load_trocr` uses `@functools.lru_cache`.
- openai generator.py:654 "multi-chunk skips rejection loop" -- correct observation but pre-existing in prior commit 844e31b (carried forward as NOTE #5 below).
- openai render.py:145 "baselines mutated during iteration" -- false positive, mutation is key-value replacement within a stable list iteration; median is pre-computed so clamping is order-independent.

### Findings

1. [WARN] reforge/quality/score.py:110-127 and reforge/pipeline.py:147-149 -- Stroke width reference is computed on raw style images whose scale is 3-4x larger than the 64px DiffusionPen canvas, causing `_stroke_width_score` to return 0.0 for essentially every generated candidate. **Partially fixed.**

   Evidence: `styles/hw-sample.png` is 1057x1607. Segmented style words have heights 118-186px. `compute_mean_stroke_width` on these returns ~9.7px (median, verified against real pipeline). DiffusionPen generates at 64x256 with 2-4px ink strokes; a synthetic 3px stroke at 64 rows measures 2.66 via distance transform. In `_stroke_width_score`, `deviation = |2.66 - 9.7| / 9.7 = 0.726`, exceeding the 0.5 falloff cap, so the score clamps to 0.0. Every candidate gets a stroke width score of 0, reducing quality_score from `total * 1.0` to `total * 0.8` uniformly. Ranking is preserved, so regression tests do not catch this.

   **Fix applied:** pipeline.py now resizes each style word to 64px canvas height before measuring stroke width. This addresses the stated scale mismatch in the code.

   **Residual issue (not fixed, consider follow-up):** For the default `hw-sample.png` style, the resized reference is still ~9.68 (essentially identical to the raw 9.70) because the segmentation of that image produces two near-fully-black crops (99% ink ratio, stroke widths of 34.67 and inf) that dominate the median alongside a genuinely thick word (9.68). Even if the junk segmentations were filtered out, the real words' scaled stroke widths (~5px) would still produce a reference too far from DiffusionPen's 2-4px typical output to score > 0. Recommend considering a scale-and-thickness-invariant metric (e.g., stroke_width / ink_height ratio) or widening the falloff range. Tracked for future spec.

2. [WARN] reforge/config.py:48 -- Stale comment on `SHORT_WORD_HEIGHT_TARGET`. Comment read "pixels, for 1-3 char words", but commit 987329b moved the threshold to `<= 2` (1-2 char words) in both `font_scale.py:28` and `score.py:75`. **Fixed.** Comment updated to "1-2 char words".

3. [WARN] tests/medium/test_descender_diagnostic.py:11,14 -- Two dead imports (`import torch` and `from reforge.config import DEFAULT_CANVAS_HEIGHT`). **Fixed.** Both removed.

4. [NOTE] reforge/model/generator.py:586-628 -- OCR rejection retry loop re-computes OCR on the selected image at iteration 1 when `num_candidates=1`, even if iteration 0 already computed it for the same image. `first_check_done` is set once and never flipped inside the loop. Wastes one TrOCR call per retry iteration on hard words only. Not a correctness bug.

5. [NOTE] reforge/model/generator.py:631 -- Multi-chunk words call OCR for every candidate in `_generate_chunk` (via `ocr_fn` wired at line 519), but the OCR rejection loop is only invoked in the `len(chunks) == 1` branch. The per-candidate OCR scoring is still useful (it selects a readable chunk), so the per-candidate call is not wasted. The absence of multi-chunk rejection retry is pre-existing (identical branch structure in commit 844e31b). External reviewer (openai) flagged this.

6. [NOTE] tests/medium/test_descender_diagnostic.py:115 -- Diagnostic test uses `assert True`; findings are only visible via captured stdout. Consistent with the test's stated purpose ("diagnostic: no hard assertion, just record findings") but provides no regression protection.

### Fixes Applied

1. Resized style word images to 64px canvas height before computing reference stroke width in pipeline.py (WARN #1, partial -- addresses scale mismatch in code; runtime reference for hw-sample.png is essentially unchanged due to segmentation quality and handwriting thickness; follow-up recommended).
2. Updated `SHORT_WORD_HEIGHT_TARGET` comment from "1-3 char words" to "1-2 char words" in config.py (WARN #2).
3. Removed unused `import torch` and `DEFAULT_CANVAS_HEIGHT` imports from test_descender_diagnostic.py (WARN #3).

Post-fix verification: 179/179 quick tests pass. 180 tests collected (unchanged). No regression.

### Accepted Risks

None.

---
*Prior review (2026-04-09, commit 844e31b): Refresh review of 1 commit implementing SPEC B/C/D. 1 WARN (unused DEFAULT_GUIDANCE_SCALE import in test_parameter_optimality.py, auto-fixed) and 1 NOTE (dead guard in height tests, carried forward).*

<!-- REVIEW_META: {"date":"2026-04-10","commit":"7a19459","reviewed_up_to":"7a194593669f59518547ea7025c0da114312d001","base":"origin/main","tier":"refresh","block":0,"warn":3,"note":3} -->
