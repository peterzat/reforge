"""Medium test: hard words regression test.

Generates every curated hard word, runs OCR, reports per-word accuracy.
Asserts average OCR > 0.5 (lower bar than easy words, reflecting genuine difficulty).
Records results to a JSONL ledger for tracking improvement over time.
"""

import json
import os
import subprocess
import time
from datetime import datetime

import numpy as np
import pytest
import torch

pytestmark = [
    pytest.mark.medium,
    pytest.mark.gpu,
    pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required"),
]

LEDGER_PATH = "tests/medium/hard_words_ledger.jsonl"


def _get_commit_hash():
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True,
        )
        return r.stdout.strip()
    except Exception:
        return "unknown"


def test_hard_words_ocr(unet, vae, tokenizer, style_features, uncond_context, device):
    """Generate each curated hard word and check OCR accuracy."""
    from reforge.data.words import load_hard_words
    from reforge.evaluate.ocr import ocr_accuracy, ocr_read
    from reforge.model.generator import generate_word
    from reforge.quality.font_scale import normalize_font_size

    words = load_hard_words()
    assert len(words) > 0, "No curated hard words found"

    results = []
    print(f"\n  Hard words test: {len(words)} words")
    print(f"  {'Word':20s} {'OCR':>6s} {'Read as':20s} {'Status'}")
    print(f"  {'-'*20} {'-'*6} {'-'*20} {'-'*8}")

    for word in words:
        img = generate_word(
            word, unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=20, guidance_scale=3.0, num_candidates=1, device=device,
        )
        img = normalize_font_size(img, word)
        acc = ocr_accuracy(img, word)
        read_as = ocr_read(img)

        status = "OK" if acc >= 0.3 else "CRITICAL"
        print(f"  {word:20s} {acc:6.3f} {read_as:20s} {status}")

        results.append({
            "word": word,
            "ocr_accuracy": round(acc, 4),
            "ocr_read": read_as,
        })

    accuracies = [r["ocr_accuracy"] for r in results]
    avg = float(np.mean(accuracies))
    critical = [r for r in results if r["ocr_accuracy"] < 0.3]

    print(f"\n  Average: {avg:.3f}  Critical: {len(critical)}/{len(results)}")

    # Record to ledger
    ledger_entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "commit": _get_commit_hash(),
        "avg_accuracy": round(avg, 4),
        "n_words": len(results),
        "n_critical": len(critical),
        "results": results,
    }
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    with open(LEDGER_PATH, "a") as f:
        f.write(json.dumps(ledger_entry) + "\n")

    assert avg > 0.5, f"Average hard word OCR {avg:.3f} below 0.5 threshold"


# A1: Punctuation-specific generation test covering multiple charset marks
PUNCTUATION_WORDS = [
    "can't",       # apostrophe in contraction
    "don't",       # apostrophe in contraction
    "it's",        # apostrophe in short word
    "hello,",      # comma (generated as part of word)
    "what?",       # question mark
    "wow!",        # exclamation mark
]


def test_punctuation_ocr(unet, vae, tokenizer, style_features, uncond_context, device):
    """A1: Generate words with punctuation marks and check OCR readability.

    Tests different punctuation characters from the charset: apostrophe,
    comma, question mark, exclamation mark. Asserts average OCR >= 0.3
    across the set.
    """
    from reforge.evaluate.ocr import ocr_accuracy, ocr_read
    from reforge.model.generator import generate_word
    from reforge.quality.font_scale import normalize_font_size

    results = []
    print(f"\n  Punctuation test: {len(PUNCTUATION_WORDS)} words")
    print(f"  {'Word':20s} {'OCR':>6s} {'Read as':20s}")
    print(f"  {'-'*20} {'-'*6} {'-'*20}")

    for word in PUNCTUATION_WORDS:
        img = generate_word(
            word, unet, vae, tokenizer, style_features,
            uncond_context=uncond_context,
            num_steps=20, guidance_scale=3.0, num_candidates=1, device=device,
        )
        img = normalize_font_size(img, word)
        acc = ocr_accuracy(img, word)
        read_as = ocr_read(img)

        print(f"  {word:20s} {acc:6.3f} {read_as:20s}")
        results.append({"word": word, "ocr_accuracy": round(acc, 4)})

    avg = float(np.mean([r["ocr_accuracy"] for r in results]))
    print(f"\n  Average punctuation OCR: {avg:.3f}")

    assert avg >= 0.3, f"Average punctuation OCR {avg:.3f} below 0.3 threshold"
