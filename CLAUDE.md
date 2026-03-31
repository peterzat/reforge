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

## Commands

All commands assume an activated venv. Always use `.venv/bin/python` (or activate first).

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Demo (end-to-end, uses hw-sample.png)
./demo.sh

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
```

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
    font_scale.py        Length-aware font normalization (height vs area strategy)
  evaluate/
    visual.py            CV-based quality evaluation (gray boxes, contrast, alignment, etc.)
    compare.py           A/B comparison image generation with labels
  config.py              All constants (charset, DDIM params, paths, presets)
  validation.py          Charset checking + split_paragraphs() / split_words()
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

**Required solution:** Dual normalization strategy:
- Short words (1-3 chars): normalize by ink height (target ~24px)
- Long words (4+ chars): normalize by area per character (target ~1500 px^2)
- Cross-word pass: scale DOWN words >120% of median height (never scale UP, preserve aspect ratio)

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
- Do NOT scale UP small words during harmonization. Only scale down outliers.
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
