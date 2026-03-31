## Spec -- 2026-03-31 -- Scaffold reforge repo with full pipeline and demo

**Goal:** Set up the reforge repository with complete directory structure, port all pipeline code from penforge with every hard-won fix baked in, establish the three-tier test infrastructure, build the CV evaluation module, and deliver a working `demo.sh` that generates a handwritten note from `hw-sample.png`.

### Acceptance Criteria

- [ ] Repository structure matches the architecture in CLAUDE.md (all directories and module files exist)
- [ ] `requirements.txt` pins versions for: torch, diffusers, transformers, Pillow, opencv-python, scipy, numpy, tqdm, huggingface-hub, timm, pytest
- [ ] `.gitignore` covers `.venv/`, `__pycache__/`, `*.pyc`, `experiments/output/`, `tests/*/output/`, `result.png`
- [ ] `hw-sample.png` is committed in `styles/` and contains a 5-word handwritten sentence (each word >= 4 chars)
- [ ] `diffusionpen/unet.py` and `diffusionpen/feature_extractor.py` are ported verbatim from DiffusionPen (MIT license)
- [ ] Style preprocessing correctly segments a sentence photo into 5 word tensors of shape `(1, 3, 64, 256)` in range `[-1, 1]`, using per-word deskew and contrast normalization (not full-image deskew or full-image morph cleanup)
- [ ] StyleEncoder returns `(5, 1280)` raw MobileNetV2 features without mean-pooling
- [ ] Generator implements DDIM sampling with CFG (default scale 3.0), best-of-N candidate selection, and adaptive canvas width up to 320px
- [ ] Long words (>10 chars) are split using score-based syllable splitting (balance + consonant penalty + boundary bonus), with each chunk >= 4 chars, chunk heights normalized, and baseline-aligned overlap blending
- [ ] Postprocessing implements all five gray-box defense layers: adaptive background estimation, body-zone noise removal, isolated-cluster filtering, compositor ink-only compositing, and post-upscale halo cleanup
- [ ] Font normalization uses dual strategy: height-based for 1-3 char words, area-based for 4+ char words
- [ ] Cross-word harmonization adjusts stroke weight (shift to global median) and height (scale down outliers >120% of median, never scale up)
- [ ] Compositor detects baselines accounting for thin and looped descenders, aligns words on shared baseline, and supports paragraph breaks via None sentinels
- [ ] State dict loading strips both `module.` prefixes from DataParallel-wrapped checkpoint keys
- [ ] `python -m pytest tests/quick/ -x -q` passes in under 10 seconds with no GPU or model weights required
- [ ] Quick tests cover at minimum: word segmentation (correct count + reading order), tensor shape/range, quality scoring (range 0-1), syllable splitting (correct chunks for "handwriting"), gray-box detection on synthetic images, baseline alignment, stroke weight convergence, height harmonization, charset validation
- [ ] `tests/medium/` contains at least one A/B harness test (marked `medium`, skips without GPU) that generates two variants and compares them via CV evaluation
- [ ] `tests/full/` contains at least one e2e test (marked `full`, skips without model weights) that runs the pipeline and saves visual output
- [ ] `pytest.ini` defines markers: `quick`, `medium`, `full`, `gpu`
- [ ] `reforge/evaluate/visual.py` implements `check_gray_boxes`, `check_ink_contrast`, `check_baseline_alignment`, `check_stroke_weight_consistency`, `check_word_height_ratio`, `check_background_cleanliness`, and `overall_quality_score`, each returning numeric scores from numpy array inputs
- [ ] Quick tests verify each CV evaluation function against synthetic test images (known-good and known-bad cases)
- [ ] `experiments/ab_harness.py` supports at least 4 preset experiments (cfg, scheduler, postprocess, combined) and generates labeled comparison PNGs
- [ ] `./demo.sh` on a fresh clone: creates venv, installs deps, downloads models, generates `result.png` from `hw-sample.png` with a multi-paragraph note (>= 2 paragraphs, >= 30 words total)
- [ ] `demo.sh` prints quality metrics from the CV evaluation module after generation
- [ ] `demo.sh` exits 0 only if output file exists, dimensions > 100x100, and file size > 10KB
- [ ] `demo.sh` completes in under 5 minutes on a machine with cached models and GPU
- [ ] CLAUDE.md is complete per the provided template (commands, architecture, data flow, constraints, anti-patterns)

### Context

This is a from-scratch repo, but the pipeline code is a port from the penforge project. Every design constraint in CLAUDE.md's "Hard-won design constraints" section represents a real bug that took multiple commits to fix. These are not optional enhancements; they are the minimum bar for a functional pipeline.

The `diffusionpen/` files (unet.py, feature_extractor.py) are copied verbatim from the DiffusionPen repository under MIT license. Do not modify them.

The CV evaluation module is not a nice-to-have. It is the mechanism by which future development iterations can be autonomously validated. Without it, every quality change requires manual visual inspection, which breaks the autonomous improvement loop.

The A/B harness presets should sweep:
- **cfg**: guidance_scale values (1.0, 3.0, 5.0, 7.5)
- **scheduler**: DDIM vs DPM++ vs UniPC at equal steps
- **postprocess**: soft sigmoid vs hard threshold
- **combined**: baseline (CFG=1.0, DDIM, 50 steps, hard) vs tuned (CFG=3.0, DPM++, 25 steps, soft)

Model weights are downloaded from HuggingFace on first run and cached at `~/.cache/huggingface/` (shared cache, do not override HF_HOME). The project-specific cache dir for any non-HF artifacts is `~/.cache/reforge/`.

Target hardware: NVIDIA RTX 4000 SFF Ada (20GB VRAM), 64GB RAM. Demo settings should use quality preset (50 steps, 3 candidates) since this machine handles it comfortably.

demo.sh text should be something readable and representative, 2-3 paragraphs, 30-50 words, using only characters from the 80-char charset. Avoid characters not in charset (no em-dashes, curly quotes, etc.).

<!-- SPEC_META: {"date":"2026-03-31","title":"Scaffold reforge repo with full pipeline and demo","criteria_total":26,"criteria_met":0} -->
