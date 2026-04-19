## Spec -- 2026-04-19 -- Contraction right-side sizing + Caveat thickness

**Goal:** Close the two residual composition-quality defects holding the human-preference target at 3/5: (a) the right-side chunk of contractions (`'t`, `'s`, `'d`) renders with visibly lighter ink weight, thinner stroke, and smaller glyph than the left-side neighbor, plainly visible on `can't` in `docs/output-history/20260419-161539.png`; (b) the trailing-mark dilation target shipped in commit `2005408` landed at 1.0× Bezier but human review still reads `;`, `?`, `!` as "a bit small". Both are polish defects blocking composition 3/5 → 4/5. Lock in durable coverage (regression tests, visual inspection) so neither recurs.

### Acceptance Criteria

- [x] 1. Medium-tier regression test generates each of `can't`, `don't`, `it's`, `they'd` at seeds 42/137/2718 and asserts, per seed and per word: right-chunk median stroke width >= 0.85 × left-chunk median stroke width; right-chunk median ink intensity within ±20% of left-chunk's; right-chunk x-height within ±15% of left-chunk's. The test must fail against today's tree (don't scored OCR 0.125 in the most recent `make test-hard`, confirming the right-chunk collapse) and pass after the fix.
- [x] 2. Unit test in `tests/quick/test_font_glyph.py` asserts `render_trailing_mark` median stroke width >= 1.15 × `make_synthetic_mark` median stroke width for each of `. , ; ! ?` at body_heights {18, 24, 32}. The dilation target is explicitly lifted from 1.0× to 1.15× Bezier.
- [x] 3. `make test-quick` passes.
- [x] 4. `make test-regression` passes on seeds 42/137/2718: primary CV gates (`height_outlier_score >= 0.90`, `ocr_min >= 0.30`) hold on every seed.
- [x] 5. `make test-hard` passes: curated hard-words average OCR remains >= 0.5 AND each of `can't`, `don't`, `it's`, `they'd` scores individual OCR >= 0.5 on seed 42 (the seed the ledger records). The current ledger shows `don't` at 0.125, which is the specific defect this criterion pins.
- [~] 6. Human review via `make test-human EVAL=composition,punctuation,hard_words,baseline`: composition rating >= 4/5 (up from the current 3/5 floor), punctuation rating >= 4/5 (up from the current 3/5 floor), baseline rating >= 4/5 (no regression from Review 11's 4/5), hard_words rating >= 2/5 (no regression from Review 6's 2/5). Freeform notes on no seed cite: the right-side of a contraction (`'t`, `'s`, `'d`) as "thin", "small", "light", or "invisible"; nor trailing `.`, `,`, `;`, `!`, `?` as "too small", "too low", or "a bit small". **PARTIAL (Review 12, `2026-04-19_173130`):** baseline 4/5 (held), hard_words 2/5 (held), composition **3/5** (rating target missed, aspirational), punctuation **3/5** (rating target missed, aspirational). Freeform notes clean: "punctuation is improved"; "every word + punctuation improved over prior runs"; no forbidden phrases. Automated evidence independently confirms the improvement: test-hard avg 0.766 → 0.827 with all four common contractions at OCR 1.000 on seed 42 (was `don't` 0.125 CRITICAL). Accepted as partial per user decision 2026-04-19: sub-defects named in the criterion are closed, the ratings-bar was ambitious given the composition plateau has sat at 3/5 for multiple reviews. Rating target carried forward as an open quality goal, not a blocker.

### Context

**Prior-turn carryover (for the coding agent, do not re-derive from git):**

- Spec 2026-04-19 "Short-word baseline alignment at composition" shipped today (uncommitted; 4 tracked files: `SPEC.md`, `reforge/compose/layout.py`, `reviews/human/FINDINGS.md`, `tests/quick/test_baseline.py`). Baseline rating 3/5 → 4/5 (Review 11, `reviews/human/2026-04-19_154926.json`). Composition held at 3/5. Commit hygiene step before starting this spec: bundle the baseline fix into a commit so this spec's diff is clean.
- Spec 2026-04-19 "Caveat glyph dilate + baseline alignment" shipped in commit `2005408` (bundled with Option W). Caveat dilation targets `body_height * 0.12` (the Bezier baseline) via `_dilate_to_stroke_width` in `reforge/model/font_glyph.py`. Review 6 (`reviews/human/2026-04-19_021632.json`) flagged "apostrophes look better" but `"; ? and ! are all a bit small"`; this spec lifts the target from 1.0× to 1.15× Bezier.
- Spec 2026-04-18 Option W shipped the `(can, 't)` contraction split in commit `2005408`. FINDINGS Review 9 captured the follow-up defect (`'t` "has very light ink width vs 'can'"). Demo 2026-04-19_161539 shows it plainly.
- BACKLOG entries this spec addresses: `S — Contraction right-side sizing (apostrophe+t thin ink)` (added 2026-04-19). The Caveat "a bit small" work is a FINDINGS Review 6 follow-up, not a BACKLOG entry.

**Suspect-list for the can't / right-chunk fix (diagnose first, don't fix all three blind):**

- IAM `MIN_WORD_CHARS=4` training filter never saw 2-char inputs; DP renders `'t` / `'s` / `'d` with thin, uncertain strokes because it's out of distribution. Candidate fix: pad the right-chunk input with an invisible filler character to clear the filter, then tight-crop the generated image.
- Post-generation `harmonize_words` stroke-shift + height harmonization applies uniformly across all words; may not correct enough on a chunk that is both too thin AND too short. Candidate fix: extend `harmonize_words` to scale right-chunks more aggressively when `len(chunk_text) <= 2`, or run a second harmonization pass with tighter thresholds for short chunks.
- `stitch_contraction` concatenates left + right images without any per-side matching. Candidate fix: measure left stroke / x-height, scale right image to match before concatenation.

Instrument a quick diagnostic before implementing: generate the four common contractions, dump left vs right stroke width + x-height + ink intensity per chunk. Pick the fix that the diagnostic points at. Do not bundle multiple candidate fixes into the same spec.

**Caveat thickness lift (mechanical):**

`_dilate_to_stroke_width(gray_img, target_px, max_iter=4)` in `font_glyph.py` caps at 4 iterations and uses `target_px = body_height * BEZIER_STROKE_FRACTION` (= 0.12). Either raise `BEZIER_STROKE_FRACTION` to ≈ 0.138 (1.15× of 0.12) or introduce a separate `TRAILING_MARK_STROKE_MULTIPLIER = 1.15`. Re-measure `test_font_glyph.py::TestDilateToBezierBaseline` — it currently asserts `>= 1.0×`; criterion 2 tightens the assertion to `>= 1.15×`.

**Pre-existing safety net to trust:**

- `generate_word` OCR rejection + retry loop applies to both left and right chunks; words failing after retries go to `hard_words.json` candidates.
- `harmonize_words` cross-word stroke-shift pass already runs post-generation.

**Failure protocol:**

- Criterion 4 or 5 fails: revert. Regression gates are load-bearing.
- Criterion 6 fails: revert; append entries to FINDINGS.md under Apostrophe-rendering (for the contraction half) and/or Trailing-punctuation (for the Caveat half); propose next direction.
- Two-consecutive-fix rule: if this spec regresses, do not stack a second attempt in the same spec. Revert and propose.

**Out of scope (tracked in BACKLOG.md or FINDINGS.md, do not bundle):**

- img2img pipeline, retraining, style-matching font marks to writer.
- QUALITY_WEIGHTS reweighting (blocked on candidate-eval human-pick join key).
- Widening last-5 composition rating window (methodology tweak).
- Plateaued single-char sizing (design-level non-goal).

**zat.env practices carried in:**

- Smallest change that addresses the root cause. Diagnose before fixing; pick one path, not all three.
- Update tests in the same increment as the code change.
- Two-consecutive-fix rule (see failure protocol).
- Do not push to the remote unless explicitly asked.

---
*Prior spec (2026-04-19, Short-word baseline alignment): SHIPPED 6/6 criteria. `detect_baseline` fixed for short non-descender words via a per-word relative drop threshold + `r-1` fallback; baseline eval 3/5 → 4/5, composition held at 3/5. Change is uncommitted pending this spec's close.*

<!-- SPEC_META: {"date":"2026-04-19","title":"Contraction right-side sizing + Caveat thickness","criteria_total":6,"criteria_met":5} -->
