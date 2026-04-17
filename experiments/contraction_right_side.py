"""Spec 2026-04-17 C: contraction right-side canvas-width experiment.

Generates the composition eval text on seeds {42, 137, 2718} at the current
CONTRACTION_RIGHT_SIDE_WIDTH (None, meaning compute_canvas_width default) and
at one narrower candidate (128px). Reports per-contraction-word OCR accuracy
and composition CV metrics (height_outlier_score, baseline_alignment,
ocr_min, punctuation_visibility) for each condition.

Decision rule (C3): accept the narrower width only if it improves
multi-seed mean OCR accuracy on contractions by >=10% AND does not regress
punctuation_visibility or any primary CV gate.
"""

import argparse
import json
import os
import sys
from statistics import mean

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reforge import config  # noqa: E402
from reforge.config import PRESET_FAST  # noqa: E402
from reforge.evaluate.ocr import ocr_accuracy  # noqa: E402
from reforge.pipeline import run  # noqa: E402

COMPOSITION_TEXT = (
    "I can't remember exactly, but it was a Thursday; the bakery on "
    "Birchwood had croissants so perfect they'd disappear by noon.\n"
    "We grabbed two, maybe three? Katherine laughed and said something "
    "wonderful about mornings being too beautiful for ordinary breakfast."
)
CONTRACTION_WORDS = ("can't", "they'd")
STYLE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "styles", "hw-sample.png")
SEEDS = [42, 137, 2718]
WIDTH_CANDIDATES = [None, 128]
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "contraction_right_side")


def _contraction_word_positions(words, positions, upscale=2):
    hits = {}
    for i, w in enumerate(words):
        if w in CONTRACTION_WORDS and w not in hits and i < len(positions):
            hits[w] = positions[i]
    return hits


def _crop_word(output_path, pos, upscale=2):
    from PIL import Image

    img = np.array(Image.open(output_path).convert("L"))
    h_img, w_img = img.shape[:2]
    x = int(pos.get("x", 0)) * upscale
    y = int(pos.get("y", 0)) * upscale
    w = int(pos.get("width", 0)) * upscale
    h = int(pos.get("height", 0)) * upscale
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(w_img, x + w), min(h_img, y + h)
    return img[y0:y1, x0:x1]


def run_one(seed: int, width: int | None, out_dir: str) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)
    config.CONTRACTION_RIGHT_SIDE_WIDTH = width
    tag = f"w{width if width is not None else 'default'}_seed{seed}"
    out_path = os.path.join(out_dir, f"{tag}.png")

    result = run(
        style_path=STYLE_PATH,
        text=COMPOSITION_TEXT,
        output_path=out_path,
        num_steps=PRESET_FAST["steps"],
        guidance_scale=PRESET_FAST["guidance_scale"],
        num_candidates=PRESET_FAST["candidates"],
        device="cuda",
        verbose=False,
    )
    scores = result["quality_scores"]
    positions = result["word_positions"]

    # Recover the flat word list aligned with positions from the rendered PNG
    # We can't get it back directly, so we split the text the same way pipeline did.
    from reforge.validation import split_paragraphs

    paragraphs = split_paragraphs(COMPOSITION_TEXT)
    flat_words = []
    for para in paragraphs:
        flat_words.extend(para)

    contraction_hits = _contraction_word_positions(flat_words, positions)
    per_contraction = {}
    for w, pos in contraction_hits.items():
        crop = _crop_word(out_path, pos)
        acc = float(ocr_accuracy(crop, w))
        per_contraction[w] = acc

    return {
        "seed": seed,
        "width": width,
        "height_outlier_score": float(scores.get("height_outlier_score", 0.0)),
        "baseline_alignment": float(scores.get("baseline_alignment", 0.0)),
        "ocr_min": float(scores.get("ocr_min", 0.0)),
        "punctuation_visibility": float(scores.get("punctuation_visibility", 0.0)),
        "contraction_ocr": per_contraction,
        "contraction_ocr_mean": mean(per_contraction.values()) if per_contraction else 0.0,
    }


def summarize(rows: list[dict]) -> dict:
    agg = {}
    for key in ("height_outlier_score", "baseline_alignment", "ocr_min", "punctuation_visibility", "contraction_ocr_mean"):
        vals = [r[key] for r in rows]
        agg[key] = {"mean": mean(vals), "min": min(vals), "max": max(vals)}
    # Per-word means
    word_means = {}
    for w in CONTRACTION_WORDS:
        vals = [r["contraction_ocr"].get(w, 0.0) for r in rows if w in r["contraction_ocr"]]
        if vals:
            word_means[w] = {"mean": mean(vals), "min": min(vals), "max": max(vals)}
    agg["per_word"] = word_means
    return agg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=OUT_DIR)
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    all_runs = {}
    for w in WIDTH_CANDIDATES:
        label = "default" if w is None else str(w)
        per_seed = [run_one(seed, w, args.out_dir) for seed in SEEDS]
        all_runs[label] = {"per_seed": per_seed, "aggregate": summarize(per_seed)}

    # C3 accept/reject
    default_mean = all_runs["default"]["aggregate"]["contraction_ocr_mean"]["mean"]
    narrow_mean = all_runs["128"]["aggregate"]["contraction_ocr_mean"]["mean"]
    ocr_rel = (narrow_mean - default_mean) / default_mean if default_mean > 0 else float("inf")

    regressed = []
    for key in ("height_outlier_score", "baseline_alignment", "ocr_min", "punctuation_visibility"):
        default_val = all_runs["default"]["aggregate"][key]["mean"]
        narrow_val = all_runs["128"]["aggregate"][key]["mean"]
        if default_val > 0 and (default_val - narrow_val) / default_val >= 0.05:
            regressed.append({"metric": key, "default": default_val, "narrow": narrow_val})

    accept = ocr_rel >= 0.10 and not regressed

    summary = {
        "seeds": SEEDS,
        "widths": {"default": None, "narrow": 128},
        "runs": all_runs,
        "ocr_relative_improvement_pct": ocr_rel * 100,
        "regressions": regressed,
        "decision": {
            "verdict": "accept_narrow" if accept else "reject_narrow",
            "reason": (
                f"narrow OCR mean {narrow_mean:.3f} vs default {default_mean:.3f} "
                f"({ocr_rel*100:+.2f}%); regressions: {regressed or 'none'}"
            ),
        },
    }

    out_json = os.path.join(args.out_dir, "summary.json")
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    print(f"\nWrote summary: {out_json}")
    print(f"Decision: {summary['decision']['verdict']}")


if __name__ == "__main__":
    main()
