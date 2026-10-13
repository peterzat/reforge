"""Known-answer page pairs for validating a visual judge.

Each pair is a clean page and the same page with one injected defect, from a
generation cache (experiments/replay_cache.py generate):

- shout:   4 short words scaled 1.7x
- blur:    30% of words Gaussian-blurred (sigma 1.6)
- jitter:  30% of words moved 6-7px off the baseline (the clamp-bug signature)
- spacing: word gaps collapsed

    .venv/bin/python experiments/cv_bench/canaries.py OUT_DIR CACHE.npz [CACHE.npz ...]
    .venv/bin/python experiments/cv_bench/canaries.py OUT_DIR CACHE.npz --judge vlm

Writes OUT_DIR/pairNN.png (page A on top, B below, order randomized) and
OUT_DIR/key.json (kept apart from the judge). With --judge vlm, asks the local
VLM (scripts/vlm_server.sh) in both A/B orders and prints per-defect
accuracy, counting a pair only when the clean page wins both times. For a Claude
judge, give a fresh-context subagent only the pairNN.png files and a fixed
rubric, then score its picks against key.json. A judge should get every pair
right before it is trusted on real comparisons (2026-10-13: Claude 15/15
including 3 human-validated pairs, local Qwen3.5-9B 8/15; docs/cv-instruments.md).
"""

import argparse
import json
import os
import random
import sys

import cv2
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

import reforge.compose.layout as layout  # noqa: E402
import reforge.compose.render as render  # noqa: E402
from reforge.compose.render import compose_words  # noqa: E402
from reforge.pipeline import postprocess_words  # noqa: E402

DEFECTS = ("shout", "blur", "jitter", "spacing")


def build_pages(npz, rng):
    z = np.load(npz, allow_pickle=True)
    words = list(z["words"])
    final = postprocess_words([None if w is None else z[f"w{i}"] for i, w in enumerate(words)], words)
    idx = [i for i, w in enumerate(words) if w is not None]
    pages = {"clean": compose_words(final, words)}

    big = list(final)
    short = [i for i in idx if len(words[i].strip(".,;:!?")) <= 3]
    for i in rng.sample(short, min(4, len(short))):
        im = big[i]
        big[i] = cv2.resize(im, (int(im.shape[1] * 1.7), int(im.shape[0] * 1.7)), interpolation=cv2.INTER_CUBIC)
    pages["shout"] = compose_words(big, words)

    blurred = list(final)
    for i in rng.sample(idx, len(idx) * 3 // 10):
        blurred[i] = cv2.GaussianBlur(blurred[i], (0, 0), 1.6)
    pages["blur"] = compose_words(blurred, words)

    shift = {i: rng.choice([-7, -6, 6, 7]) for i in rng.sample(idx, len(idx) * 3 // 10)}
    real_detect, order = render.detect_baseline, iter(idx)
    render.detect_baseline = lambda img, word=None: real_detect(img, word=word) + shift.get(next(order), 0)
    try:
        pages["jitter"] = compose_words(final, words)
    finally:
        render.detect_baseline = real_detect

    saved = layout.WORD_SPACING
    layout.WORD_SPACING = -6
    try:
        pages["spacing"] = compose_words(final, words)
    finally:
        layout.WORD_SPACING = saved
    return pages


def stack(a, b):
    ims = [np.array(x.convert("L")) for x in (a, b)]
    w = max(i.shape[1] for i in ims)
    ims = [np.pad(i, ((0, 0), (0, w - i.shape[1])), constant_values=255) for i in ims]
    lab = [cv2.putText(cv2.cvtColor(i, cv2.COLOR_GRAY2BGR), t, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 255), 3)
           for i, t in zip(ims, "AB")]
    return np.vstack([lab[0], np.full((12, w, 3), 128, np.uint8), lab[1]]), ims


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out_dir")
    ap.add_argument("caches", nargs="+")
    ap.add_argument("--judge", choices=["vlm"])
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    os.makedirs(args.out_dir, exist_ok=True)
    pairs = []
    for npz in args.caches:
        pages = build_pages(npz, rng)
        for d in DEFECTS:
            pairs.append({"cache": os.path.basename(npz), "defect": d, "pages": (pages["clean"], pages[d])})
    rng.shuffle(pairs)
    key, results = {}, []
    for n, p in enumerate(pairs, 1):
        good_is = rng.choice("AB")
        a, b = p["pages"] if good_is == "A" else p["pages"][::-1]
        sheet, (ia, ib) = stack(a, b)
        name = f"pair{n:02d}"
        cv2.imwrite(os.path.join(args.out_dir, name + ".png"), sheet)
        key[name] = {"cache": p["cache"], "defect": p["defect"], "good_is": good_is}
        if args.judge == "vlm":
            from reforge.evaluate.vlm import ask
            schema = {"type": "object", "properties": {"choice": {"type": "string", "enum": ["A", "B"]}},
                      "required": ["choice"]}
            prompt = ("Image 1 is page A and image 2 is page B: two renderings of the same handwritten note. "
                      "Which looks more like a natural, consistent note by one person? Consider consistent "
                      "lowercase size, a common baseline, legibility and natural spacing. "
                      'Answer as JSON {"choice": "A" or "B"}.')
            # Judge both orders; a pair counts only if the judge picks the
            # clean page both times (exposes position bias).
            first = json.loads(ask(prompt, [ia, ib], schema=schema, max_tokens=20))["choice"]
            second = json.loads(ask(prompt, [ib, ia], schema=schema, max_tokens=20))["choice"]
            swapped_good = "B" if good_is == "A" else "A"
            results.append((p["defect"], first == good_is and second == swapped_good))
    json.dump(key, open(os.path.join(args.out_dir, "key.json"), "w"), indent=1)
    print(f"{len(pairs)} pairs in {args.out_dir}")
    if results:
        for d in DEFECTS:
            r = [ok for dd, ok in results if dd == d]
            print(f"  {d:8s} {sum(r)}/{len(r)}")
        print(f"  total    {sum(ok for _, ok in results)}/{len(results)}")


if __name__ == "__main__":
    main()
