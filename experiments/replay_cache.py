"""Cache generations once, then replay downstream stages offline.

Holding generation fixed is what made the 2026-10-13 A/B tests clear: both
arms of a sizing, compose or post-processing change render the same words,
so only the change under test differs.

    # 1. Generate (GPU, ~2 min per seed with the quality preset)
    .venv/bin/python experiments/replay_cache.py generate OUT_DIR --seeds 42 137 2718
    # 2. Compose a cache with the working tree, or with any git ref
    .venv/bin/python experiments/replay_cache.py compose OUT_DIR/seed42.npz page.png
    .venv/bin/python experiments/replay_cache.py compose OUT_DIR/seed42.npz old.png --ref origin/main

Caches hold raw generate_word() outputs (before sizing). Seeding matches
pipeline.run(seed=...): word i of a run is seeded from (seed, i).
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEMO_TEXT = (
    "I can't remember exactly, but it was a Thursday; the bakery on Birchwood "
    "had croissants so perfect they'd disappear by noon.\nWe grabbed two, maybe "
    "three? Katherine laughed and said something wonderful about mornings being "
    "too beautiful for ordinary breakfast."
)


def generate(args):
    sys.path.insert(0, REPO)
    os.chdir(REPO)
    import cv2
    import numpy as np
    import torch

    from reforge.config import PRESETS
    from reforge.model.encoder import StyleEncoder
    from reforge.model.generator import generate_word
    from reforge.model.weights import (
        download_style_encoder_weights, download_unet_weights,
        load_tokenizer, load_unet, load_vae,
    )
    from reforge.preprocess.normalize import preprocess_words
    from reforge.preprocess.segment import segment_sentence_image
    from reforge.quality.harmonize import compute_mean_stroke_width
    from reforge.validation import split_paragraphs

    device = "cuda"
    preset = PRESETS[args.preset]
    style = segment_sentence_image(cv2.imread(args.style, cv2.IMREAD_GRAYSCALE))
    style_features = StyleEncoder(checkpoint_path=download_style_encoder_weights()).to(device).encode(
        preprocess_words(style))
    unet = load_unet(download_unet_weights(), device=device)
    vae = load_vae(device=device)
    tokenizer = load_tokenizer()
    uncond = tokenizer(" ", return_tensors="pt", padding="max_length", max_length=16)

    def _to_canvas(img, h=64):
        return cv2.resize(img, (max(1, int(img.shape[1] * h / img.shape[0])), h), interpolation=cv2.INTER_AREA)

    widths = [w for w in (compute_mean_stroke_width(_to_canvas(s)) for s in style) if w > 0]
    ref_stroke = float(np.median(widths)) if widths else 0.0

    flat = []
    for i, para in enumerate(split_paragraphs(args.text.replace("\\n", "\n"))):
        if i:
            flat.append(None)
        flat.extend(para)

    os.makedirs(args.out_dir, exist_ok=True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    for seed in args.seeds:
        t0 = time.time()
        arrays, word_idx = {}, 0
        for i, w in enumerate(flat):
            if w is None:
                continue
            word_idx += 1
            torch.manual_seed(seed * 1_000_003 + word_idx)
            arrays[f"w{i}"] = generate_word(
                w, unet, vae, tokenizer, style_features, uncond_context=uncond,
                num_steps=preset["steps"], guidance_scale=preset["guidance_scale"],
                num_candidates=preset["candidates"], device=device,
                style_reference_imgs=style, reference_stroke_width=ref_stroke,
            )
        np.savez_compressed(os.path.join(args.out_dir, f"seed{seed}.npz"),
                            words=np.array(flat, dtype=object), **arrays)
        print(f"seed {seed}: {len(arrays)} words in {time.time() - t0:.0f}s", flush=True)


_COMPOSE = r'''
import json, os, sys
repo, npz, out = sys.argv[1:4]
sys.path.insert(0, repo); os.chdir(repo)
import numpy as np
z = np.load(npz, allow_pickle=True)
words = list(z["words"])
imgs = [None if w is None else z[f"w{i}"] for i, w in enumerate(words)]
try:
    from reforge.pipeline import postprocess_words
    final = postprocess_words(imgs, words)
except ImportError:  # refs before 2026-10-13: the hand-wired order pipeline.run used
    from reforge.quality.font_scale import equalize_body_zones, normalize_font_size
    from reforge.quality.harmonize import harmonize_words
    n = [None if w is None else normalize_font_size(im, w) for w, im in zip(words, imgs)]
    it = iter(harmonize_words(equalize_body_zones([x for x in n if x is not None])))
    final = [None if x is None else next(it) for x in n]
from reforge.compose.render import compose_words
from reforge.evaluate.visual import overall_quality_score
img, pos = compose_words(final, words, return_positions=True)
img.save(out)
q = overall_quality_score(np.array(img), [x for x in final if x is not None], pos,
                          words=[w for w in words if w is not None])
keep = ("x_height_consistency", "ocr_accuracy", "ocr_min", "word_readability_rate",
        "stroke_weight_consistency", "overall")
print(json.dumps({k: round(float(q[k]), 4) for k in keep if k in q}))
'''


def compose(args):
    npz, out = os.path.abspath(args.npz), os.path.abspath(args.out)
    if not args.ref:
        subprocess.run([sys.executable, "-c", _COMPOSE, REPO, npz, out], check=True)
        return
    with tempfile.TemporaryDirectory() as tmp:
        wt = os.path.join(tmp, "wt")
        subprocess.run(["git", "-C", REPO, "worktree", "add", "-q", "--detach", wt, args.ref], check=True)
        try:
            subprocess.run([sys.executable, "-c", _COMPOSE, wt, npz, out], check=True)
        finally:
            subprocess.run(["git", "-C", REPO, "worktree", "remove", "--force", wt], check=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("out_dir")
    g.add_argument("--seeds", type=int, nargs="+", default=[42, 137, 2718])
    g.add_argument("--text", default=DEMO_TEXT)
    g.add_argument("--style", default=os.path.join(REPO, "styles", "hw-sample.png"))
    g.add_argument("--preset", default="quality")
    c = sub.add_parser("compose")
    c.add_argument("npz")
    c.add_argument("out")
    c.add_argument("--ref", help="git ref to compose with (temporary worktree)")
    args = ap.parse_args()
    {"generate": generate, "compose": compose}[args.cmd](args)


if __name__ == "__main__":
    main()
