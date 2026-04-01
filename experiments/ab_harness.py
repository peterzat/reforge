"""A/B experiment runner with predefined presets.

Supports single-word and multi-word experiments with statistical context
(mean/std across multiple runs). Results are logged to JSON for accumulation
across sessions.
"""

import argparse
import json
import os
import sys
import time

import cv2
import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PRESETS = {
    "cfg": {
        "description": "Sweep guidance_scale values",
        "variants": [
            {"label": "CFG=1.0 (no guidance)", "guidance_scale": 1.0},
            {"label": "CFG=3.0 (default)", "guidance_scale": 3.0},
            {"label": "CFG=5.0", "guidance_scale": 5.0},
            {"label": "CFG=7.5", "guidance_scale": 7.5},
        ],
    },
    "scheduler": {
        "description": "DDIM vs DPM++ vs UniPC at equal steps",
        "variants": [
            {"label": "DDIM (25 steps)", "scheduler": "ddim", "num_steps": 25},
            {"label": "DPM++ (25 steps)", "scheduler": "dpmsolver++", "num_steps": 25},
            {"label": "UniPC (25 steps)", "scheduler": "unipc", "num_steps": 25},
        ],
    },
    "postprocess": {
        "description": "Soft sigmoid vs hard threshold postprocessing",
        "variants": [
            {"label": "Hard threshold", "postprocess": "hard"},
            {"label": "Soft sigmoid", "postprocess": "soft"},
        ],
    },
    "combined": {
        "description": "Baseline vs tuned settings",
        "variants": [
            {
                "label": "Baseline (CFG=1.0, DDIM, 50 steps, hard)",
                "guidance_scale": 1.0,
                "scheduler": "ddim",
                "num_steps": 50,
                "postprocess": "hard",
            },
            {
                "label": "Tuned (CFG=3.0, DPM++, 25 steps, soft)",
                "guidance_scale": 3.0,
                "scheduler": "dpmsolver++",
                "num_steps": 25,
                "postprocess": "soft",
            },
        ],
    },
}


def generate_variant(
    word: str, unet, vae, tokenizer, style_features, uncond_context,
    variant: dict, device: str,
) -> np.ndarray:
    """Generate a word image using variant-specific settings."""
    from reforge.model.generator import generate_word

    guidance_scale = variant.get("guidance_scale", 3.0)
    num_steps = variant.get("num_steps", 50)

    img = generate_word(
        word,
        unet,
        vae,
        tokenizer,
        style_features,
        uncond_context=uncond_context if guidance_scale != 1.0 else None,
        num_steps=num_steps,
        guidance_scale=guidance_scale,
        num_candidates=1,
        device=device,
    )
    return img


def generate_multi_word_variant(
    words: list[str], unet, vae, tokenizer, style_features, uncond_context,
    variant: dict, device: str,
) -> np.ndarray:
    """Generate and compose multiple words using variant-specific settings."""
    from reforge.compose.render import compose_words
    from reforge.quality.font_scale import normalize_font_size
    from reforge.quality.harmonize import harmonize_words

    imgs = []
    for w in words:
        img = generate_variant(
            w, unet, vae, tokenizer, style_features,
            uncond_context, variant, device,
        )
        imgs.append(normalize_font_size(img, w))

    imgs = harmonize_words(imgs)
    composed = compose_words(imgs, words, upscale_factor=1)
    return np.array(composed)


def run_experiment(
    style_path: str, experiment: str, device: str = "cuda",
    num_runs: int = 1, multi_word: bool = False,
):
    """Run an A/B experiment and save comparison images + JSON results.

    Args:
        style_path: Path to style reference image.
        experiment: Preset name from PRESETS.
        device: Torch device.
        num_runs: Number of runs per variant for statistical context.
        multi_word: If True, generate a 5-word line instead of a single word.
    """
    from reforge.evaluate.compare import create_comparison_image
    from reforge.evaluate.visual import overall_quality_score
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

    preset = PRESETS[experiment]
    print(f"Running experiment: {experiment}")
    print(f"Description: {preset['description']}")
    if num_runs > 1:
        print(f"Runs per variant: {num_runs}")
    if multi_word:
        print("Mode: multi-word (5-word line)")

    # Load style
    style_img = cv2.imread(style_path, cv2.IMREAD_GRAYSCALE)
    if style_img is None:
        raise FileNotFoundError(f"Cannot read: {style_path}")
    words_raw = segment_sentence_image(style_img)
    if len(words_raw) != 5:
        raise ValueError(f"Expected 5 words, got {len(words_raw)}")
    style_tensors = preprocess_words(words_raw)

    # Load models
    style_ckpt = download_style_encoder_weights()
    encoder = StyleEncoder(checkpoint_path=style_ckpt).to(device)
    style_features = encoder.encode(style_tensors)

    unet_ckpt = download_unet_weights()
    unet = load_unet(unet_ckpt, device=device)
    vae = load_vae(device=device)
    tokenizer = load_tokenizer()

    uncond_context = tokenizer(" ", return_tensors="pt", padding="max_length", max_length=16)

    test_words = ["Quick", "brown", "foxes", "jump", "high"] if multi_word else None
    test_word = "Hello"

    # Generate variants with multiple runs
    all_results = []
    best_images = []
    best_labels = []
    best_scores = []

    for variant in preset["variants"]:
        label = variant["label"]
        print(f"  Generating: {label}")
        run_scores = []
        run_images = []

        for run_idx in range(num_runs):
            if multi_word:
                img = generate_multi_word_variant(
                    test_words, unet, vae, tokenizer, style_features,
                    uncond_context, variant, device,
                )
            else:
                img = generate_variant(
                    test_word, unet, vae, tokenizer, style_features,
                    uncond_context, variant, device,
                )
            score = overall_quality_score(img)

            # Add OCR accuracy for single-word mode
            if not multi_word:
                try:
                    from reforge.evaluate.ocr import ocr_accuracy
                    score["ocr_accuracy"] = ocr_accuracy(img, test_word)
                except ImportError:
                    pass

            run_scores.append(score)
            run_images.append(img)

            if num_runs > 1:
                ocr_str = f", OCR={score.get('ocr_accuracy', 'N/A')}" if "ocr_accuracy" in score else ""
                print(f"    Run {run_idx + 1}/{num_runs}: {score['overall']:.3f}{ocr_str}")

        # Compute statistics
        overall_scores = [s["overall"] for s in run_scores]
        mean_score = float(np.mean(overall_scores))
        std_score = float(np.std(overall_scores)) if num_runs > 1 else 0.0

        # Pick best run for comparison image
        best_idx = int(np.argmax(overall_scores))
        best_images.append(run_images[best_idx])
        best_labels.append(label)
        best_scores.append(run_scores[best_idx])

        variant_result = {
            "label": label,
            "settings": {k: v for k, v in variant.items() if k != "label"},
            "num_runs": num_runs,
            "overall_mean": round(mean_score, 4),
            "overall_std": round(std_score, 4),
            "per_run_scores": [
                {k: round(v, 4) if isinstance(v, float) else v for k, v in s.items()}
                for s in run_scores
            ],
        }
        all_results.append(variant_result)

        if num_runs > 1:
            print(f"    Mean: {mean_score:.3f} +/- {std_score:.3f}")
        else:
            print(f"    Score: {mean_score:.3f}")

    # Create comparison image
    comparison = create_comparison_image(
        best_images, best_labels, best_scores,
        title=f"Experiment: {experiment}",
    )

    os.makedirs("experiments/output", exist_ok=True)
    suffix = "_multiword" if multi_word else ""
    output_path = f"experiments/output/{experiment}{suffix}_comparison.png"
    comparison.save(output_path)
    print(f"Comparison saved to: {output_path}")

    # Log results to JSON
    result_record = {
        "experiment": experiment,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "style_path": style_path,
        "multi_word": multi_word,
        "test_input": test_words if multi_word else test_word,
        "num_runs": num_runs,
        "variants": all_results,
    }

    json_path = "experiments/output/results.json"
    existing = []
    if os.path.exists(json_path):
        with open(json_path) as f:
            existing = json.load(f)
    existing.append(result_record)
    with open(json_path, "w") as f:
        json.dump(existing, f, indent=2)
    print(f"Results appended to: {json_path}")

    return result_record


def main():
    parser = argparse.ArgumentParser(description="A/B experiment runner for reforge.")
    parser.add_argument("--style", type=str, required=True, help="Path to style image.")
    parser.add_argument(
        "--experiment",
        type=str,
        required=True,
        choices=list(PRESETS.keys()),
        help="Experiment preset to run.",
    )
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument(
        "--runs", type=int, default=1,
        help="Number of runs per variant for statistical context.",
    )
    parser.add_argument(
        "--multi-word", action="store_true",
        help="Test with a 5-word line instead of a single word.",
    )
    args = parser.parse_args()
    run_experiment(
        args.style, args.experiment, args.device,
        num_runs=args.runs, multi_word=args.multi_word,
    )


if __name__ == "__main__":
    main()
