# Compute strategy

Moved from CLAUDE.md on 2026-10-13; CLAUDE.md keeps the rules, this file keeps
the rationale and tables.

## Hardware target

NVIDIA RTX 4000 SFF Ada (20GB VRAM, 6144 CUDA cores, 70W TDP), 64GB RAM,
14-core i5-13500. This comfortably runs DiffusionPen inference and supports
rapid A/B experimentation during development.

The GPU is shared. As of 2026-10-13 the daydream project's production vLLM
server holds ~9 GB and ComfyUI can claim 6-12 GB while rendering, so assume
~11 GB free, not 20. Reforge needs ~3.5 GB.

Every operation in the pipeline has a deliberate placement: GPU, CPU, or RAM.
Changes that move work between devices should be intentional.

## GPU (CUDA): model inference only

These operations run on GPU and must stay there:

| Operation | Module | Why GPU |
|-----------|--------|---------|
| UNet forward pass (DDIM loop) | `model/generator.py` | 100+ forward passes per word, compute-bound |
| VAE decode | `model/generator.py` | Matrix-heavy decode of latents to pixels |
| Style encoding (MobileNetV2) | `model/encoder.py` | Batch of 5 image embeddings |
| Text encoding (Canine-C, inside UNet) | `diffusionpen/unet.py` | Called every DDIM step via cross-attention |

Rules:
- All inference must be wrapped in `torch.no_grad()`. No exceptions.
- Tensors created for inference (latents, noise, contexts) should be created
  directly on device (`device=` kwarg), not created on CPU and moved.
- Reusable tensors (unconditional CFG context, zero-style features) must be
  built once and passed through, never rebuilt per call. (Audit 2026-10-13:
  `ddim_sample` still moves the unconditional context to the device and
  rebuilds `zero_style` and the `DDIMScheduler` per call; performance only.)
- `pipeline.run()` sets `torch.set_float32_matmul_precision("high")` and, for
  unseeded runs, `cudnn.benchmark = True` for Ada tensor cores, and restores
  the previous values when generation ends. Seeded runs use deterministic
  cuDNN. These were set at import until 2026-10-13, which changed numerics
  for every later test in the same pytest process.

## CPU (numpy/cv2): image processing

| Operation | Module | Why CPU |
|-----------|--------|---------|
| Word segmentation | `preprocess/segment.py` | cv2 connected components, runs once |
| Per-word deskew/normalize | `preprocess/normalize.py` | cv2 rotation/CLAHE on small crops |
| Postprocessing (5 defense layers) | `model/generator.py` | Percentile stats, contour analysis on 64x256 images |
| Word sizing | `quality/font_scale.py` | One cv2 resize per word |
| Stroke/weight harmonization | `quality/harmonize.py` | Pixel-level adjustments on small arrays |
| Baseline detection | `compose/layout.py` | Row-density scan on small arrays |
| Canvas compositing | `compose/render.py` | Pixel copy/blend, upscale, halo cleanup |
| CV evaluation | `evaluate/visual.py` | Contour/gradient analysis for quality metrics |
| Quality scoring | `quality/score.py` | Sobel gradients, pixel statistics |
| OCR (TrOCR-small) | `evaluate/ocr.py` | Runs on CPU so it never competes with generation |

Rationale: these operate on individual word images (64x256, ~16KB each). GPU
transfer overhead would exceed compute savings.

## RAM: model weights and tensors

Approximate VRAM budget (float32):
- UNet: ~2.0 GB
- VAE: ~0.7 GB
- Canine-C text encoder (inside UNet): ~0.3 GB
- MobileNetV2 style encoder: ~0.01 GB
- Per-step activations: ~0.5 GB
- **Total: ~3.5 GB**

System RAM is used for style image loading and segmentation (~5 MB),
generated word images (~50 KB per word), the composed canvas (~5-10 MB after
upscale), and the HuggingFace model cache on disk (~4 GB at
`~/.cache/huggingface/`).

## Device flow

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
  -> sizing: one resample per word (cv2)
  -> harmonization (numpy)
  -> composition (numpy/cv2/PIL)
  -> .save() to disk, plus the run manifest JSON
```

## Testing tiers and compute

| Tier | GPU | Models | What it validates |
|------|-----|--------|-------------------|
| Quick | No | None (pure numpy/cv2) | All CPU-side logic |
| Medium | Required | All real weights | GPU inference path, A/B quality comparison, regression gate |
| Full | Required | All real weights | End-to-end pipeline including composition and disk I/O |

Quick tests must never load model weights or touch the GPU. Medium and full
tests skip cleanly when CUDA is unavailable.

## What not to do with compute

- Do NOT move postprocessing to GPU. The images are 64x256 uint8; transfer
  overhead dominates.
- Do NOT batch multiple words in a single UNet pass. Canvas widths vary
  (256-320px), making static batching wasteful.
- Do NOT use float16 without testing. The UNet checkpoint was trained in
  float32; quantization effects on handwriting quality are unknown.
- Do NOT reload models or tokenizers inside per-word loops. Build once, pass
  through.
- Do NOT create tensors on CPU and then .to(device) when you can pass
  `device=` at creation.
- Do NOT set global torch numerics at module import.
