# Backlog

Running register of considered proposals that were deferred, explicitly scoped
out, or rejected. The `/spec` skill truncates the prior `SPEC.md` body to a
one-line summary on every turn close, so anything not re-entered into the next
spec gets lost. This file is the durable home.

**Read this before drafting a new `SPEC.md`** or setting an Out-of-scope section.
Any entry still worth tracking should carry forward (with updated revisit
criteria); any that shipped should be moved to the relevant commit or finding.

## How entries are structured

```
### <short name>
- **One-line description** of the proposal.
- **Why deferred:** reason.
- **Revisit criteria:** what would make this worth picking up again.
- **Origin:** spec date or plan slug where it was first considered.
```

## Rejected by user, unlikely to revisit

### Case-3 font fallback for contraction right-side letters
- Substitute a real-font glyph for `'t` / `'s` / `'d` etc. (the single/double-char right side of contractions).
- **Why deferred:** user rejected on style grounds — mid-word hand mismatch (DP-hand letters adjacent to font-hand letter within the same word) too jarring.
- **Revisit criteria:** (a) `styles/hw-sample.png` gets replaced with a style that visibly matches an OFL font; (b) a style-transfer path (e.g. future img2img) can re-style the font glyph toward the writer's hand.
- **Origin:** plan `soft-shimmying-parnas`, 2026-04-17.

## Rejected on current-pipeline grounds, re-openable if pipeline changes

### img2img full-line style transfer
- Render intended text with a real handwriting font, VAE-encode, add partial noise, run DDIM denoising under writer style conditioning. Would unify the "hand" across the page and sidestep most short-canvas hallucination.
- **Why deferred:** pipeline starts from `torch.randn` at `reforge/model/generator.py:813` with no VAE encode path. Requires modifying the DDIM sampling loop plus out-of-distribution weight use (DiffusionPen trained text-to-image from noise only). Multi-turn architectural change.
- **Revisit criteria:** (a) DiffusionPen gets re-trained; (b) a small spike shows the existing weights tolerate partial-noise latents acceptably; (c) turn-3+ ablations show wrapper-layer improvements have plateaued and architectural work becomes the only remaining lever.
- **Origin:** plan `soft-shimmying-parnas`, 2026-04-17.

### Multi-seed voting for canvas-fill hallucination
- Generate each word on N seeds, pick the cleanest via OCR or shape-match scoring.
- **Why deferred:** root cause of "cantt"/"itss" is seed-invariant — DP hallucinates surrounding letters when asked to generate 1-char content, regardless of seed. Three seeds just produce three variants of the same failure.
- **Revisit criteria:** if root-cause analysis changes (e.g. failures shown to be seed-dependent by a diagnostic run).
- **Origin:** plan `soft-shimmying-parnas`, 2026-04-17.

## Cantt-specific proposals — status update 2026-04-18

Turn 2026-04-18 attempted F (full-word DP + apostrophe overlay) with K
(OCR safety valve). **Attempted and reverted — negative result.** Alternatives
below are now more relevant.

### F — Full-word DP + `_overlay_apostrophe` (ATTEMPTED, REVERTED 2026-04-18)

- **What we tried:** removed `is_contraction()` dispatch so DP saw whole
  contractions, then post-processed by detecting the apostrophe column
  (character-index ratio + snap-to-inter-letter-gap), blanking a small
  region, and drawing a clean tapered-comma Bezier above the x-height line.
  Turn 2c added an OCR safety valve falling back to the split path if the
  overlay OCR < `CONTRACTION_OCR_FLOOR` (0.5).
- **Evidence it failed** (review 2026-04-18_154757):
  - Composition rating: 2/5. Human note: *"can't is can'''t"* — three
    visible apostrophe-shapes stacked.
  - Punctuation rating: 2/5. `can't` and `it's` read as `can''t'` /
    `it'''o` — same stacking on the punctuation eval.
  - Per-seed variance revealed the mechanism: seed 2718 produced a single
    clean apostrophe (no stacking); seeds 42 and 137 produced three. DP
    renders apostrophe-like ink inside the body zone on some seeds, deeper
    than the overlay's blank region reached. The overlay *added* its clean
    mark on top of DP's stray ink; safety valve never fired because OCR
    could still read "canit" from the stacked output (accuracy 0.8,
    well above the 0.5 floor).
  - Hard-words test ledger confirmed: commit 5bfeca5 contraction OCR on
    seed 42 = 0.8/1.0/1.0/1.0 (can't/they'd/don't/it's). OCR-high, human-bad.
- **Why the fix attempt failed:** widening the blank region to cover the
  full body zone in the apostrophe column required a density guard (skip
  the body-zone blank if the column is high-density, i.e., likely inside
  a letter). But DP's stray apostrophe-shaped ink IS high-density — the
  guard protects against erasing letters AND against erasing the very
  thing we want to erase. Solution would need morphological component
  analysis (identify specifically-apostrophe-shaped components and erase
  only those), which is substantially more code than a rectangle blank.
- **Reverted commits:** fe12a7b (Turn 2b overlay), 7d55f9c (Turn 2c
  safety valve). Kept: Turn 2d font glyph rendering for trailing marks,
  Turn 1 determinism, Turn 2e deferral register.
- **Revisit criteria:** (a) someone designs a morphological-component-
  based detector that can reliably isolate DP's apostrophe ink without
  touching letter ink, or (b) the full-word DP path (no overlay, option
  E below) demonstrates acceptable apostrophe quality on its own, or
  (c) img2img becomes feasible and renders apostrophes in the writer's
  style without post-processing.

### E — Drop splitting entirely, full-word DP, NO overlay (PROMOTED TO PRIMARY CANDIDATE)

Previously listed as "diagnostic only"; review results make this the
leading candidate for next turn. Rationale: the overlay was the source
of the stacking regression, so removing splitting WITHOUT adding an
overlay is different from both the current (split) and attempted (F) paths.
- **What it would do:** remove `is_contraction()` dispatch so DP generates
  contractions as single words. No overlay. Trust DP's rendering.
- **Why worth trying:** hard-words OCR data showed DP renders contractions
  decently on 2-3 of 4 words (can't 0.8, they'd 1.0, don't 1.0, it's 1.0
  at seed 42 on commit 5bfeca5). Seed 2718 composition showed DP producing
  a visually clean "can't" on its own. The known pre-split risk is that
  some words/seeds will produce unreadable output; without a safety valve,
  those regress.
- **Risk:** without safety valve, a bad DP contraction regresses the whole
  composition. Mitigations: rely on the existing OCR rejection + retry
  loop in `generate_word` (up to 2 retries if accuracy < 0.4); if that
  still fails, the word gets recorded to hard_words candidates for manual
  triage.
- **Revisit:** next turn, after the lessons from F's failure are integrated
  into the plan. Consider combining with option W (split at `'t` boundary)
  as an intermediate: generate `can` and `'t` as 2-char units, which avoids
  1-char canvas-fill hallucination and removes the synthetic apostrophe
  path entirely.

The pre-F cant/k/o/l/y Plan B alternatives follow; these are the alternatives held in reserve.

### W — Split at (can, 't)
- Generate `'t` as a 2-char unit rather than splitting apostrophe out as its own synthetic glyph.
- **Why deferred:** F chosen as the structural bet; W is redundant if F succeeds.
- **Revisit criteria:** F regresses OCR below the current split-path baseline — specifically if Turn 2c's OCR safety valve trips on >50% of contractions.
- **Origin:** plan `soft-shimmying-parnas`, 2026-04-17.

### E — Drop splitting entirely, no overlay
- Simplest change: `is_contraction()` returns False, DP handles whole contraction with whatever apostrophe it produces.
- **Why deferred:** expected to regress OCR (pre-split DP contractions OCR'd 0.0-0.5 per FINDINGS). Useful only as a diagnostic baseline, not as a shipped change.
- **Revisit criteria:** as a Turn-3 ablation data point, not as a replacement for F.
- **Origin:** plan `soft-shimmying-parnas`, 2026-04-17.

### Q — Wider canvas (320px) for full contraction
- Increase canvas width from 256px to 320px (UNet max) for contractions to reduce canvas-fill hallucination pressure.
- **Why deferred:** F at default width expected to resolve the problem. Cheap parameter tweak.
- **Revisit criteria:** Turn 2a diagnosis shows DP's full-word output still has canvas-fill pressure on contractions, or F's overlay position detection is noisy because letters crowd the canvas.
- **Origin:** plan `soft-shimmying-parnas`, 2026-04-17.

### L — Tight-crop DP right-side output
- Aggressively crop the right-side generation to its central 30-40% before stitching, discarding canvas-fill margins.
- **Why deferred:** only relevant if we keep the split path. Not applicable under F.
- **Revisit criteria:** W becomes active (i.e., split path returns).
- **Origin:** plan `soft-shimmying-parnas`, 2026-04-17.

### O — Wider post-apostrophe gap
- Add 2-3px extra space after the apostrophe in stitch geometry so the eye registers a clear letter boundary.
- **Why deferred:** only relevant if we keep the split path. Not applicable under F.
- **Revisit criteria:** W becomes active.
- **Origin:** plan `soft-shimmying-parnas`, 2026-04-17.

### Y — Curated library of known-good contraction endings
- Cache well-generated `'t` / `'s` / `'d` fragments from previous runs, reuse them for future contractions.
- **Why deferred:** introduces technical debt (content caching, cross-run style drift). Pragmatic but ugly.
- **Revisit criteria:** F + K + W all plateau and we're choosing between this and retraining.
- **Origin:** plan `soft-shimmying-parnas`, 2026-04-17.

### Alternate apostrophe shapes
- Dot, angled slash, or floating comma variants beyond the chosen "tapered comma above x-height."
- **Why deferred:** initial shape choice lands first; alternatives are iteration candidates.
- **Revisit criteria:** initial shape does not land in review (reads as letter, clips into descenders, or doesn't blend).
- **Origin:** plan `soft-shimmying-parnas`, 2026-04-17.

## Scoped out for dedicated work later

### Caveat glyphs too thin in composition (Turn 2d follow-up)
- Review 2026-04-18_154757 punctuation eval flagged small ";" and "!". Caveat strokes survive the smoke test (single word at full canvas height) but look visually thin after composition's normalize_font_size + 2x upscale. The old Bezier marks (`make_synthetic_mark`) use `stroke_w = body_height * 0.12` + `dot_radius = body_height * 0.16` — denser than Caveat's natural weight at the same cap-height.
- **Why deferred:** discovered alongside the overlay regression in the 2026-04-18 review; separate issue worth its own turn with a dedicated smoke test at production scale.
- **Fix approach:** add a morphological dilate step to `render_trailing_mark` in `reforge/model/font_glyph.py`. Target stroke width = Bezier-equivalent (`body_height * 0.12`). Post-rasterization, measure the Caveat glyph's median stroke width; dilate by the difference. Verify with a new smoke-test script that renders Caveat marks at production body_height (18-30px), composites inline with DP words at the same scale, and qpeeks for approval before integrating.
- **Revisit criteria:** next turn after the cantt problem is addressed.
- **Origin:** review 2026-04-18_154757, turn `soft-shimmying-parnas`.

### Style-matching font-rendered trailing marks to the writer
- Use StyleEncoder scoring to pick the best-matching OFL font from a candidate set, or post-render a style-nudge pass over the font glyph.
- **Why deferred:** complexity; trailing-marks font fallback is already a net win without style matching.
- **Revisit criteria:** reviews cite font marks as visibly mismatched from writer style after the basic fallback lands.
- **Origin:** plan `soft-shimmying-parnas`, 2026-04-17.

### "by" descender clipping
- Recurring human observation that "by" descender (the `y`) is clipped at composition time — only the two peaks remain visible.
- **Why deferred:** separate spec scope. May benefit incidentally from harmonization over mixed font + DP content once turn 2026-04-17 ships.
- **Revisit criteria:** review after turn 2026-04-17 still cites the defect; then draft a dedicated spec.
- **Origin:** FINDINGS.md (Baseline alignment fragile finding, review 9 = 2026-04-17_141320).

### Widening the last-5 composition rating window
- Change the "last 5 ratings median" quality target to last-7 or last-10.
- **Why deferred:** methodology tweak, not load-bearing on current defects. Should only move if evidence shows the 5-window measures the wrong thing.
- **Revisit criteria:** evidence that 5-window variance is masking real trajectory movement (e.g. 10-window median tells a different story).
- **Origin:** prior spec 2026-04-17's "Out of scope" section.

### QUALITY_WEIGHTS reweighting
- Retune the weights in `reforge/quality/score.py` to better match human candidate preference (reviews show ~25% human-metric agreement).
- **Why deferred:** blocked on the candidate-score log from spec 2026-04-17 D1 reaching N>=15 samples.
- **Revisit criteria:** candidate log has >=15 human-picked samples joined against logged candidate scores.
- **Origin:** FINDINGS.md (Quality score disagrees with human candidate preference).

### Plateaued single-char sizing
- Capital `I` fills the full canvas, making lowercase words look tiny by comparison. Four wrapper-layer interventions exhausted.
- **Why deferred:** requires a design-level change (retraining, new model, or pre-generation case handling via architectural change). CLAUDE.md names this as out of scope.
- **Revisit criteria:** DP retrained on case-proportional data; or a different model with case awareness is adopted; or user explicitly accepts 2/5 as target.
- **Origin:** FINDINGS.md Plateaued finding (2026-04-10).

### Retraining / fine-tuning DiffusionPen
- Any workflow that modifies the pretrained UNet, style encoder, or VAE weights.
- **Why deferred:** CLAUDE.md non-goal.
- **Revisit criteria:** explicit scope change from the user.
- **Origin:** CLAUDE.md "Non-goals."
