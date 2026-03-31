"""A/B experiment runner with predefined presets.

Supports 4 presets: cfg, scheduler, postprocess, combined.
Each generates labeled comparison PNGs.
"""

import argparse
import os
import sys

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


def run_experiment(style_path: str, experiment: str, device: str = "cuda"):
    """Run an A/B experiment and save comparison images."""
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

    # Pre-build unconditional context for CFG (reused across variants)
    uncond_context = tokenizer(" ", return_tensors="pt", padding="max_length", max_length=16)

    # Generate variants
    test_word = "Hello"
    images = []
    labels = []
    scores = []

    for variant in preset["variants"]:
        print(f"  Generating: {variant['label']}")
        img = generate_variant(
            test_word, unet, vae, tokenizer, style_features,
            uncond_context, variant, device,
        )
        score = overall_quality_score(img)
        images.append(img)
        labels.append(variant["label"])
        scores.append(score)
        print(f"    Score: {score['overall']:.3f}")

    # Create comparison image
    comparison = create_comparison_image(images, labels, scores, title=f"Experiment: {experiment}")

    os.makedirs("experiments/output", exist_ok=True)
    output_path = f"experiments/output/{experiment}_comparison.png"
    comparison.save(output_path)
    print(f"Comparison saved to: {output_path}")


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
    args = parser.parse_args()
    run_experiment(args.style, args.experiment, args.device)


if __name__ == "__main__":
    main()
