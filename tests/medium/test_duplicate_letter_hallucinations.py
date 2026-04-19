"""Medium-tier multi-seed validation for the duplicate-letter hallucination class.

Spec 2026-04-19 criterion 3: `mornings`, `something`, `really` each score
OCR >= 0.5 on at least 2 of 3 seeds (42, 137, 2718). This is the durability
gate: single-seed luck on `make test-hard` does not satisfy the criterion.

The three target words were cited in human reviews as duplicate-letter
hallucinations (`morninggs`, `somettthing`, `reallly`); if DP regresses
on the pattern for one word, at least two seeds must still read cleanly.
"""

import numpy as np
import pytest
import torch

pytestmark = [
    pytest.mark.medium,
    pytest.mark.gpu,
    pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required"),
]

TARGET_WORDS = ("mornings", "something", "really")
SEEDS = (42, 137, 2718)
MIN_PASSING_SEEDS = 2
MIN_OCR = 0.5


def test_target_words_pass_on_at_least_2_of_3_seeds(
    unet, vae, tokenizer, style_features, uncond_context, device,
):
    from reforge.evaluate.ocr import ocr_accuracy
    from reforge.model.generator import generate_word
    from reforge.quality.font_scale import normalize_font_size

    per_word_results: dict[str, list[tuple[int, float, str]]] = {
        w: [] for w in TARGET_WORDS
    }

    for word in TARGET_WORDS:
        for seed in SEEDS:
            torch.manual_seed(seed)
            np.random.seed(seed)
            img = generate_word(
                word, unet, vae, tokenizer, style_features,
                uncond_context=uncond_context,
                num_steps=20, guidance_scale=3.0, num_candidates=1,
                device=device,
            )
            img = normalize_font_size(img, word)
            acc = float(ocr_accuracy(img, word))
            per_word_results[word].append((seed, acc))
            print(f"  {word:12s} seed={seed:4d}  OCR={acc:.3f}")

    failures: list[str] = []
    for word, entries in per_word_results.items():
        passing = [seed for seed, acc in entries if acc >= MIN_OCR]
        if len(passing) < MIN_PASSING_SEEDS:
            detail = ", ".join(f"seed={s} OCR={acc:.3f}" for s, acc in entries)
            failures.append(
                f"{word!r}: only {len(passing)} of {len(SEEDS)} seeds scored "
                f">= {MIN_OCR}; ledger: {detail}"
            )

    assert not failures, "multi-seed validation failed:\n  " + "\n  ".join(failures)
