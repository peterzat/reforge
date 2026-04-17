"""Human evaluation system for reforge quality assessment.

Generates test images for 9 evaluation types, presents them via qpeek's
--html mode as a single-page wizard, captures structured JSON responses,
and persists review data.

Evaluation types:
    candidate   -- Best-of-N candidate selection calibration (B1)
    stitch      -- Chunk stitching overlap comparison (B2)
    sizing      -- Short vs long word size consistency (B3)
    baseline    -- Baseline alignment with descenders (B4)
    spacing     -- Word spacing and jitter comparison (B5)
    ink_weight  -- Stroke weight consistency comparison (B6)
    composition -- Full two-paragraph composition rating (B7)
    hard_words  -- Curated hard words readability check (D2)
    punctuation -- Punctuation rendering readability check

Review JSON schema (saved to reviews/human/YYYY-MM-DD_HHMMSS.json):
    {
        "version": 1,
        "timestamp": "2026-04-02T14:30:00",
        "commit": "<short hash>",
        "pipeline_checksums": {"<path>": "sha256:<hex>", ...},
        "evaluations": {
            "<eval_type>": {
                "skipped": false,
                <type-specific fields>,
                "notes": ""
            }, ...
        },
        "cv_metrics": {<overall_quality_score output>}
    }

Usage:
    python scripts/human_eval.py                          # all 7 types
    python scripts/human_eval.py --eval candidate,stitch  # subset
    python scripts/human_eval.py --device cpu              # force CPU
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PIPELINE_FILES = [
    "reforge/model/generator.py",
    "reforge/compose/layout.py",
    "reforge/compose/render.py",
    "reforge/quality/harmonize.py",
    "reforge/quality/font_scale.py",
    "reforge/quality/score.py",
    "reforge/config.py",
    "reforge/evaluate/visual.py",
    "reforge/evaluate/compare.py",
    "reforge/evaluate/ocr.py",
]

EVAL_TYPES = [
    "candidate", "stitch", "sizing", "baseline",
    "spacing", "ink_weight", "composition", "hard_words",
    "punctuation",
]

STYLE_PATH = "styles/hw-sample.png"
REVIEW_DIR = "reviews/human"
IMAGE_DIR = os.path.join(REVIEW_DIR, "images")
FINDINGS_PATH = os.path.join(REVIEW_DIR, "FINDINGS.md")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def compute_pipeline_checksums() -> dict[str, str]:
    """SHA256 of each tracked pipeline file."""
    checksums = {}
    for path in PIPELINE_FILES:
        full = os.path.join(PROJECT_ROOT, path)
        if os.path.exists(full):
            h = hashlib.sha256(open(full, "rb").read()).hexdigest()
            checksums[path] = f"sha256:{h}"
        else:
            checksums[path] = "missing"
    return checksums


def get_commit_hash() -> str:
    """Current git HEAD short hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def check_staleness() -> tuple[bool, str]:
    """Check if newest review is stale relative to current pipeline files.

    Returns (is_stale, reason).
    """
    if not os.path.isdir(REVIEW_DIR):
        return True, "No reviews directory"

    reviews = sorted([
        f for f in os.listdir(REVIEW_DIR)
        if f.endswith(".json") and not f.startswith(".")
    ])
    if not reviews:
        return True, "No reviews found"

    newest = os.path.join(REVIEW_DIR, reviews[-1])
    try:
        with open(newest) as f:
            review = json.load(f)
    except (json.JSONDecodeError, OSError):
        return True, f"Cannot read newest review: {reviews[-1]}"

    current = compute_pipeline_checksums()
    saved = review.get("pipeline_checksums", {})

    changed = [p for p, h in current.items() if saved.get(p) != h]
    if changed:
        return True, f"{len(changed)} pipeline file(s) changed since last review"
    return False, ""


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def load_models(device: str):
    """Load all models for generation. Returns a dict of model components.

    Follows the same loading pattern as pipeline.py and medium test conftest.
    """
    import torch
    from reforge.model.encoder import StyleEncoder
    from reforge.model.weights import (
        download_style_encoder_weights,
        download_unet_weights,
        load_tokenizer,
        load_unet,
        load_vae,
    )
    from reforge.preprocess.normalize import preprocess_words
    from reforge.preprocess.segment import segment_sentence_image

    style_img = cv2.imread(STYLE_PATH, cv2.IMREAD_GRAYSCALE)
    if style_img is None:
        raise FileNotFoundError(f"Cannot read style image: {STYLE_PATH}")
    word_imgs_raw = segment_sentence_image(style_img)
    assert len(word_imgs_raw) == 5, f"Expected 5 style words, got {len(word_imgs_raw)}"

    style_tensors = preprocess_words(word_imgs_raw)
    style_ckpt = download_style_encoder_weights()
    encoder = StyleEncoder(checkpoint_path=style_ckpt).to(device)
    style_features = encoder.encode(style_tensors)

    unet_ckpt = download_unet_weights()
    unet = load_unet(unet_ckpt, device=device)
    vae = load_vae(device=device)
    tokenizer = load_tokenizer()

    uncond_context = tokenizer(" ", return_tensors="pt", padding="max_length", max_length=16)

    return {
        "unet": unet,
        "vae": vae,
        "tokenizer": tokenizer,
        "style_features": style_features,
        "uncond_context": uncond_context,
        "style_word_images": word_imgs_raw,
        "device": device,
    }


# ---------------------------------------------------------------------------
# Per-word generation helper
# ---------------------------------------------------------------------------

def _generate_single_word(word, models, num_steps=20, guidance_scale=3.0):
    """Generate a single word image (1 candidate, no best-of-N)."""
    from reforge.model.generator import (
        compute_canvas_width,
        ddim_sample,
        postprocess_word,
    )

    canvas_width = compute_canvas_width(len(word))
    text_ctx = models["tokenizer"](
        word, return_tensors="pt", padding="max_length", max_length=16,
    )
    img = ddim_sample(
        models["unet"], models["vae"], text_ctx, models["style_features"],
        uncond_context=models["uncond_context"],
        canvas_width=canvas_width,
        num_steps=num_steps,
        guidance_scale=guidance_scale,
        device=models["device"],
    )
    return postprocess_word(img)


def _generate_words(words, models, num_steps=20, guidance_scale=3.0):
    """Generate multiple word images with font normalization."""
    from reforge.quality.font_scale import normalize_font_size

    images = []
    for w in words:
        img = _generate_single_word(w, models, num_steps, guidance_scale)
        img = normalize_font_size(img, w)
        images.append(img)
    return images


# ---------------------------------------------------------------------------
# Evaluation type generators
# ---------------------------------------------------------------------------

def generate_candidate_eval(models, output_dir):
    """B1: Generate 5 candidates for a word, record quality_score ranking."""
    import datetime

    import torch

    from reforge.config import PRESET_QUALITY
    from reforge.evaluate.compare import create_comparison_image
    from reforge.model.generator import _log_candidate_scores
    from reforge.quality.score import quality_score_breakdown

    word = "garden"
    steps = PRESET_QUALITY["steps"]
    guidance = PRESET_QUALITY["guidance_scale"]

    # Deterministic seed so the candidate log can be joined to the review.
    seed = 137
    torch.manual_seed(seed)

    timestamp = datetime.datetime.now().isoformat(timespec="seconds")

    candidates = []
    log_rows = []
    for i in range(5):
        img = _generate_single_word(word, models, num_steps=steps, guidance_scale=guidance)
        score, sub_scores = quality_score_breakdown(img)
        label = chr(65 + i)  # A, B, C, D, E
        candidates.append({"label": label, "image": img, "quality_score": round(score, 4)})
        row_sub = {k: round(float(v), 4) for k, v in sub_scores.items()}
        log_rows.append({"index": i, "sub_scores": row_sub, "total": round(float(score), 4)})

    # Which candidate does quality_score pick?
    best_idx = max(range(len(candidates)), key=lambda i: candidates[i]["quality_score"])
    quality_pick = candidates[best_idx]["label"]

    # Append to the candidate log whenever logging is enabled; this is the
    # join-side record that the review wizard's human pick can be matched to.
    if os.environ.get("REFORGE_LOG_CANDIDATES", "") == "1":
        _log_candidate_scores(word, log_rows, best_idx, timestamp=timestamp)

    # Build comparison image
    comparison = create_comparison_image(
        [c["image"] for c in candidates],
        [f"{c['label']} (score: {c['quality_score']:.3f})" for c in candidates],
        title=f'Candidate selection: "{word}"',
    )
    comp_path = os.path.join(output_dir, "candidate_comparison.png")
    comparison.save(comp_path)

    return {
        "type": "candidate",
        "word": word,
        "seed": seed,
        "log_timestamp": timestamp,
        "comparison_image": comp_path,
        "candidates": [{"label": c["label"], "quality_score": c["quality_score"]} for c in candidates],
        "quality_score_pick": quality_pick,
    }


def _measure_ink_height(img: np.ndarray, threshold: int = 180) -> int:
    """Measure the ink height (vertical extent of ink pixels) in a word image."""
    ink_rows = np.any(img < threshold, axis=1)
    if not np.any(ink_rows):
        return 0
    first = int(np.argmax(ink_rows))
    last = len(ink_rows) - 1 - int(np.argmax(ink_rows[::-1]))
    return last - first + 1


def _normalize_chunks_to_same_height(chunk_images: list[np.ndarray]) -> list[np.ndarray]:
    """Normalize chunk images so all have the same ink height.

    Uses median ink height as the target. Returns copies; does not
    modify the input list.
    """
    heights = [_measure_ink_height(c) for c in chunk_images]
    valid = [h for h in heights if h > 0]
    if not valid:
        return list(chunk_images)
    target_h = int(np.median(valid))
    if target_h < 4:
        return list(chunk_images)

    normalized = []
    for i, chunk in enumerate(chunk_images):
        if heights[i] > 0 and heights[i] != target_h:
            scale = target_h / heights[i]
            new_h = max(1, int(chunk.shape[0] * scale))
            new_w = max(1, int(chunk.shape[1] * scale))
            chunk = cv2.resize(chunk, (new_w, new_h), interpolation=cv2.INTER_AREA)
        normalized.append(chunk)
    return normalized


def generate_stitch_eval(models, output_dir):
    """B2: Generate a long word with different STITCH_OVERLAP_PX values.

    stitch_chunks() handles x-height normalization and baseline alignment
    internally (cross-correlation alignment since 2026-04-14). We record
    chunk heights for the label but do not pre-normalize, which was found
    to interfere with the internal baseline alignment.
    """
    from reforge.evaluate.compare import create_comparison_image
    from reforge.model.generator import (
        compute_canvas_width,
        ddim_sample,
        postprocess_word,
        split_long_word,
        stitch_chunks,
    )

    word = "understanding"
    chunks = split_long_word(word)

    # Generate chunk images once
    chunk_images = []
    for chunk in chunks:
        canvas_width = compute_canvas_width(len(chunk))
        text_ctx = models["tokenizer"](
            chunk, return_tensors="pt", padding="max_length", max_length=16,
        )
        img = ddim_sample(
            models["unet"], models["vae"], text_ctx, models["style_features"],
            uncond_context=models["uncond_context"],
            canvas_width=canvas_width,
            num_steps=20, guidance_scale=3.0,
            device=models["device"],
        )
        img = postprocess_word(img)
        chunk_images.append(img)

    # D2: Record raw chunk heights for the label (diagnostic only)
    raw_heights = [_measure_ink_height(c) for c in chunk_images]
    height_note = "Raw heights: " + ", ".join(
        f"{chunks[i]} {raw_heights[i]}px" for i in range(len(chunks))
    )

    # Stitch with different overlap values (stitch_chunks normalizes internally)
    overlaps = [4, 8, 12, 16]
    stitched = []
    for overlap in overlaps:
        with patch("reforge.model.generator.STITCH_OVERLAP_PX", overlap):
            result = stitch_chunks(list(chunk_images))
        stitched.append(result)

    comparison = create_comparison_image(
        stitched,
        [f"Overlap: {o}px" for o in overlaps],
        title=f'Chunk stitching: "{word}" ({" + ".join(chunks)})\n{height_note}',
    )
    comp_path = os.path.join(output_dir, "stitch_comparison.png")
    comparison.save(comp_path)

    return {
        "type": "stitch",
        "word": word,
        "chunks": chunks,
        "overlaps": overlaps,
        "raw_heights": raw_heights,
        "comparison_image": comp_path,
    }


def generate_sizing_eval(models, output_dir):
    """B3: Generate multi-char words of varied length on a single line.

    Tests whether the font normalization pipeline produces consistent
    sizing across words of different lengths (all >= 3 chars). Does not
    include single-char words, which are a Plateaued DiffusionPen
    limitation tracked separately in FINDINGS.md.
    """
    from reforge.compose.render import compose_words
    from reforge.quality.harmonize import harmonize_words

    words = ["the", "quick", "something"]
    word_images = _generate_words(words, models)
    word_images = harmonize_words(word_images)

    composed, positions = compose_words(
        word_images, words, page_width=600,
        return_positions=True, page_ratio="fixed",
    )
    comp_path = os.path.join(output_dir, "sizing_composed.png")
    composed.save(comp_path)

    return {
        "type": "sizing",
        "words": words,
        "comparison_image": comp_path,
    }


def generate_baseline_eval(models, output_dir):
    """B4: Generate a phrase with descenders for baseline alignment check."""
    from reforge.compose.render import compose_words
    from reforge.quality.harmonize import harmonize_words

    words = ["jumping", "quickly", "beyond", "gray", "fences"]
    word_images = _generate_words(words, models)
    word_images = harmonize_words(word_images)

    composed, positions = compose_words(
        word_images, words, page_width=800,
        return_positions=True, page_ratio="fixed",
    )
    comp_path = os.path.join(output_dir, "baseline_composed.png")
    composed.save(comp_path)

    return {
        "type": "baseline",
        "words": words,
        "comparison_image": comp_path,
    }


def generate_spacing_eval(models, output_dir):
    """B5: Same phrase composed with two different WORD_SPACING values."""
    from reforge.compose.render import compose_words
    from reforge.evaluate.compare import create_comparison_image
    from reforge.quality.harmonize import harmonize_words

    words = ["bright", "morning", "light", "through", "windows"]
    word_images = _generate_words(words, models)
    word_images = harmonize_words(word_images)

    from reforge.config import WORD_SPACING as current_spacing
    half_spacing = max(1, current_spacing // 2)
    configs = [
        (f"A: Current ({current_spacing}px)", current_spacing),
        (f"B: Tighter ({half_spacing}px)", half_spacing),
    ]
    composed_images = []
    for label, spacing in configs:
        with patch("reforge.compose.layout.WORD_SPACING", spacing):
            composed = compose_words(
                list(word_images), list(words),
                page_width=800, page_ratio="fixed",
            )
        composed_images.append(np.array(composed))

    comparison = create_comparison_image(
        composed_images,
        [c[0] for c in configs],
        title="Word spacing comparison",
    )
    comp_path = os.path.join(output_dir, "spacing_comparison.png")
    comparison.save(comp_path)

    return {
        "type": "spacing",
        "words": words,
        "configs": [{"label": c[0], "spacing_px": c[1]} for c in configs],
        "comparison_image": comp_path,
    }


def generate_ink_weight_eval(models, output_dir):
    """B6: Same phrase with two stroke weight harmonization strengths."""
    from reforge.compose.render import compose_words
    from reforge.config import STROKE_WEIGHT_SHIFT_STRENGTH
    from reforge.evaluate.compare import create_comparison_image
    from reforge.quality.harmonize import harmonize_words

    words = ["Quick", "brown", "foxes", "jump", "high"]
    word_images = _generate_words(words, models)

    configs = [
        (f"A: Current ({STROKE_WEIGHT_SHIFT_STRENGTH})", STROKE_WEIGHT_SHIFT_STRENGTH),
        (f"B: Reduced ({STROKE_WEIGHT_SHIFT_STRENGTH - 0.22:.2f})", STROKE_WEIGHT_SHIFT_STRENGTH - 0.22),
    ]
    composed_images = []
    for label, strength in configs:
        with patch("reforge.quality.harmonize.STROKE_WEIGHT_SHIFT_STRENGTH", strength):
            harmonized = harmonize_words(list(word_images))
        composed = compose_words(
            harmonized, list(words),
            page_width=800, page_ratio="fixed",
        )
        composed_images.append(np.array(composed))

    comparison = create_comparison_image(
        composed_images,
        [c[0] for c in configs],
        title="Ink weight consistency comparison",
    )
    comp_path = os.path.join(output_dir, "ink_weight_comparison.png")
    comparison.save(comp_path)

    return {
        "type": "ink_weight",
        "words": words,
        "configs": [{"label": c[0], "strength": c[1]} for c in configs],
        "comparison_image": comp_path,
    }


def generate_composition_eval(models, output_dir):
    """B7: Full two-paragraph composition with CV metrics.

    Generation is scoped-deterministic: seeds torch and numpy per run, disables
    cudnn.benchmark for the eval path only (restored on exit), and runs three
    seeds (matching the test_quality_regression set). The seed whose
    overall_quality_score is the median of the three is promoted to
    composition_full.png for human display; all three are archived under
    images/archive/ so historical runs can be diffed visually.
    """
    import shutil

    import numpy as np
    import torch

    from reforge.config import PRESET_QUALITY
    from reforge.pipeline import run

    # Use the same text as demo.sh so known issues (e.g. "noon" -> "no") surface
    text = (
        "I can't remember exactly, but it was a Thursday; the bakery on "
        "Birchwood had croissants so perfect they'd disappear by noon.\n"
        "We grabbed two, maybe three? Katherine laughed and said something "
        "wonderful about mornings being too beautiful for ordinary breakfast."
    )
    preset = PRESET_QUALITY
    seeds = [42, 137, 2718]

    # Scope CUDA determinism to the eval path: pipeline.py sets
    # cudnn.benchmark=True for speed in production, but benchmark-mode CUDA
    # picks algorithms based on current GPU state, which leaks non-determinism
    # into sampling. We snapshot and restore so the pipeline reverts after.
    saved_benchmark = torch.backends.cudnn.benchmark
    saved_deterministic = torch.backends.cudnn.deterministic
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True

    archive_dir = os.path.join(output_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    try:
        per_seed = []
        for seed in seeds:
            torch.manual_seed(seed)
            np.random.seed(seed)
            seed_path = os.path.join(output_dir, f"composition_full_seed{seed}.png")
            result = run(
                style_path=STYLE_PATH,
                text=text,
                output_path=seed_path,
                num_steps=preset["steps"],
                guidance_scale=preset["guidance_scale"],
                num_candidates=preset["candidates"],
                device=models["device"],
                verbose=False,
            )
            archive_path = os.path.join(
                archive_dir, f"{timestamp}_seed{seed}_composition.png"
            )
            shutil.copy(seed_path, archive_path)
            per_seed.append({
                "seed": seed,
                "image_path": seed_path,
                "archive_path": archive_path,
                "cv_metrics": result["quality_scores"],
            })
    finally:
        torch.backends.cudnn.benchmark = saved_benchmark
        torch.backends.cudnn.deterministic = saved_deterministic

    sorted_by_overall = sorted(per_seed, key=lambda e: e["cv_metrics"].get("overall", 0.0))
    median_entry = sorted_by_overall[len(sorted_by_overall) // 2]

    out_path = os.path.join(output_dir, "composition_full.png")
    shutil.copy(median_entry["image_path"], out_path)

    per_seed_cv = {str(entry["seed"]): entry["cv_metrics"] for entry in per_seed}

    return {
        "type": "composition",
        "preset": "quality",
        "preset_params": preset,
        "text": text,
        "comparison_image": out_path,
        "cv_metrics": median_entry["cv_metrics"],
        "per_seed_cv": per_seed_cv,
        "selected_seed": median_entry["seed"],
    }


def generate_hard_words_eval(models, output_dir):
    """D2: Generate curated hard words for human readability review."""
    import random

    from reforge.data.words import load_hard_words
    from reforge.evaluate.compare import create_comparison_image
    from reforge.evaluate.ocr import ocr_accuracy
    from reforge.quality.score import quality_score

    all_words = load_hard_words()
    # Pick 8 words, mixing categories: some short, some confusable, some chunking
    rng = random.Random(42)
    sample = rng.sample(all_words, min(8, len(all_words)))

    word_images = []
    word_meta = []
    for word in sample:
        img = _generate_single_word(word, models, num_steps=20, guidance_scale=3.0)
        acc = ocr_accuracy(img, word)
        score = quality_score(img)
        word_images.append(img)
        word_meta.append({
            "word": word,
            "ocr_accuracy": round(acc, 4),
            "quality_score": round(score, 4),
        })

    comparison = create_comparison_image(
        word_images,
        [f'{m["word"]} (OCR: {m["ocr_accuracy"]:.2f})' for m in word_meta],
        title="Hard words readability check",
    )
    comp_path = os.path.join(output_dir, "hard_words_comparison.png")
    comparison.save(comp_path)

    return {
        "type": "hard_words",
        "words": word_meta,
        "comparison_image": comp_path,
    }


def generate_punctuation_eval(models, output_dir):
    """Generate words with different punctuation marks for readability review.

    Tests: apostrophe contraction, comma-adjacent, period, question mark,
    exclamation, semicolon. Covers both synthetic punctuation (contractions)
    and DiffusionPen-rendered punctuation.
    """
    from reforge.evaluate.compare import create_comparison_image
    from reforge.evaluate.ocr import ocr_accuracy
    from reforge.model.generator import generate_word

    # Words exercising different punctuation types from the charset
    punct_words = [
        "can't",      # apostrophe contraction (synthetic)
        "hello,",     # trailing comma
        "world.",     # trailing period
        "really?",    # trailing question mark
        "great!",     # trailing exclamation
        "wait;",      # trailing semicolon
        "it's",       # short contraction (synthetic)
        "she'd",      # contraction with d (synthetic)
    ]

    word_images = []
    word_meta = []
    for word in punct_words:
        img = generate_word(
            word,
            models["unet"], models["vae"], models["tokenizer"],
            models["style_features"],
            uncond_context=models["uncond_context"],
            num_steps=20, guidance_scale=3.0,
            num_candidates=1,
            device=models["device"],
        )
        acc = ocr_accuracy(img, word)
        word_images.append(img)
        word_meta.append({
            "word": word,
            "ocr_accuracy": round(acc, 4),
        })

    comparison = create_comparison_image(
        word_images,
        [f'{m["word"]} (OCR: {m["ocr_accuracy"]:.2f})' for m in word_meta],
        title="Punctuation readability check",
    )
    comp_path = os.path.join(output_dir, "punctuation_comparison.png")
    comparison.save(comp_path)

    return {
        "type": "punctuation",
        "words": word_meta,
        "comparison_image": comp_path,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

GENERATORS = {
    "candidate": generate_candidate_eval,
    "stitch": generate_stitch_eval,
    "sizing": generate_sizing_eval,
    "baseline": generate_baseline_eval,
    "spacing": generate_spacing_eval,
    "ink_weight": generate_ink_weight_eval,
    "composition": generate_composition_eval,
    "hard_words": generate_hard_words_eval,
    "punctuation": generate_punctuation_eval,
}


def generate_all_evals(eval_types, models, output_dir):
    """Generate images for requested eval types. Returns {type: metadata}."""
    os.makedirs(output_dir, exist_ok=True)
    results = {}
    for et in eval_types:
        t0 = time.monotonic()
        sys.stderr.write(f"  Generating {et}...")
        sys.stderr.flush()
        results[et] = GENERATORS[et](models, output_dir)
        elapsed = time.monotonic() - t0
        sys.stderr.write(f" done ({elapsed:.1f}s)\n")
    return results


def build_html_page(eval_metadata, eval_types, output_dir):
    """Build the custom HTML review page by injecting data into template.

    Returns path to the generated HTML file.
    """
    # Build the data structure the HTML page needs
    steps = []
    image_files = []

    for et in eval_types:
        meta = eval_metadata[et]
        img_path = meta["comparison_image"]
        img_basename = os.path.basename(img_path)
        image_files.append(img_path)

        step = {
            "eval_type": et,
            "image": img_basename,
        }

        if et == "candidate":
            step["title"] = "Candidate Selection"
            step["description"] = (
                f'Which candidate of "{meta["word"]}" looks best? '
                f'Quality score picked: {meta["quality_score_pick"]}'
            )
            step["input_type"] = "pick"
            step["options"] = [c["label"] for c in meta["candidates"]]
            step["extra_fields"] = [
                {"name": "agrees_with_metric", "type": "checkbox",
                 "label": "Agree with quality score pick?"},
            ]
        elif et == "stitch":
            step["title"] = "Chunk Stitching"
            step["description"] = (
                f'Which overlap produces the least visible seam for '
                f'"{meta["word"]}" ({" + ".join(meta["chunks"])})?'
            )
            step["input_type"] = "pick"
            step["options"] = [f"{o}px" for o in meta["overlaps"]]
        elif et == "sizing":
            step["title"] = "Short vs Long Word Sizing"
            step["description"] = (
                f'Words: {", ".join(meta["words"])}. '
                f'Rate whether relative sizes look natural.'
            )
            step["input_type"] = "rating"
            step["rating_label"] = "Size consistency"
        elif et == "baseline":
            step["title"] = "Baseline Alignment"
            step["description"] = (
                f'Phrase: "{" ".join(meta["words"])}". '
                f'Rate baseline smoothness (especially descenders: j, q, y, g).'
            )
            step["input_type"] = "rating"
            step["rating_label"] = "Baseline smoothness"
        elif et == "spacing":
            step["title"] = "Spacing and Jitter"
            step["description"] = "Which spacing configuration looks more natural?"
            step["input_type"] = "ab_pick"
            step["options"] = ["A", "B"]
            step["option_labels"] = [c["label"] for c in meta["configs"]]
        elif et == "ink_weight":
            step["title"] = "Ink Weight Consistency"
            step["description"] = "Which variant has more consistent ink weight across words?"
            step["input_type"] = "ab_pick"
            step["options"] = ["A", "B"]
            step["option_labels"] = [c["label"] for c in meta["configs"]]
        elif et == "composition":
            step["title"] = "Full Composition"
            step["description"] = (
                "Rate overall 'handwritten note' impression. "
                "Flag any visible defects."
            )
            step["input_type"] = "composition_rating"
            step["defect_options"] = [
                "gray_boxes", "spacing_tight", "spacing_loose",
                "size_inconsistent", "baseline_drift", "ink_weight_uneven",
                "seam_visible", "letter_malformed", "other",
            ]
        elif et == "hard_words":
            word_list = ", ".join(w["word"] for w in meta.get("words", []))
            step["title"] = "Hard Words Readability"
            step["description"] = (
                f"Rate overall readability of these difficult words: {word_list}. "
                "Flag any that are unreadable."
            )
            step["input_type"] = "hard_words_rating"
            step["unreadable_options"] = [w["word"] for w in meta.get("words", [])]
        elif et == "punctuation":
            word_list = ", ".join(w["word"] for w in meta.get("words", []))
            step["title"] = "Punctuation Readability"
            step["description"] = (
                f"Rate overall readability of punctuated words: {word_list}. "
                "Flag any where punctuation is missing, malformed, or unreadable."
            )
            step["input_type"] = "hard_words_rating"
            step["unreadable_options"] = [w["word"] for w in meta.get("words", [])]

        steps.append(step)

    # Read HTML template and inject data
    template_path = os.path.join(os.path.dirname(__file__), "human_eval_page.html")
    with open(template_path) as f:
        html = f.read()

    html = html.replace("/* INJECT_STEPS_JSON */", json.dumps(steps))
    html = html.replace("/* INJECT_EVAL_ORDER */", json.dumps(eval_types))

    out_path = os.path.join(output_dir, "review_page.html")
    with open(out_path, "w") as f:
        f.write(html)

    return out_path, image_files


def launch_qpeek(html_path, image_files):
    """Launch qpeek with custom HTML page. Returns parsed response or None.

    Returns None on abandon (exit code 1) or timeout (exit code 3).
    """
    cmd = [
        sys.executable, "-m", "qpeek",
        "--html", html_path,
        "--timeout", "0",
    ] + image_files

    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, cwd=PROJECT_ROOT)

    if result.returncode == 0:
        # qpeek prints JSON to stdout: {"files": [...], "response": "<our json>"}
        stdout = result.stdout.strip()
        if stdout:
            try:
                outer = json.loads(stdout)
                # Unwrap: our responses are JSON-encoded inside the "response" field
                inner = outer.get("response", "{}")
                if isinstance(inner, str):
                    return json.loads(inner)
                return inner
            except (json.JSONDecodeError, AttributeError):
                sys.stderr.write(f"Warning: could not parse qpeek output as JSON\n")
                sys.stderr.write(f"Raw output: {stdout[:500]}\n")
                return None
        return None
    elif result.returncode == 1:
        sys.stderr.write("Review abandoned (browser closed).\n")
        return None
    elif result.returncode == 3:
        sys.stderr.write("Review timed out.\n")
        return None
    else:
        sys.stderr.write(f"qpeek exited with code {result.returncode}\n")
        return None


def save_review(responses, eval_metadata, eval_types):
    """Persist review JSON. Returns path to saved file."""
    now = datetime.now()
    filename = now.strftime("%Y-%m-%d_%H%M%S") + ".json"
    path = os.path.join(REVIEW_DIR, filename)

    # Get CV metrics from composition eval if present
    cv_metrics = {}
    per_seed_cv = None
    selected_seed = None
    if "composition" in eval_metadata:
        comp = eval_metadata["composition"]
        cv_metrics = comp.get("cv_metrics", {})
        per_seed_cv = comp.get("per_seed_cv")
        selected_seed = comp.get("selected_seed")

    review = {
        "version": 1,
        "timestamp": now.isoformat(timespec="seconds"),
        "commit": get_commit_hash(),
        "pipeline_checksums": compute_pipeline_checksums(),
        "evaluations": responses,
        "cv_metrics": cv_metrics,
    }
    if per_seed_cv is not None:
        review["per_seed_cv"] = per_seed_cv
    if selected_seed is not None:
        review["selected_seed"] = selected_seed

    os.makedirs(REVIEW_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(review, f, indent=2, default=str)

    return path


def print_summary(review_path, responses):
    """Print human-readable summary of the review."""
    print(f"\nReview saved: {review_path}")
    print("\nSummary:")
    for et, resp in responses.items():
        if resp.get("skipped"):
            print(f"  {et:15s}  skipped")
        elif "pick" in resp:
            print(f"  {et:15s}  picked: {resp['pick']}")
        elif "preferred" in resp:
            print(f"  {et:15s}  preferred: {resp['preferred']}")
        elif "rating" in resp:
            print(f"  {et:15s}  rating: {resp['rating']}/5")
        else:
            print(f"  {et:15s}  recorded")
        if resp.get("notes"):
            print(f"  {'':15s}  notes: {resp['notes']}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Human quality evaluation for reforge")
    parser.add_argument(
        "--eval", type=str, default=None,
        help="Comma-separated eval types to run (default: all)",
    )
    parser.add_argument(
        "--device", type=str, default=None,
        help="Torch device (default: cuda if available)",
    )
    args = parser.parse_args()

    # Determine device
    import torch
    if args.device:
        device = args.device
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        sys.stderr.write("CUDA not available. Human eval requires GPU for generation.\n")
        sys.exit(1)

    # Parse eval filter
    if args.eval:
        eval_types = [e.strip() for e in args.eval.split(",")]
        invalid = [e for e in eval_types if e not in EVAL_TYPES]
        if invalid:
            sys.stderr.write(f"Unknown eval types: {', '.join(invalid)}\n")
            sys.stderr.write(f"Valid types: {', '.join(EVAL_TYPES)}\n")
            sys.exit(1)
    else:
        eval_types = list(EVAL_TYPES)

    sys.stderr.write(f"Human evaluation: {', '.join(eval_types)}\n")
    sys.stderr.write(f"Device: {device}\n\n")

    # Load models
    sys.stderr.write("Loading models...\n")
    t0 = time.monotonic()
    models = load_models(device)
    sys.stderr.write(f"Models loaded ({time.monotonic() - t0:.1f}s)\n\n")

    # Generate evaluation images
    sys.stderr.write("Generating evaluation images:\n")
    t0 = time.monotonic()
    eval_metadata = generate_all_evals(eval_types, models, IMAGE_DIR)
    sys.stderr.write(f"\nGeneration complete ({time.monotonic() - t0:.1f}s)\n\n")

    # Build HTML page and launch qpeek
    html_path, image_files = build_html_page(eval_metadata, eval_types, IMAGE_DIR)
    sys.stderr.write("Launching review in browser...\n")
    responses = launch_qpeek(html_path, image_files)

    if responses is None:
        sys.stderr.write("No review data captured.\n")
        sys.exit(0)

    # Save review
    review_path = save_review(responses, eval_metadata, eval_types)
    print_summary(review_path, responses)

    print("Review captured. Run the coding agent to draft updated FINDINGS.md.")


if __name__ == "__main__":
    main()
