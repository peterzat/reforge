# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.
It holds rules and gotchas; reference material lives in `docs/` and is linked
where it applies.

## What this project does

Reforge is a handwriting style transfer system built on DiffusionPen (ECCV 2024). The user provides a photograph of a handwritten sentence (5 words); the system segments it into word images, uses them as style references for DiffusionPen, and generates arbitrary English text in that handwriting style as a grayscale PNG. Multi-line and multi-paragraph output is supported. The output should look like a handwritten note suitable for printing.

This is an applied science project. Development is experiment-driven: every quality change is validated through A/B testing, and the test infrastructure is designed so Claude Code can autonomously iterate toward better output.

### Non-goals

- Real-time generation (batch is fine)
- Training or fine-tuning DiffusionPen (inference only)
- Non-Latin scripts (IAM dataset is Latin only)
- Web UI (CLI-first, library-second)

## Quality target

The target is "the best achievable wrapper around frozen DiffusionPen," not "indistinguishable from real handwriting."

**Gate** (must hold on every seed 42/137/2718 in `make test-regression`):

- `x_height_consistency` must not drop more than 0.05 below its per-seed baseline (baseline 0.954 on all seeds, 2026-10-13). It measures the `size_inconsistent` defect directly (all-body words like `was`/`on`/`so` against the x-height of long words). The user preferred the sizing policy it rewards on 3/3 seeds in a blind A/B (`reviews/human/2026-10-13_170905.json`). It is a regression floor for a human-validated property, not a proxy for overall preference.
- OCR floor: every word of 3+ letters reads at >= 0.30 (TrOCR hallucinates on 1-2 letter words).
- SSIM >= 0.80 against `tests/medium/reference_output.png`.

**History:** spec 2026-04-10 gated on `height_outlier_score`, chosen by Spearman correlation at N=16 (rho +0.30). At N=34 it did not replicate (rho -0.22 on the 18 held-out reviews) and it rewarded equal total word height, the mechanism behind `size_inconsistent`. See `docs/metric_correlation.md`. No CV metric yet tracks overall human preference: the best held-out signal is `word_readability_rate` (rho ~+0.2).

**Human-preference target:** median composition rating >= 4/5 across the most recent 5 `make test-human` reviews (the April median was 3/5; zone sizing and the compose fixes of 2026-10-13 have not had a composition review yet). For deciding between two variants, prefer blind pairwise A/B (see Measurement practice).

### Scope limits

- **Do not chase problems that retraining would solve.** Interventions in the wrapper layer (preprocessing, candidate selection, post-processing, composition) are fair game. Anything that would require the base model to generate different pixels is out of scope.
- **Plateau claims need clean experiments.** The capital-`I` sizing finding was declared a DiffusionPen-level plateau after four wrapper interventions, and the x-height lever was ruled out on 2026-04-19; both conclusions were confounded by compose bugs found on 2026-10-13 (see Hard-won design constraints). Before declaring a plateau, confirm the experiment held generation fixed and that both arms were free of known defects.
- Targets may be raised or lowered with human review. Either move should be explicit, not a side effect.

## Commands

Always use `.venv/bin/python` (or activate the venv first).

```bash
# Setup
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
make setup-hooks          # pre-commit: quick tests; pre-push: regression gate

# Run
./demo.sh                 # seed 42 demo -> result.png + result.json (run manifest)
python reforge.py --style styles/hw-sample.png --text "Hello world" --output result.png --seed 7
python reforge.py --style-images w1.png w2.png w3.png w4.png w5.png --text "Hello" --output result.png

# Tests
make test-quick            # quick tests (mocked, ~5s, no GPU)
make test-regression       # quality regression gate (GPU, ~25s)
make test-ocr              # OCR accuracy only (GPU)
make test-medium           # medium tier (GPU, ~4 min); `make test` is an alias
make test-full             # e2e tests + demo.sh + best-output + archive (GPU, ~6 min)
make test-hard             # hard words (GPU, ~30s)
make test-tuning           # preset / generation-default optimality (GPU, ~55s)
make test-human            # human review wizard (see docs/human-review.md)
make review                # demo + manifest metrics
make findings-sweep        # list review JSONs not yet processed into FINDINGS.md

# A single test
.venv/bin/python -m pytest tests/quick/test_baseline.py -x -q

# Re-baseline the regression gate (deliberate, human-approved changes only)
.venv/bin/python -m pytest tests/medium/test_quality_regression.py --update-baseline --update-reference -x -s

# Visual inspection from this headless box
./qpeek.sh result.png
```

"Run all tests" means `make test-full`. It includes demo.sh and archives one OUTPUT_HISTORY entry; do not substitute `make test` or `make test-medium`.

### Development loop

| Stage | Command | When |
|-------|---------|------|
| Edit check | `make test-quick` | After every code change |
| Gate | `make test-regression` | After changing generation, sizing, compose or config values |
| Full validation | `make test` | After completing a fix or feature |
| Pre-push validation | `make test-full` | Once per push (it writes an OUTPUT_HISTORY entry) |
| Human review | blind A/B or `make test-human` | After quality-affecting changes (advisory, not gating) |

Hooks: pre-commit runs `make test-quick`-equivalent (logic errors); pre-push runs the regression gate (quality regressions). `/codereview` is a static review and does not run tests. Keep this separation: fast logic checks at commit time, quality regression at push time, everything else during development.

GPU compute is plentiful for reforge's ~3.5 GB, but the GPU is shared: daydream's production vLLM server holds ~9 GB and ComfyUI can take 6-12 GB while rendering. Do not stop other projects' servers. Run GPU tests aggressively within the free memory. Launch long GPU jobs with `setsid nohup ... &` so an SSH drop does not kill them.

## Measurement and experiment practice

These rules come from the 2026-10-13 audit (`docs/audit-2026-10-13.md`), which found that the project's main measurement instruments had drifted from what they claimed to measure.

- **Seed everything you compare.** `--seed` / `run(seed=...)` seeds each word from (seed, word index) with deterministic cuDNN; the same seed is pixel-identical across processes. Every run writes `<output>.json` (seed, settings, git commit + dirty flag, sizing policy, full metrics); read metrics from it rather than re-scoring a PNG (re-scoring cannot run OCR).
- **Hold generation fixed for downstream changes.** For sizing, compose, harmonization or post-processing changes, cache `generate_word()` outputs once and replay both arms from the cache. Otherwise generation noise swamps the change.
- **Write the expectation first.** Record what you expect in `docs/experiment-log.jsonl` (`reforge.evaluate.experiments.log_experiment`, field `expected`) before running, then log the observed outcome and verdict, including falsified expectations.
- **Decide between variants with blind pairwise A/B,** not 1-5 ratings: randomized order, key stored separately, recorded as a review JSON. Run the blind model judge (fresh-context subagent, fixed rubric, images only) first as a pre-screen and log its agreement with the human. Calibration so far: 3/3 agreement on one session.
- **Look at the output.** Claude Code reads PNGs directly. Contact sheets of every word with detected baselines drawn found more bugs on 2026-10-13 than any metric.
- **Gates need held-out replication.** With ~16 metrics tested at p < 0.3, about 5 pass by chance. A metric gates only after it holds on reviews it was not selected on, or after a human-validated controlled comparison. Rerun `scripts/metric_correlation.py --output docs/metric_correlation.md` after review sessions.
- **The evaluator is the human's.** Changing `PRIMARY_METRICS`, gate thresholds, the gate's word list, `quality_baseline.json`, `reference_output.png` or `QUALITY_CONTINUOUS_WEIGHTS` requires explicit human approval in the conversation. Never re-baseline to make a failing gate pass. `.claude/settings.json` enforces part of this: editing `quality_baseline.json` or `regression_gate.py`, or running anything with `--update-baseline` / `--update-reference`, prompts for approval.
- **One stage graph.** `pipeline.postprocess_words()` is the single definition of sizing + harmonization. Tests, evals and experiments call it rather than re-wiring the passes (the old gate's hand-wired copy skipped a stage production ran).
- **Human reviews are ground truth.** `reviews/human/*.json` is tracked and never deleted (`prune_reviews.py --apply` moves to `stale/`).

## Human review and FINDINGS workflow

Reference (eval types, code-area mapping, qpeek modes): `docs/human-review.md`.

**When changing generation, composition, or quality code, read `reviews/human/FINDINGS.md` for human-observed quality patterns.**

**qpeek rules:** run review servers in the foreground or as `./qpeek.sh ... & sleep 1; disown`, never with `run_in_background`. After "qpeek ready", the URL must be the last visible text in the response, as `**qpeek ready: <url>** -- waiting for your review.`, using the Tailscale `100.x.x.x` address. When the user says "qpeek <file>", run `./qpeek.sh <file>` immediately.

**Findings workflow:** FINDINGS.md maintenance is tied into the `/spec` loop.

- **Detection:** `scripts/findings_sweep.py` (also `make findings-sweep`) lists any review JSON in `reviews/human/` whose filename stem sorts after the `FINDINGS_LAST_PROCESSED` marker at the top of FINDINGS.md. Exits 1 if anything is unprocessed, 0 otherwise. Read-only.
- **Automatic hook on `/spec` in evolve mode at turn close:** after all spec acceptance criteria are verified met, AND before generating the next-turn proposal, run `.venv/bin/python scripts/findings_sweep.py`. If it exits 1, draft FINDINGS.md updates inline, **present the diff in the terminal** (not via qpeek; qpeek is for images only), wait for user ack, apply the edits, bump the `FINDINGS_LAST_PROCESSED` marker to the newest review's stem in the same edit, then continue to proposal generation. If the sweep exits 0, skip.
- **When drafting updates**, use the triage rules in FINDINGS.md's "How this file works" section (evidence-for-existing / new-standalone / not-actionable) and apply the status-change triggers:
  - Move to **Resolved** when a targeted eval or specific review note confirms the fix.
  - Move to **Plateaued** when the rule in FINDINGS.md is met: 3+ code changes, 3+ reviews, no rating movement >= 1 point, from experiments that held generation fixed (see Scope limits).
  - Propose **Graduation** to CLAUDE.md when 3+ reviews AND 2+ code changes AND the principle is stable and generalizable. Graduation promotes the principle into "Hard-won design constraints" and compresses the FINDINGS entry to a pointer.

**Finding-driven iteration pattern:**
1. Read `reviews/human/FINDINGS.md` and pick the most actionable Active finding. Skip Plateaued findings unless you have a design-level change.
2. Implement the smallest change that addresses the root cause.
3. Validate with a blind A/B on cached generations, or `make test-human EVAL=<affected types>`.
4. Update the finding's status based on human feedback.

Human review is advisory only. It is not a commit gate.

## Architecture

Module map and data flow: `docs/architecture.md`. Entry points:

- `reforge.py` (CLI) -> `reforge/pipeline.py:run()` -> `postprocess_words()` -> `compose/render.py:compose_words()`
- Generation: `reforge/model/generator.py:generate_word()` (trailing marks -> contraction -> chunking -> best-of-N -> OCR retry)
- Sizing: `reforge/quality/font_scale.py` (`SIZING_POLICY` in `config.py`)
- Gate: `tests/medium/test_quality_regression.py`, `reforge/evaluate/regression_gate.py`
- Compute placement rules and VRAM budget: `docs/compute-strategy.md`
- Test tiers, metric validity table, hard-words watchlist: `docs/testing-guide.md`

## DiffusionPen model constraints (immutable)

These are hard constraints from the pretrained model. They cannot be changed without retraining.

### UNet architecture

Custom UNet (not a diffusers model). Loaded from `ema_ckpt.pt` (not `ckpt.pt`). Constructor:
```python
UNetModel(image_size=(64,256), in_channels=4, model_channels=320, out_channels=4,
          num_res_blocks=1, attention_resolutions=(1,1), channel_mult=(1,1),
          num_heads=4, num_classes=339, context_dim=320, vocab_size=79,
          text_encoder=<CanineModel>, args=_Args())
```

Fully convolutional in width (works at any width multiple of 16), but quality degrades beyond 320px (1.25x training width).

### 5-style-image requirement

The UNet has a hardcoded reshape:
```python
y = y.reshape(b, 5, -1)   # literal 5
y = torch.mean(y, dim=1)
y = self.style_lin(y)      # Linear(1280, 1280)
emb = emb + y
```
StyleEncoder.encode() must return `(batch*5, 1280)` raw features. Do NOT mean-pool before passing to UNet.

### Normalization

- Style images: `(pixel/255 - 0.5) / 0.5` (white=+1, black=-1). Do NOT use ImageNet stats.
- VAE decode: `vae.decode(latent / 0.18215).sample`, then `(x/2 + 0.5).clamp(0,1)` -> [0,1] RGB.

### Text encoding

Canine-C tokenizer output dict passed directly to UNet as `context`. UNet calls `self.text_encoder(**context)` internally, projects 768->320 via `self.text_lin`.

### State dict loading

Checkpoint saved with DataParallel wrapping the UNet and the text_encoder inside it. Keys look like `module.text_encoder.module.char_embeddings.*`. The loader must strip both `module.` prefixes.

### CFG (Classifier-Free Guidance)

Two UNet passes per timestep when `guidance_scale != 1.0`: conditional (text + style) and unconditional (tokenized `" "` + zero style features). Combined as `noise_pred = uncond + scale * (cond - uncond)`. Default scale is 3.0. Setting 1.0 disables CFG.

### Canvas filling

DiffusionPen fills its 64px canvas vertically for every word regardless of letter shapes: raw ink height is ~64px for "was", "remember" and "bakery" alike. An all-body word therefore arrives with ~2.2x the x-height of an ascender word. Any sizing that equalizes total ink height preserves that gap (see Word sizing below).

### Style image requirements

- Exactly 5 words required (hardcoded reshape)
- Each word must be >= 4 chars (IAM training filter: `len > 3`)
- All 5 words should be from the same writer, with consistent pressure and slant
- Default reference sentence: "Quick Brown Foxes Jump High"
- Triplet-loss encoder (default) generalizes better to novel writers
- Multi-writer sourcing plan (not started): `docs/style-inputs.md`

### Charset

80 characters: `a-z A-Z 0-9 space _ ! " # & ' ( ) * + , - . / : ; ?`
Newlines allowed only as paragraph separators.

### Word length

~8 chars fit naturally on 256px canvas. Words up to 10 chars can use adaptive canvas width (up to 320px). Words >10 chars require syllable splitting + stitching, with quality degradation.

### Model weights (HuggingFace `konnik/DiffusionPen`)

| File | Purpose |
|------|---------|
| `diffusionpen_iam_model_path/models/ema_ckpt.pt` | UNet (use this, not ckpt.pt) |
| `style_models/iam_style_diffusionpen_triplet.pth` | Style encoder (default, better for new writers) |
| `style_models/iam_style_diffusionpen_class.pth` | Style encoder (better for IAM writers) |

VAE + scheduler from `stable-diffusion-v1-5/stable-diffusion-v1-5`. Canine-C from `google/canine-c`. Shared HuggingFace cache at `~/.cache/huggingface/`.

## Hard-won design constraints

Each describes a real problem, its root cause, and the constraint that prevents it.

### Gray box artifacts (multi-layer defense required)

**Problem:** Gray rectangular regions appear around word ink, especially short words.

**Root cause cascade:** DiffusionPen generates dark-gray backgrounds (~150-175) for short words. Fixed thresholds cannot distinguish ink from background. Bicubic upscaling creates interpolation halos around isolated noise pixels.

**Required defense layers:**
1. Adaptive background estimation: 90th-percentile pixel value, ink threshold at 70% of estimate
2. Body-zone anchored noise removal: middle 60% of rows defines "body zone"; columns without sufficient body-zone ink are blanked
3. Isolated-cluster filtering: column clusters are grouped transitively when gaps are under 20px; groups other than the largest are discarded unless they hold >= 15% of the ink columns (which keeps the right half of a contraction)
4. Compositor-level filtering: composite only ink pixels (< 200 threshold) onto canvas
5. Post-upscale halo cleanup: dilate strong-ink mask (~4px radius), blank gray pixels not near dilated ink

**Constraint:** No single threshold or layer suffices. Always test with single-character words ("I", "a") and very short words.

### Word sizing (zone sizing, one resample)

**Problem:** Short all-body words ("was", "on", "so") rendered at ~2x the body size of their neighbors while descender words ("by") looked small and raised: the `size_inconsistent` defect in 26 of 34 rated reviews.

**Root causes (2026-10-13):** (1) DiffusionPen fills the canvas, so equal total ink height means unequal x-heights. (2) The sizing passes (normalize, body-zone equalize, two height-harmonize passes) each resampled the previous output: body-zone equalization shrank short words to ~0.2x and height harmonization re-inflated them to ~0.4x, so it changed nothing except blur, and "by" went through a 15px bottleneck.

**Required solution:**
- `SIZING_POLICY = "zone"`: size each word so its x-height lands on `ZONE_X_HEIGHT_TARGET`, with the x-height from `font_scale.estimate_x_height`: a letter-class prior (`ZONE_HEIGHT_RATIOS`; "t" is a weak ascender in this hand) blended toward the measured ratio for words of 4+ letters. `compute_x_height` alone misreads short words ("it" as 5-9px of a 64px word).
- Compose all sizing decisions into one scale per word and resample once (`plan_word_scales` / `size_words`). Never chain resizes.
- Trailing marks use the same `estimate_x_height`.
- `total_height` remains available for A/B and rollback.

**Lesson:** the 2026-04-19 conclusion that "x-height is the wrong lever" came from an experiment whose both arms carried the baseline clamp bug below. An experiment cannot rule out a lever while a known defect sits in both arms.

### Stroke weight variation (global harmonization)

**Problem:** Adjacent words look bold/thin inconsistently.

**Root cause:** Per-word contrast stretching independently sets each word's ink range.

**Required solution:** Compute median ink brightness across all words, shift each word's ink to converge on global median. Do this after sizing, before composition.

**Plateau (graduated from FINDINGS 2026-04-20):** The post-processing harmonize pass has exhausted its lift. Six consecutive A/B reviews on the harmonize strength showed no visible difference between variants. Further stroke-weight gains come from **candidate selection** (stroke-width scoring during best-of-N against style images as reference), not from the harmonize pass. Keep the harmonize pass as a floor, but do not tune it further.

### Long word chunking (score-based syllable splitting)

**Problem:** Words >10 chars need splitting, but naive splits create awkward chunks and visible seams.

**Required solution:**
- Score all split positions: balance (prefer equal chunks) + consonant-cluster penalty (-3 if >= 3 trailing consonants) + boundary bonus (+2 for CC boundary, +1 for CV)
- Each chunk must be >= 4 chars (IAM minimum)
- Normalize chunk heights to median before stitching
- Baseline-aligned stitching via **ink-profile cross-correlation**, not single-point ink-bottom alignment (graduated from FINDINGS 2026-04-19).
- Overlap blending (8px linear alpha fade) at stitch boundary

**Asymmetric split stitching (contractions, graduated from FINDINGS 2026-04-20):** Where one chunk is substantially shorter (e.g. `can` + `'t`), the short chunk falls outside IAM's 4-char training distribution and emerges thinner, smaller and lighter. Use `_match_chunk_to_reference` (`reforge/model/generator.py`) to match the short chunk's ink height, stroke width and ink median to the long chunk. Then stitch on each half's **detected baseline** (`detect_baseline` with the part's text), not on ink bottoms: ink-bottom alignment put the `'d` of "they'd" on the tip of the `y` descender, and the old padding doubled any bottom mismatch (fixed 2026-10-13).

### Trailing punctuation synthesis (graduated from FINDINGS 2026-04-20)

**Problem:** DiffusionPen does not produce visible ink for trailing punctuation. Any punctuated word rendered whole comes out unpunctuated.

**Required solution:**
- Split **every** trailing mark off (`split_trailing_marks`: "Wait..." -> "Wait" + "..."), generate the base word through `generate_word` recursively (so "don't." takes the contraction path and "extraordinarily," is chunked), then attach marks left to right (`_attach_trailing_marks`). Punctuation is checked before contractions.
- Use Caveat TTF glyphs (not Bezier curves) for natural mark shape (`reforge/model/font_glyph.py`).
- Retarget morphological dilation against the **measured Bezier-equivalent stroke width**. `TRAILING_MARK_TARGET_MULTIPLIER = 1.15` is the production value.
- Attach baseline-aware using `compose.layout.detect_baseline`, not full ink bottom.

**Regression coverage:** `TestDilateToBezierBaseline` (1.15x ratio across five marks at three body heights), `TestTrailingMarkRouting`.

### Preprocessing order (per-word operations only after segmentation)

**Problem:** Full-image deskew corrupts adaptive thresholding. Full-image morphological cleanup severs cursive letter connections.

**Constraint:** On the full sentence image, do only: threshold, tight crop, segmentation. Per-word operations (deskew, morph cleanup, component filtering, contrast normalization) happen after each word is cropped.

### Baseline detection and placement

**Problem:** Words read as superscript or sunk: "exactly", "maybe", "by", "it was a" raised; "two", "for" low.

**Root causes (2026-10-13):** (1) `compose_words` clamped any word whose baseline *row index* was more than 20% from the line's median row to that median. Word canvases are scaled by different factors, so those indices are not comparable; the clamp moved ~30% of correctly detected words by 10-18px (after upscale) and missed the real detection errors. (2) The density scan put "it" and "for" on their crossbars and "by" on its descender tip.

**Required solution:**
- Place each word's detected baseline row on the line's ruled baseline. No clamp. Never compare row indices across differently scaled canvases.
- `detect_baseline(img, word)` is word-aware: a word with no descender-capable character (`gjpqy`, cursive `f`, trailing `,` `;`) sits on its ink bottom; otherwise scan from the midpoint for a density drop, require "body below" to be a run of >= 15% of ink height (not a one-row tail curl), and walk back to the last row at >= min(0.35, 0.5 x the word's peak density).
- Shift all offsets so the highest word top is row 0 (first-line words with low baselines were silently dropped).
- Verify by drawing detected baselines on a contact sheet of every word; regression tests build fixtures from the measured profiles of real words.

## Anti-patterns (do NOT do these)

- Do NOT use ImageNet normalization for style images. Use `(pixel/255 - 0.5) / 0.5`.
- Do NOT mean-pool style features before passing to UNet. The UNet does its own reshape + mean internally.
- Do NOT deskew the full sentence image. Only deskew individual word crops.
- Do NOT apply morphological cleanup to the full sentence image. Only per-word.
- Do NOT use `ckpt.pt`. Use `ema_ckpt.pt`.
- Do NOT use a single threshold for gray-box removal. Multi-layer defense is required.
- Do NOT equalize total ink height across words; size by x-height (zone sizing).
- Do NOT chain image resizes across sizing passes. Compose the scales and resample once.
- Do NOT compare baseline row indices across word canvases of different scale.
- Do NOT tighten total-height harmonization beyond 110%/88% (metric gaming: "The" rendered as "Tle" at word_height_ratio 1.00).
- Do NOT split long words without ensuring each chunk is >= 4 chars.
- Do NOT align stitched chunks at the top, or on single-point ink bottoms. Use cross-correlation (chunks) or detected baselines (contractions).
- Do NOT use fixed background threshold (e.g., 200). Use adaptive 90th-percentile estimation.
- Do NOT override `HF_HOME` per-project. Use the shared cache at `~/.cache/huggingface/`.
- Do NOT set global torch numerics (TF32, cuDNN flags) at module import.
- Do NOT hand-wire the sizing/harmonization passes in tests or evals; call `pipeline.postprocess_words`.

## Known constraints

- Exactly 5 style images required (UNet hardcoded reshape)
- Each style word must be >= 4 chars (IAM training filter)
- Max ~10 chars per word before chunking (MAX_WORD_LENGTH = 10)
- Charset is 80 chars (no accents, no unicode beyond basic punctuation)
- Output is always grayscale (mode "L")
- IAM training bias: Western handwriting works best; novel styles produce less faithful output
- `ZONE_HEIGHT_RATIOS` were measured on hw-sample output; other hands may need their own
- TrOCR-small (the OCR instrument) is unreliable on 1-2 letter words
