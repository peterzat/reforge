# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## What this project does

Reforge is a handwriting style transfer system built on DiffusionPen (ECCV 2024). The user provides a photograph of a handwritten sentence (5 words); the system segments it into word images, uses them as style references for DiffusionPen, and generates arbitrary English text in that handwriting style as a grayscale PNG. Multi-line and multi-paragraph output is supported. The output should look like a handwritten note suitable for printing.

This is an applied science project. Development is experiment-driven: every quality change is validated through A/B testing with CV metrics, and the test infrastructure is designed so Claude Code can autonomously iterate toward better output.

### Non-goals

- Real-time generation (batch is fine)
- Training or fine-tuning DiffusionPen (inference only)
- Non-Latin scripts (IAM dataset is Latin only)
- Web UI (CLI-first, library-second)

## Quality Target (spec 2026-04-10 E1)

The project has a concrete "done" target so the iteration loop can declare
victory instead of chasing proxies forever. The target is "the best achievable
wrapper around frozen DiffusionPen," not "indistinguishable from real
handwriting."

**Primary gate targets** (must hold on every seed in the multi-seed regression):

- `height_outlier_score >= 0.90` (the only metric cleared the B1 bar at N=16)
- `ocr_min >= 0.30` (existing readability floor, gates independently)

`height_outlier_score` was chosen by the Spearman correlation analysis in
`docs/metric_correlation.md` as the only CV metric with positive rho >= 0.2 and
p < 0.3 against human composition ratings. `baseline_alignment` was a near
miss (rho = +0.273, p = 0.307) and is tracked as a diagnostic. All other
metrics (`composition_score`, `style_fidelity`, `stroke_weight_consistency`,
`ocr_accuracy`, `layout_regularity`, `background_cleanliness`, etc.) are
diagnostics that print on regression but do not gate; four of them are
*negatively* correlated with human rating on this dataset, which is itself a
finding about the current metric set, not evidence the metrics should be
inverted.

The narrowness of the primary set is deliberate. With one gating metric plus
the OCR floor, the regression is strict but honest: it catches "don't break
height harmonization and don't produce unreadable output," which is the only
thing the current CV metric set supports gating on. Widening requires either
more review data (N=16 is weak) or new metrics designed to positively track
human preference.

**Human-preference target:** median composition rating >= 4/5 across the most
recent 5 `make test-human` reviews. The observed ceiling is 4/5 ("easily our
best so far," review 2026-04-10_002757); the target requires that ceiling to
become the new floor, not a lucky peak. Current median across the last 5 is
3/5, so this is a meaningful but achievable lift.

**Multi-seed stability:** all primary gate targets must hold on all 3 seeds
(42, 137, 2718). Improving one seed at the cost of another is not progress.
The quality regression test enforces this automatically.

### Scope limits (spec 2026-04-10 E2)

- **Sizing at 2/5 is not part of the target.** It is a DiffusionPen-level
  limitation on single-character word generation (see the Plateaued finding
  in `reviews/human/FINDINGS.md`). Four wrapper-layer interventions have been
  exhausted without moving it past 2/5. Fixing it requires retraining,
  fine-tuning, or a different model entirely, which is a non-goal.
- **The target is a wrapper ceiling, not a handwriting ceiling.** If a future
  turn demonstrates the target is too aspirational for this system, it may be
  lowered with human review. If the targets are reached with room to spare,
  they may be raised. Either move should be explicit, not a side effect.
- **Do not chase problems that retraining would solve.** Interventions in the
  wrapper layer (preprocessing, candidate selection, post-processing,
  composition) are fair game. Anything that would require the base model to
  generate different pixels is out of scope.

When all primary gate targets hold on all 3 seeds AND the median of the
last 5 human composition ratings is >= 4/5, the project is "done" at the
methodology level. Further work is optional polish or target-raising.

## Commands

All commands assume an activated venv. Always use `.venv/bin/python` (or activate first).

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make setup-hooks          # install git hooks (pre-commit: quick tests, pre-push: regression)

# Demo (end-to-end, uses hw-sample.png)
./demo.sh

# Run tests via Makefile
make test-quick            # quick tests (mocked, <10s, no GPU)
make test-regression       # quality regression baseline only (GPU, ~14s)
make test-ocr              # OCR accuracy only (GPU, ~14s)
make test-medium           # medium tests (A/B harnesses, GPU, <2min)
make test                  # alias for test-medium
make test-full             # e2e tests + demo.sh (GPU + model weights, ~4.5min)
make review                # run demo + print metrics for visual review

# "Run all tests" means make test-full. This includes demo.sh and output archival.
# Do not substitute make test or make test-medium when asked to "run all tests".

# Run quick tests (mocked, <10s, no GPU)
python -m pytest tests/quick/ -x -q

# Run medium tests (A/B harnesses, optional GPU, <2min)
python -m pytest tests/medium/ -x -q

# Run full tests (e2e, requires GPU + model weights, <10min)
python -m pytest tests/full/ -x -s

# Run a single test
python -m pytest tests/quick/test_preprocessor.py::test_segment_words_finds_5 -x

# Run the CLI
python reforge.py --style hw-sample.png --text "Hello world" --output result.png
python reforge.py --style hw-sample.png --text "First paragraph\nSecond paragraph" --output result.png
python reforge.py --style-images w1.png w2.png w3.png w4.png w5.png --text "Hello" --output result.png

# A/B experiments
python experiments/ab_harness.py --style styles/hw-sample.png --experiment cfg
python experiments/ab_harness.py --style styles/hw-sample.png --experiment scheduler
python experiments/ab_harness.py --style styles/hw-sample.png --experiment postprocess
python experiments/ab_harness.py --style styles/hw-sample.png --experiment combined

# Quick visual inspection (opens in browser from headless box)
./qpeek.sh result.png
./qpeek.sh result.png --ask "How does it look?" --choices "good,bad,meh"
```

### Development loop cadence

| Stage | Command | Time | When |
|-------|---------|------|------|
| Edit check | `make test-quick` | 0.8s | After every code change |
| Parameter tuning | `make test-regression` | ~14s | After changing config values |
| OCR check | `make test-ocr` | ~14s | After changes to generation or postprocessing |
| Full validation | `make test` | ~2 min | After completing a fix or feature |
| Pre-commit gate | `make test-full` | ~4.5 min | Before committing (includes demo.sh visual output) |
| Hard words | `make test-hard` | ~30s | After generation or postprocessing changes |
| Tuning | `make test-tuning` | ~55s | After changing preset values or generation defaults |
| Human review | `make test-human` | ~3 min | After quality-affecting changes (advisory, not gating) |

### Git hook gating strategy

Two hooks gate the commit/push flow, each targeting a different failure class:

| Hook | Runs | Time | What it catches |
|------|------|------|-----------------|
| pre-commit | `make test-quick` | 0.8s | Logic errors, API breakage (mocked, no GPU) |
| pre-push | `make test-regression` | ~14s | Quality regressions (real GPU inference against baseline) |

The full medium suite (~2min) is for development iteration, not gating. Codereview (pre-push, via Claude Code skill) is a static quality review and does not run tests. When adding new test tiers or gating infrastructure, preserve this separation: fast logic checks at commit time, quality regression at push time, everything else during development.

For autonomous iteration, the inner loop is: edit, `make test-quick`, `make test-regression`, repeat. Run `make test` only when the change is ready for full validation.

GPU compute is plentiful (20GB VRAM, ~3.5GB used by DiffusionPen). Run GPU tests aggressively as part of the development loop. Do not be conservative about GPU test execution; the experiment-driven workflow depends on fast, frequent GPU runs for signal.

### Quality review workflow

After `make test-full` or when evaluating output quality:

1. Run `make review` (runs demo.sh, prints metrics in paste-friendly format)
2. Copy the printed output and open `result.png`
3. Paste both into a Claude conversation for visual assessment
4. Findings become items for the next spec

The review identifies issues that CV metrics miss: letter formation quality, natural spacing feel, overall "handwritten note" impression. This is a development workflow, not a runtime gate.

### Human review workflow

Human evaluation captures quality dimensions that CV metrics and multimodal AI miss:
naturalness, spacing feel, overall "handwritten note" impression. Eight structured
evaluation types isolate specific quality dimensions.

```bash
make test-human                          # all 8 eval types (~2 min generation + review time)
make test-human EVAL=candidate,stitch    # run only specific types
```

**Evaluation types:**
- **candidate** -- best-of-N candidate selection calibration
- **stitch** -- chunk stitching overlap comparison
- **sizing** -- short vs long word size consistency
- **baseline** -- baseline alignment with descenders
- **spacing** -- word spacing and jitter comparison
- **ink_weight** -- stroke weight consistency comparison
- **composition** -- full two-paragraph composition rating with defect flags
- **hard_words** -- curated hard words readability check

Reviews are saved to `reviews/human/<timestamp>.json`. The `make test-full` target
prints a staleness notice when pipeline files have changed since the last review.

**When changing generation, composition, or quality code, read `reviews/human/FINDINGS.md`
for human-observed quality patterns.**

**Findings workflow:** After a review, the agent detects unprocessed review JSON files
(review timestamp newer than FINDINGS.md modification time), drafts updated findings,
and presents the draft via qpeek for human approval. Findings that persist across 3+
reviews and 2+ code changes are candidates for graduation to CLAUDE.md.

**Finding-driven iteration pattern:**
1. Read `reviews/human/FINDINGS.md` and pick the most actionable Active finding.
   **Skip Plateaued findings**: they represent base-model limitations that have
   exhausted wrapper-layer interventions and require a design-level change
   (retraining, new architecture, different intervention layer, or explicit
   user acceptance) to exit that status. Iterating on a Plateaued finding with
   another wrapper-layer tweak wastes budget and will not move the human rating.
2. Implement a fix (smallest change that addresses the root cause).
3. Run targeted eval: `make test-human EVAL=<affected types>` (see mapping below).
4. Update the finding's status based on human feedback (Resolved, Acceptable,
   Plateaued, or remains In Progress for another iteration). A finding moves to
   Plateaued after 3+ code changes and 3+ reviews without the rating moving by
   at least 1 point (see FINDINGS.md for the full rule).
5. Repeat with the next finding, or run a full eval every 3 spec iterations as a
   health check.

**Eval type to code area mapping** (for targeted runs after code changes):

| Eval type | Code areas | When to run |
|-----------|-----------|-------------|
| candidate | quality/score.py, config.py (QUALITY_WEIGHTS) | After scoring weight changes |
| stitch | model/generator.py (stitch_chunks, split_word) | After chunking or stitching changes |
| sizing | quality/font_scale.py, config.py (HEIGHT_*) | After font normalization changes |
| baseline | compose/layout.py, compose/render.py | After baseline detection or descender changes |
| spacing | config.py (WORD_SPACING), compose/render.py | After spacing or layout changes |
| ink_weight | quality/harmonize.py, config.py (STROKE_WEIGHT_*) | After harmonization changes |
| composition | full pipeline (end-to-end) | After any quality-affecting change; uses quality preset |
| hard_words | model/generator.py (generate_word, postprocess) | After generation or gray-box defense changes |

Human review is advisory only. It is not a commit gate and does not modify git hooks.

### Hard words watchlist

`reforge/data/hard_words.json` tracks words that are difficult for the generation
pipeline. Two tiers: **curated** (verified hard words, the regression baseline) and
**candidates** (automatically collected, awaiting triage).

**How candidates are added:**
- Automatically: when the OCR rejection loop in `generate_word()` exhausts retries
  without reaching 0.3 accuracy, the word is appended to candidates
- Human eval: the `hard_words` evaluation type in `make test-human` lets humans flag
  unreadable words; the agent extracts nominations from review notes
- Manually: add entries to the JSON file directly

**Triage workflow:** Run `python -m reforge.data.words triage` to review candidates,
promote them to curated, or dismiss them. This is a manual step.

**Regression test:** `make test-hard` generates every curated word, runs OCR, and
asserts average accuracy > 0.5. Results are recorded to a JSONL ledger at
`tests/medium/hard_words_ledger.jsonl` for tracking improvement over time.

### qpeek (visual inspection tool)

[qpeek](https://github.com/peterzat/qpeek) is installed in the venv for quick visual inspection of output on this headless box. It starts a transient web server, serves the file, and exits when the browser tab closes. Zero dependencies (stdlib only). Wrapper script: `./qpeek.sh <file>`.

Modes: view-only (default), survey with freeform text (`--ask "question"`), survey with button choices (`--ask "question" --choices "a,b,c"`), batch rating (`--batch`). Survey modes print structured JSON to stdout. Binds to `0.0.0.0:2020` by default.

Used by `make test-human` for structured human evaluation via custom HTML mode (`--html`). The human review system serves a multi-step wizard page that collects ratings, A/B picks, and defect flags across 7 evaluation types in a single session.

**When waiting for qpeek review:** The qpeek URL and waiting status must be the **last visible text** in the response. Never bury the URL inside a tool call or follow it with analysis. Format: `**qpeek ready: <url>** -- waiting for your review.` Wait for "qpeek ready" in the output before sharing the URL. When the user says "qpeek <file>", run `./qpeek.sh <file>` immediately via Bash.

## Architecture

```
reforge.py               CLI (argparse) -> calls pipeline.run()
reforge/
  pipeline.py            Orchestration: validate -> preprocess -> encode -> generate -> harmonize -> compose
  preprocess/
    segment.py           Word segmentation (horizontal + vertical projection profiles)
    normalize.py         Per-word deskew, contrast normalization, tensor conversion
  model/
    encoder.py           StyleEncoder: MobileNetV2 backbone -> (5, 1280) raw features
    generator.py         DDIM loop + best-of-N + chunking + stitch + postprocessing
    weights.py           HuggingFace download + state dict loading
  compose/
    layout.py            Line wrapping, baseline detection, paragraph breaks
    render.py            Word compositing onto canvas, upscaling, halo cleanup
  quality/
    score.py             Per-word quality scoring (background, ink, edges, height)
    harmonize.py         Cross-word height + stroke weight harmonization
    font_scale.py        Length-aware font normalization (unified height strategy)
  evaluate/
    visual.py            CV-based quality evaluation (gray boxes, contrast, alignment, etc.)
    compare.py           A/B comparison image generation with labels
  config.py              All constants (charset, DDIM params, paths, presets)
  validation.py          Charset checking + split_paragraphs() / split_words()
  data/
    hard_words.json      Hard words watchlist (curated + candidates)
    words.py             Load/query/triage hard words
  diffusionpen/
    unet.py              UNetModel -- verbatim from DiffusionPen repo (MIT)
    feature_extractor.py ImageEncoder (timm MobileNetV2) -- verbatim from DiffusionPen repo
styles/                  Style reference images (hw-sample.png + future additions)
experiments/
  ab_harness.py          A/B experiment runner with predefined presets
  output/                Generated comparison images (gitignored)
tests/
  quick/                 Component tests, mocked, <10s
  medium/                A/B harness tests, optional GPU, <2min
  full/                  E2E tests, requires GPU + model weights, <10min
  fixtures/              Synthetic test images
docs/
  best-output.png        Current demo output (referenced by README)
  OUTPUT_HISTORY.md      Timestamped archive of demo outputs with metrics
  output-history/        Archived output PNGs (one per make test-full run)
scripts/
  archive-output.sh      Captures output + git state + metrics into history
  human_eval.py          Human evaluation: 8 eval types, qpeek orchestration, staleness check
  human_eval_page.html   Custom HTML wizard template for qpeek --html
  prune_reviews.py       Prune stale review JSON files (dry-run/--apply)
reviews/
  human/                 Human review data
    FINDINGS.md          Durable principles extracted from reviews (committed)
    *.json               Per-session review data (gitignored)
    images/              Generated evaluation images (gitignored)
```

### Data flow

```
style image(s)
  +-- preprocess/segment.py: segment_sentence_image()  ->  list[5 x (1,3,64,256) tensor]
       +-- model/encoder.py: StyleEncoder.encode()  ->  (5, 1280) raw MobileNetV2 features
            |
            +-- model/generator.py: generate_word(word, style_features)
                  |  tokenizer(word) -> text dict -> UNet cross-attn
                  |  style_features -> UNet timestep emb (after reshape+mean+linear)
                  +-- DDIM loop -> VAE decode -> postprocess -> uint8 grayscale ndarray

text input
  +-- validation.split_paragraphs(text)  ->  list[list[str]]
       +-- pipeline inserts None sentinels between paragraphs
            +-- compose/render.py: compose_words([img, img, None, img, ...])  ->  PIL Image "L"  ->  PNG
                  None sentinel = forced line break + paragraph_spacing gap + paragraph_indent
```

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

### Style image requirements

- Exactly 5 words required (hardcoded reshape)
- Each word must be >= 4 chars (IAM training filter: `len > 3`)
- All 5 words should be from the same writer, with consistent pressure and slant
- Default reference sentence: "Quick Brown Foxes Jump High"
- Triplet-loss encoder (default) generalizes better to novel writers

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

These are lessons learned from the penforge predecessor. Each describes a real problem, its root cause, and the design constraint that prevents it.

### Gray box artifacts (multi-layer defense required)

**Problem:** Gray rectangular regions appear around word ink, especially short words.

**Root cause cascade:** DiffusionPen generates dark-gray backgrounds (~150-175) for short words. Fixed thresholds cannot distinguish ink from background. Bicubic upscaling creates interpolation halos around isolated noise pixels.

**Required defense layers:**
1. Adaptive background estimation: 90th-percentile pixel value, ink threshold at 70% of estimate
2. Body-zone anchored noise removal: middle 60% of rows defines "body zone"; columns without sufficient body-zone ink are blanked
3. Isolated-cluster filtering: body-column clusters separated by 20px+ gaps from main cluster are discarded
4. Compositor-level filtering: composite only ink pixels (< 200 threshold) onto canvas
5. Post-upscale halo cleanup: dilate strong-ink mask (~4px radius), blank gray pixels not near dilated ink

**Constraint:** No single threshold or layer suffices. Always test with single-character words ("I", "a") and very short words.

### Word size inconsistency (length-aware normalization)

**Problem:** 1-3 char words render huge (fill the 64x256 canvas), multi-char words render small.

**Root cause:** Area-per-char metric explodes for single-char words.

**Required solution:** Unified height-based normalization:
- Short words (1-3 chars): normalize by ink height (target ~32px)
- Long words (4+ chars): normalize by ink height (target ~35px, slightly higher to account for denser ink)
- Cross-word pass: scale DOWN words >110% of median height, scale UP words <88% of median height (preserve aspect ratio)
- Previous dual strategy (height for short, area for long) created a discontinuity that caused wild height variation on multi-line text

### Stroke weight variation (global harmonization)

**Problem:** Adjacent words look bold/thin inconsistently.

**Root cause:** Per-word contrast stretching independently sets each word's ink range.

**Required solution:** Compute median ink brightness across all words, shift each word's ink to converge on global median. Do this after generation, before composition.

### Long word chunking (score-based syllable splitting)

**Problem:** Words >10 chars need splitting, but naive splits create awkward chunks and visible seams.

**Required solution:**
- Score all split positions: balance (prefer equal chunks) + consonant-cluster penalty (-3 if >= 3 trailing consonants) + boundary bonus (+2 for CC boundary, +1 for CV)
- Each chunk must be >= 4 chars (IAM minimum)
- Normalize chunk heights to median before stitching
- Baseline-aligned stitching (align at bottom, pad shorter chunks at top)
- Overlap blending (8px linear alpha fade) at stitch boundary

### Preprocessing order (per-word operations only after segmentation)

**Problem:** Full-image deskew corrupts adaptive thresholding. Full-image morphological cleanup severs cursive letter connections.

**Root cause:** Rotating gray paper with white border fill creates bright borders. Erode/dilate on full sentence destroys thin strokes between letters.

**Constraint:** On the full sentence image, do only: threshold, tight crop, segmentation. Per-word operations (deskew, morph cleanup, component filtering, contrast normalization) happen after each word is cropped.

### Baseline and descender detection

**Problem:** Looped descenders (g, y) and two-bowl letters fool bottom-up baseline scans.

**Required solution:** Top-down scan from midpoint, looking for density drop below 15% with no body rows below. Walk back to last 35%-density row. Reject spurious dips < 15% of total ink height.

## Style input strategy

### Directory structure

```
styles/
  hw-sample.png          Peter's handwriting (primary reference, committed)
  README.md              Notes on each style source, writer ID, quality observations
  friends/               Contributed samples from other writers
  datasets/              Samples extracted from public handwriting datasets
  synthetic/             DiffusionPen-generated best outputs used as style references
```

### Sourcing plan (incremental)

1. **hw-sample.png** is the primary style. demo.sh always uses it.
2. Friends: gather 3-5 samples from different writers for diversity testing.
3. Public datasets: IAM, RIMES, or other public handwriting corpora. Use high-quality samples as additional test styles.
4. Synthetic: use DiffusionPen's own best-quality outputs (carefully selected, understanding that these are model outputs, not real handwriting) as supplementary style references for testing generalization.
5. All style images should be 5-word sentences with each word >= 4 chars.

## Test strategy

### Three tiers

| Tier | Directory | Runtime | GPU | Purpose |
|------|-----------|---------|-----|---------|
| Quick | `tests/quick/` | <10s | No | Component logic: segmentation, normalization, scoring, harmonization, charset, gray-box detection, syllable splitting, baseline alignment, stroke weight. All models mocked. |
| Medium | `tests/medium/` | <2min | Optional | A/B quality harnesses: generate pairs with different settings, run CV evaluation, assert improvement or non-regression. Skip without GPU. |
| Full | `tests/full/` | <10min | Yes | E2E pipeline: real model weights, real style images, real output. Visual output saved to `tests/full/output/`. Skip without GPU + weights. |

### CV evaluation functions (in `reforge/evaluate/visual.py`)

These let Claude Code "see" results by computing numeric quality metrics:
- `check_gray_boxes(img) -> bool` -- detect rectangular gray artifacts
- `check_ink_contrast(img) -> float` -- ink-to-background contrast ratio
- `check_baseline_alignment(img, word_positions) -> float` -- vertical consistency score
- `check_stroke_weight_consistency(word_imgs) -> float` -- cross-word ink median spread
- `check_word_height_ratio(word_imgs) -> float` -- max/min ink height ratio
- `check_background_cleanliness(img) -> float` -- fraction of non-white non-ink pixels
- `overall_quality_score(img) -> dict` -- composite of all checks

### Autonomous quality loop

The medium tests enable iterative improvement:
1. Claude Code changes a parameter or postprocessing approach
2. Runs medium tests with A/B harness
3. CV evaluation produces numeric comparison
4. If improved: commit. If regressed: revert and try different approach.

This pattern should work without human intervention for parameter tuning and postprocessing refinement.

### pytest markers

```ini
[pytest]
markers =
    quick: component tests, mocked, <10s
    medium: A/B harness tests, optional GPU, <2min
    full: e2e tests, requires GPU + model weights, <10min
    gpu: requires CUDA GPU
```

## Anti-patterns (do NOT do these)

- Do NOT use ImageNet normalization for style images. Use `(pixel/255 - 0.5) / 0.5`.
- Do NOT mean-pool style features before passing to UNet. The UNet does its own reshape + mean internally.
- Do NOT deskew the full sentence image. Only deskew individual word crops.
- Do NOT apply morphological cleanup to the full sentence image. Only per-word.
- Do NOT use `ckpt.pt`. Use `ema_ckpt.pt`.
- Do NOT use a single threshold for gray-box removal. Multi-layer defense is required.
- Do NOT scale UP words during harmonization unless they are below 88% of median height. The undersize threshold prevents excessive height variance while preserving natural proportions for near-median words.
- Do NOT split long words without ensuring each chunk is >= 4 chars.
- Do NOT align stitched chunks at the top. Align at the bottom (baseline).
- Do NOT use fixed background threshold (e.g., 200). Use adaptive 90th-percentile estimation.
- Do NOT override `HF_HOME` per-project. Use the shared cache at `~/.cache/huggingface/`.

## Hardware target

NVIDIA RTX 4000 SFF Ada (20GB VRAM, 6144 CUDA cores, 70W TDP), 64GB RAM, 14-core i5-13500. This comfortably runs DiffusionPen inference and supports rapid A/B experimentation during development.

## Compute strategy

Every operation in the pipeline has a deliberate placement: GPU, CPU, or RAM. Changes that move work between devices should be intentional.

### GPU (CUDA) -- model inference only

These operations run on GPU and must stay there:

| Operation | Module | Why GPU |
|-----------|--------|---------|
| UNet forward pass (DDIM loop) | `model/generator.py` | 100+ forward passes per word, compute-bound |
| VAE decode | `model/generator.py` | Matrix-heavy decode of latents to pixels |
| Style encoding (MobileNetV2) | `model/encoder.py` | Batch of 5 image embeddings |
| Text encoding (Canine-C, inside UNet) | `diffusionpen/unet.py` | Called every DDIM step via cross-attention |

Rules:
- All inference must be wrapped in `torch.no_grad()`. No exceptions.
- Tensors created for inference (latents, noise, contexts) should be created directly on device (`device=` kwarg), not created on CPU and moved.
- Reusable tensors (unconditional CFG context, zero-style features) must be built once and passed through, never rebuilt per call.
- `torch.set_float32_matmul_precision("high")` and `cudnn.benchmark = True` are set at pipeline import for Ada tensor core acceleration.

### CPU (numpy/cv2) -- image processing

These operations run on CPU and should stay there:

| Operation | Module | Why CPU |
|-----------|--------|---------|
| Word segmentation | `preprocess/segment.py` | cv2 connected components, runs once |
| Per-word deskew/normalize | `preprocess/normalize.py` | cv2 rotation/CLAHE on small crops |
| Postprocessing (5 defense layers) | `model/generator.py` | Percentile stats, contour analysis on 64x256 images |
| Font normalization | `quality/font_scale.py` | cv2 resize on small images |
| Stroke/height harmonization | `quality/harmonize.py` | Pixel-level adjustments on small arrays |
| Baseline detection | `compose/layout.py` | Row-density scan on small arrays |
| Canvas compositing | `compose/render.py` | Pixel copy/blend, upscale, halo cleanup |
| CV evaluation | `evaluate/visual.py` | Contour/gradient analysis for quality metrics |
| Quality scoring | `quality/score.py` | Sobel gradients, pixel statistics |

Rationale: These operate on individual word images (64x256, ~16KB each). GPU transfer overhead would exceed compute savings. cv2 and numpy are efficient for this scale.

### RAM -- model weights and tensors

Approximate VRAM budget (float32):
- UNet: ~2.0 GB
- VAE: ~0.7 GB
- Canine-C text encoder (inside UNet): ~0.3 GB
- MobileNetV2 style encoder: ~0.01 GB
- Per-step activations: ~0.5 GB
- **Total: ~3.5 GB of 20 GB** (comfortable headroom)

System RAM is used for:
- Style image loading and segmentation (~5 MB)
- Generated word images in numpy (~50 KB per word, ~2 MB for 40 words)
- Composed canvas (~5-10 MB after upscale)
- HuggingFace model cache on disk (~4 GB at `~/.cache/huggingface/`)

### Device flow

```
style image (disk)
  -> cv2.imread (CPU/RAM)
  -> segment + normalize (CPU)
  -> word_to_tensor (CPU) -> .to(device) in encoder.encode() (GPU)
  -> StyleEncoder.encode() (GPU) -> (5, 1280) features on GPU

text input (CPU)
  -> tokenizer (CPU) -> dict of tensors
  -> .to(device) in ddim_sample() (GPU)

DDIM loop (GPU, under torch.no_grad):
  latents created on GPU
  -> UNet forward (GPU) -> noise prediction
  -> scheduler.step (GPU) -> updated latents
  -> VAE decode (GPU) -> pixel tensor
  -> .cpu().numpy() (transfer to CPU)

postprocessing (CPU):
  -> 5 defense layers (numpy/cv2)
  -> font normalization (cv2)
  -> harmonization (numpy)
  -> composition (numpy/cv2/PIL)
  -> .save() to disk
```

### Testing tiers and compute

| Tier | GPU | Models | What it validates |
|------|-----|--------|-------------------|
| Quick | No | None (pure numpy/cv2) | All CPU-side logic: segmentation, normalization, scoring, harmonization, evaluation |
| Medium | Required | All real weights | GPU inference path, A/B quality comparison |
| Full | Required | All real weights | End-to-end pipeline including composition and disk I/O |

Quick tests must never import torch model code or touch GPU. Medium and full tests skip cleanly when CUDA is unavailable (`@pytest.mark.skipif(not torch.cuda.is_available(), ...)`).

### What NOT to do with compute

- Do NOT move postprocessing to GPU. The images are 64x256 uint8; transfer overhead dominates.
- Do NOT batch multiple words in a single UNet pass. Canvas widths vary (256-320px), making static batching wasteful.
- Do NOT use float16 without testing. The UNet checkpoint was trained in float32; quantization effects on handwriting quality are unknown.
- Do NOT reload models or tokenizers inside per-word loops. Build once, pass through.
- Do NOT create tensors on CPU and then .to(device) when you can pass `device=` at creation.

## Known constraints

- Exactly 5 style images required (UNet hardcoded reshape)
- Each style word must be >= 4 chars (IAM training filter)
- Max ~10 chars per word before chunking (MAX_WORD_LENGTH = 10)
- Charset is 80 chars (no accents, no unicode beyond basic punctuation)
- Output is always grayscale (mode "L")
- IAM training bias: Western handwriting works best; novel styles produce less faithful output
- 70W GPU TDP: good for inference and experimentation, not heavy training
