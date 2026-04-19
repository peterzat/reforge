## Spec -- 2026-04-19 -- Caveat glyph dilate + baseline alignment

**Goal:** Fix the two trailing-punctuation defects flagged by human Review 9: Caveat-rendered `.`, `;`, `!`, `?` marks are visibly thinner than the surrounding DP-rendered letters, and they sit "too low" because the attach step aligns their ink bottom with the word's full ink bottom (including descenders) rather than the word baseline. Dilate the Caveat raster to match the Bezier stroke-width baseline, and change the attach step to align on the word's baseline (non-descender letter bottom).

### Acceptance Criteria

- [x] 1. `render_trailing_mark` output has a median stroke width at least equal to the Bezier baseline `body_height * 0.12` at body_heights in {18, 24, 32}.
- [x] 2. Trailing marks `.`, `;`, `!`, `?` attach to a word so the mark's ink bottom aligns with the word's baseline (non-descender letter bottom), not the word's full ink bottom. A period attached to a word containing descenders (e.g. `jump.`) sits at the baseline row of the non-descender letters, not below the descender tail.
- [x] 3. `tests/quick/test_font_glyph.py` (or an adjacent new test file) contains unit tests for both behaviors: (a) median stroke width at body_height 24 meets the Bezier baseline; (b) attaching a period to a synthetic word whose descender extends >= 6 px below the baseline places the period's ink bottom within 1 px of the baseline row, not within 1 px of the descender bottom.
- [x] 4. `make test-quick` passes.
- [x] 5. `make test-regression` passes on seeds 42/137/2718: primary CV gates (`height_outlier_score >= 0.90`, `ocr_min >= 0.30`) hold on every seed.
- [x] 6. `make test-hard` passes: average OCR on the curated hard-words set remains >= 0.5.
- [x] 7. Human review `make test-human EVAL=punctuation,composition`: punctuation rating >= 3/5 (up from Review 9's None/5), and freeform notes do not cite trailing punctuation (`.`, `;`, `!`, `?`) as "too thin", "too small", or "too low" on any seed. Composition rating does not drop below 3/5 (no regression on the contraction path shipped last turn).

### Context

**Prior-turn carryover (for the coding agent, do not re-derive from git):**

- Spec 2026-04-18 Option W shipped. Contraction handling now returns `("can", "'t")` and renders both halves via the normal DP path with no synthetic apostrophe. Composition went 2/5 → 3/5; apostrophes "look better" per human Review 9 (`reviews/human/2026-04-18_233350.json`).
- Review 9 rated `punctuation` None/5 with the note: "apostrophes look better. All other punctuation is too low and too small. make sure the bottom of punctuation aligns with the non-descender part of letters. 't' in 'can't' has very light ink width vs 'can'." The thin-ink complaint on `'t` is a W follow-up captured in FINDINGS.md Review 9, *not* in scope here; this spec addresses trailing punctuation only.
- Caveat is the live trailing-mark renderer. Rasterizer: `reforge/model/font_glyph.py:render_trailing_mark`. Dispatcher: `reforge/model/generator.py:_render_trailing_mark_or_fallback` (falls back to Bezier `make_synthetic_mark` if the font is disabled in config or missing on disk). Attach step: `_attach_mark_to_word` in the same file.

**Where to make each change.**

- *Thickness (criterion 1)*: `render_trailing_mark` rasterizes from PIL then (optionally) trims. Add a post-rasterization morphological dilation that measures the Caveat glyph's median stroke width and dilates by the difference to the Bezier target (`body_height * 0.12`). The Bezier target exists in `make_synthetic_mark` and is the comparison.
- *Alignment (criterion 2)*: `_attach_mark_to_word` currently aligns both parts by `_ink_bottom`. When the word has a descender (`j`, `g`, `p`, `q`, `y`), that bottom sits below the word baseline, so the mark follows the descender down. Fix by detecting the word's baseline (non-descender letter bottom) — `reforge/compose/layout.py` already has baseline-detection logic for the same purpose; reuse it — and aligning the mark's ink bottom against that row instead.

**Design note on the alignment fix.** For a word without descenders, ink_bottom == baseline and behavior is unchanged. For a word with descenders, baseline < ink_bottom and the mark moves up by (ink_bottom - baseline) px. The mark's own descender (for `,` and `;`) is handled separately: those still want their *visual baseline* aligned with the word baseline, so their ink then extends below. The unit test in criterion 3 (a word with >= 6 px of descender) pins this down.

**Pre-existing safety net.** The Bezier fallback (`make_synthetic_mark`) remains in place. If the dilate code path breaks or the font is missing, fallback is still Bezier. Do not delete `make_synthetic_mark`.

**Failure protocol:**

- Criterion 5 or 6 fails: revert the code change. Regression gates are load-bearing.
- Criterion 7 fails: revert; append Review 10 to the FINDINGS.md `Trailing punctuation is invisible` entry (which tracks the broader punctuation quality story); note whether the thickness or alignment sub-issue blocked and propose the next direction.
- Two-consecutive-fix rule: if this spec regresses, do not attempt an alternate dilate approach or a different alignment strategy in the same spec. Revert and propose.

**Out of scope (tracked in BACKLOG.md or FINDINGS.md, do not bundle):**

- `'t` thin-ink weight in contraction right-side (FINDINGS Review 9 W follow-up).
- Style-matching font-rendered marks to the writer's hand (BACKLOG).
- `by` descender clipping (BACKLOG; separate baseline-detection issue at composition time).
- Apostrophe rendering — contractions do not use `render_trailing_mark`; they render via the normal DP word path under Option W.
- Punctuation-visibility CV metric re-tuning.

**zat.env practices carried in:**

- Smallest change that addresses the root cause. Do not refactor the Bezier path or the `_attach_mark_to_word` API beyond what is needed for alignment.
- Update tests in the same increment as the code change.
- Two-consecutive-fix rule (see failure protocol).
- Do not push to the remote unless explicitly asked.

---
*Prior spec (2026-04-18, Option W split at `'t`): SHIPPED 8/8 criteria. Composition 3/5 (up from Option E's 2/5); `apostrophes look better` per Review 9. Follow-up on `'t` thin ink captured in FINDINGS.md, not bundled here.*

<!-- SPEC_META: {"date":"2026-04-19","title":"Caveat glyph dilate + baseline alignment","criteria_total":7,"criteria_met":7} -->
