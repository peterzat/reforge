"""Spec 2026-04-17 A: variance check for _reinforce_thin_strokes().

Generates the composition eval text on a 5-seed set with and without the
reinforcement path, then reports per-seed and aggregate deltas on
height_outlier_score, baseline_alignment, ocr_min, and the strong-ink-pixel
count (< 80) inside the leading "I" region.

Uses PRESET_FAST (20 steps, 1 candidate) so runtime stays tractable; the
metric set is the same one test-regression gates on.
"""

import argparse
import json
import os
import sys
from statistics import mean

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reforge.config import PRESET_FAST  # noqa: E402
from reforge.pipeline import run  # noqa: E402

COMPOSITION_TEXT = (
    "I can't remember exactly, but it was a Thursday; the bakery on "
    "Birchwood had croissants so perfect they'd disappear by noon.\n"
    "We grabbed two, maybe three? Katherine laughed and said something "
    "wonderful about mornings being too beautiful for ordinary breakfast."
)
STYLE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "styles", "hw-sample.png")
SEEDS = [42, 137, 2718, 7, 2025]
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "reinforce_variance")


def measure_i_ink(output_png_path: str, word_positions: list[dict], upscale: int = 2) -> int:
    """Count strong-ink pixels (< 80) in the first word's bbox if it's 'I'.

    ``word_positions`` are pre-upscale coords from compose_words; the saved
    PNG is upscaled by ``upscale``, so we scale the bbox to match.
    """
    from PIL import Image

    if not word_positions:
        return 0
    pos = word_positions[0]
    img = np.array(Image.open(output_png_path).convert("L"))
    h_img, w_img = img.shape[:2]
    x = int(pos.get("x", 0)) * upscale
    y = int(pos.get("y", 0)) * upscale
    w = int(pos.get("width", 0)) * upscale
    h = int(pos.get("height", 0)) * upscale
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(w_img, x + w)
    y1 = min(h_img, y + h)
    if x0 >= x1 or y0 >= y1:
        return 0
    region = img[y0:y1, x0:x1]
    return int(np.sum(region < 80))


def run_one(seed: int, out_dir: str, tag: str) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)
    out_path = os.path.join(out_dir, f"{tag}_seed{seed}.png")
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
    i_ink = measure_i_ink(out_path, positions)
    return {
        "seed": seed,
        "height_outlier_score": float(scores.get("height_outlier_score", 0.0)),
        "baseline_alignment": float(scores.get("baseline_alignment", 0.0)),
        "ocr_min": float(scores.get("ocr_min", 0.0)),
        "i_strong_ink": i_ink,
        "punctuation_visibility": float(scores.get("punctuation_visibility", 0.0)),
    }


def summarize(rows: list[dict]) -> dict:
    agg: dict = {}
    for key in ("height_outlier_score", "baseline_alignment", "ocr_min", "i_strong_ink", "punctuation_visibility"):
        vals = [r[key] for r in rows]
        agg[key] = {"mean": mean(vals), "min": min(vals), "max": max(vals)}
    return agg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=OUT_DIR)
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    # Condition 1: HEAD (reinforcement on)
    os.environ.pop("REFORGE_DISABLE_REINFORCEMENT", None)
    on_rows = [run_one(s, args.out_dir, "on") for s in SEEDS]

    # Condition 2: reinforcement off (via guard)
    os.environ["REFORGE_DISABLE_REINFORCEMENT"] = "1"
    off_rows = [run_one(s, args.out_dir, "off") for s in SEEDS]
    os.environ.pop("REFORGE_DISABLE_REINFORCEMENT", None)

    summary = {
        "seeds": SEEDS,
        "on": {"per_seed": on_rows, "aggregate": summarize(on_rows)},
        "off": {"per_seed": off_rows, "aggregate": summarize(off_rows)},
    }

    # Delta analysis
    def _pct_delta(on_val: float, off_val: float) -> float:
        if off_val == 0:
            return float("inf") if on_val > 0 else 0.0
        return (on_val - off_val) / abs(off_val)

    deltas = {}
    for key in ("height_outlier_score", "baseline_alignment", "ocr_min", "i_strong_ink", "punctuation_visibility"):
        on_mean = summary["on"]["aggregate"][key]["mean"]
        off_mean = summary["off"]["aggregate"][key]["mean"]
        deltas[key] = {
            "on_mean": on_mean,
            "off_mean": off_mean,
            "abs_delta": on_mean - off_mean,
            "rel_delta_pct": _pct_delta(on_mean, off_mean) * 100,
        }
    summary["deltas"] = deltas

    # A3 decision rule
    i_ink_on = summary["on"]["aggregate"]["i_strong_ink"]["mean"]
    i_ink_off = summary["off"]["aggregate"]["i_strong_ink"]["mean"]
    ink_cond = (i_ink_on >= 1.25 * i_ink_off) if i_ink_off > 0 else (i_ink_on > 0)

    cv_regressed = False
    cv_regression_details = []
    for key in ("height_outlier_score", "baseline_alignment", "ocr_min"):
        on_mean = summary["on"]["aggregate"][key]["mean"]
        off_mean = summary["off"]["aggregate"][key]["mean"]
        if off_mean > 0:
            rel = (off_mean - on_mean) / off_mean
            if rel >= 0.05:
                cv_regressed = True
                cv_regression_details.append({"metric": key, "regression_pct": rel * 100})

    if ink_cond and not cv_regressed:
        decision = "keep"
    elif not ink_cond and cv_regressed:
        decision = "revert"
    else:
        decision = "tune"
    summary["decision"] = {
        "verdict": decision,
        "i_ink_gain_met": ink_cond,
        "cv_regressed": cv_regressed,
        "cv_regression_details": cv_regression_details,
    }

    out_json = os.path.join(args.out_dir, "summary.json")
    with open(out_json, "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nWrote summary: {out_json}")
    print(f"Decision: {decision}")


if __name__ == "__main__":
    main()
