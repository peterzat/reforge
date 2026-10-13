"""Benchmark word readers (OCR) on the labeled crops in this directory.

Usage:
    .venv/bin/python experiments/cv_bench/bench_readers.py trocr_small,vlm

Readers: trocr_small (CPU, reforge default), trocr_large (GPU), vlm (local
server from scripts/vlm_server.sh). Prints one summary line per reader:

- ok_exact / ok_acc: exact-match rate and mean character accuracy on
  well-formed words (reading ability), split by word length;
- bad_corrected: share of malformed renderings read as the intended word
  (language-model "correction"; high means the reader measures legibility,
  not letter fidelity);
- auc_ok_vs_bad: how well accuracy-vs-intended separates well-formed from
  malformed words (0.5 = no separation).

Results from 2026-10-13 are in docs/cv-instruments.md.
"""

import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from reforge.evaluate.ocr import _char_accuracy  # noqa: E402


def make_reader(name):
    if name == "trocr_small":
        from reforge.evaluate.ocr import ocr_read
        return ocr_read
    if name == "trocr_large":
        import torch
        from PIL import Image
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        proc = TrOCRProcessor.from_pretrained("microsoft/trocr-large-handwritten")
        model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-large-handwritten").to("cuda").eval()

        def read(img):
            px = proc(images=Image.fromarray(img).convert("RGB"), return_tensors="pt").pixel_values.to("cuda")
            with torch.no_grad():
                ids = model.generate(px, max_new_tokens=16)
            return proc.batch_decode(ids, skip_special_tokens=True)[0].strip()
        return read
    if name == "vlm":
        from reforge.evaluate.vlm import available, read_word
        if not available():
            sys.exit("no VLM server; run scripts/vlm_server.sh start")
        return read_word
    raise SystemExit(f"unknown reader {name}")


def norm(s):
    return s.lower().strip().rstrip(".,;:!? ").strip()


def auc(pos, neg):
    return float(np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg]))


def main():
    crops = np.load(os.path.join(HERE, "word_crops.npz"))
    items = json.load(open(os.path.join(HERE, "word_labels.json")))["items"]
    for name in sys.argv[1].split(","):
        read = make_reader(name)
        t0 = time.time()
        rows = []
        for it in items:
            out = read(crops[it["key"]])
            rows.append({**it, "read": out, "acc": _char_accuracy(out, it["target"])})
        ok = [r for r in rows if r["status"] == "ok"]
        bad = [r for r in rows if r["status"] == "malformed"]

        def exact(rs):
            return round(float(np.mean([norm(r["read"]) == norm(r["target"]) for r in rs])), 3) if rs else None

        def by_len(lo, hi):
            return [r for r in ok if lo <= len(norm(r["target"])) <= hi]

        summary = {
            "s_per_word": round((time.time() - t0) / len(rows), 3),
            "ok_exact": exact(ok), "ok_acc": round(float(np.mean([r["acc"] for r in ok])), 3),
            "ok_exact_len<=2": exact(by_len(1, 2)), "ok_exact_len3-4": exact(by_len(3, 4)),
            "ok_exact_len5+": exact(by_len(5, 99)),
            "bad_corrected": exact(bad),
            "auc_ok_vs_bad": round(auc([r["acc"] for r in ok], [r["acc"] for r in bad]), 3),
        }
        print(name, json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
