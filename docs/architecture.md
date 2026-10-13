# Architecture

Moved from CLAUDE.md on 2026-10-13 and brought up to date with the code.

## Module map

```
reforge.py               CLI (argparse, --seed) -> pipeline.run()
reforge/
  pipeline.py            run(): validate -> preprocess -> encode -> generate ->
                         postprocess_words() -> compose -> evaluate -> manifest
                         postprocess_words(): the single definition of the
                         sizing + harmonization stage graph
  preprocess/
    segment.py           Word segmentation (horizontal + vertical projection profiles)
    normalize.py         Per-word deskew, contrast normalization, tensor conversion
  model/
    encoder.py           StyleEncoder: MobileNetV2 backbone -> (5, 1280) raw features
    generator.py         DDIM loop, best-of-N, OCR retry, chunking + stitch,
                         contraction split + stitch, trailing-mark synthesis,
                         5-layer gray-box postprocessing
    font_glyph.py        Caveat TTF trailing marks, dilated to Bezier stroke width
    weights.py           HuggingFace download + state dict loading
  compose/
    layout.py            Line wrapping, word-aware baseline detection, paragraph breaks
    render.py            Word compositing on detected baselines, upscale, halo cleanup
  quality/
    score.py             Per-candidate quality scoring (background, ink, edges, height)
    harmonize.py         Stroke width + ink weight harmonization (height passes are
                         legacy; folded into font_scale for SIZING_POLICY="total_height")
    font_scale.py        Word sizing: zone_class, estimate_x_height, plan_word_scales,
                         size_words (one resample per word)
    ink_metrics.py       Shared ink height / x-height measurement
  evaluate/
    visual.py            CV quality metrics and overall_quality_score
    regression_gate.py   Pure-python gate logic (strict primary metrics, OCR floor)
    ocr.py               Word reading: TrOCR-small (CPU) or REFORGE_OCR_BACKEND=vlm
    vlm.py               Stdlib client for a local vision-language model server
    ledger.py            JSONL quality ledger + drift detection
    experiments.py       docs/experiment-log.jsonl (expected vs. observed)
    reference.py         SSIM against reference images
    compare.py           A/B comparison image generation with labels
    diagnostic.py        Word clipping / descender diagnostics
  config.py              All constants (charset, DDIM params, sizing policy, gate)
  validation.py          Charset checking + split_paragraphs() / split_words()
  data/
    hard_words.json      Hard words watchlist (curated + candidates)
    words.py             Load/query/triage hard words
  diffusionpen/
    unet.py              UNetModel, verbatim from the DiffusionPen repo (MIT)
    feature_extractor.py ImageEncoder (timm MobileNetV2), verbatim
styles/                  Style reference images (hw-sample.png)
fonts/                   Caveat (OFL) for trailing marks
experiments/             A/B harness, sweeps, replay_cache.py (cache generations,
                         replay downstream stages), cv_bench/ (instrument benchmarks)
tests/                   quick/ (CPU, mocked), medium/ (GPU, gate + A/B), full/ (e2e)
docs/                    Design docs, analyses, output history, this file
scripts/                 human_eval.py, metric_correlation.py, findings_sweep.py,
                         archive-output.sh, prune_reviews.py, vlm_server.sh, analyses
reviews/human/           Review JSONs (tracked ground truth), FINDINGS.md,
                         images/ (local only)
```

## Data flow

```
style image(s)
  +-- preprocess/segment.py: segment_sentence_image()  ->  5 word crops
       +-- model/encoder.py: StyleEncoder.encode()  ->  (5, 1280) raw MobileNetV2 features
            |
            +-- model/generator.py: generate_word(word, style_features)
                  |  trailing marks split off -> recurse on base word -> attach marks
                  |  contraction -> generate halves -> match short half -> stitch on baselines
                  |  >10 chars -> syllable chunks -> cross-correlation stitch
                  |  tokenizer(word) -> text dict -> UNet cross-attn
                  |  style_features -> UNet timestep emb (after reshape+mean+linear)
                  +-- DDIM loop -> VAE decode -> postprocess -> best-of-N -> OCR retry
                       -> uint8 grayscale ndarray (DiffusionPen fills the 64px canvas)

text input
  +-- validation.split_paragraphs(text)  ->  list[list[str]]
       +-- pipeline inserts None sentinels between paragraphs
            +-- pipeline.postprocess_words(): size_words (zone x-height sizing, one
            |   resample) -> harmonize_stroke_width -> harmonize_stroke_weight
            +-- compose/render.py: compose_words([img, img, None, img, ...])
                  each word's detected baseline row lands on the line's ruled baseline
                  None sentinel = forced line break + paragraph_spacing + paragraph_indent
                  -> PIL Image "L" -> PNG + <name>.json run manifest
```
