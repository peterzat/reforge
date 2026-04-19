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

## Contraction rendering proposals

Status: F (full-word DP + overlay) and E (full-word DP, no overlay) have both
been attempted and reverted on human review. Option W is the active spec
(2026-04-18). If W also fails, the remaining wrapper-layer moves are Q/Y or
promotion of the finding to Plateaued. See FINDINGS.md Apostrophe-rendering
entry for the full history.

### F — Full-word DP + overlay apostrophe
- Full-word DP with a post-hoc apostrophe overlay: detect apostrophe column, blank a small region, draw a clean Bezier mark on top.
- **Why deferred:** attempted and reverted 2026-04-18 (review `_154757`, reverted commits fe12a7b + 7d55f9c). Rectangle-blank-plus-density-guard cannot distinguish DP's stray apostrophe-shaped ink from letter ink; a real fix needs morphological-component analysis. Full detail in FINDINGS.md Apostrophe-rendering Review 7.
- **Revisit criteria:** (a) a morphological-component-based detector reliably isolates DP's stray apostrophe ink without touching letter ink, or (b) img2img becomes feasible and renders apostrophes in the writer's style without post-processing.
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

### S — Contraction right-side sizing (apostrophe+t thin ink)
- Close the `'t` / `'s` / `'d` right-side chunk defect where the 2-char split output renders with visibly lighter ink weight and smaller glyph than the left-side neighbor letters. Demo `can't` in `docs/output-history/20260419-161539.png` shows it plainly. A durable fix must include regression tests that measure right-vs-left stroke width + x-height and gate on a tolerance, plus a human-review pass on `make test-human EVAL=composition` with freeform notes that do not cite apostrophe+right-chunk as too thin or too small.
- **Why deferred:** out of scope for active spec 2026-04-19 (short-word baseline alignment). Tracked as Option W follow-up in FINDINGS.md Apostrophe-rendering Review 9.
- **Revisit criteria:** next contraction-focused spec, OR `'t`/`'s`/`'d` thin-ink flagged in 2+ consecutive human reviews, OR project targets composition >= 4/5 and this is the loudest remaining defect.
- **Origin:** spec 2026-04-19, review `2026-04-19_021632` (Option W landing).

## Scoped out for dedicated work later

### Caveat glyphs too thin in composition (Turn 2d follow-up) (ACTIVE in spec 2026-04-19)
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

### candidate-eval human-pick join key
- Record the human-selected candidate index into the review JSON (or the candidate-scores JSONL keyed by word+seed+timestamp) so candidate-score logs can be joined against human preference for QUALITY_WEIGHTS tuning.
- **Why deferred:** requires an interactive `make test-human EVAL=candidate` review to verify the join key populates correctly; out of scope for an autonomous turn. Deferred in spec 2026-04-17 (criterion D3) and carried through spec 2026-04-18 without being addressed.
- **Revisit criteria:** a `make test-human EVAL=candidate` session is due OR the `quality_score_disagrees` finding's data gap is chosen as the primary target of a turn. The entry above (QUALITY_WEIGHTS reweighting) cannot unblock without this join-key landing first.
- **Origin:** spec 2026-04-17 (criterion D3).

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
