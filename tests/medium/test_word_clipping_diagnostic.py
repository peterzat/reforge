"""Diagnostic test: trace words through postprocessing to identify clipping causes.

Generates words using the real model, captures raw VAE output before
postprocessing, and runs the diagnostic instrument on each word.
Results are logged for root-cause analysis.
"""

import json
import sys

import numpy as np
import pytest
import torch

pytestmark = [
    pytest.mark.medium,
    pytest.mark.gpu,
    pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required"),
]


# Demo text words for diagnostic
DEMO_WORDS = [
    "The", "quiet", "morning", "light", "filters",
    "through", "shadows", "dancing", "across", "the",
    "favorite", "songs", "playing", "softly", "while",
    "fingers", "trace", "patterns",
]


@pytest.fixture(scope="module")
def model_suite():
    """Load all models once for the module."""
    from reforge.model.encoder import StyleEncoder
    from reforge.model.weights import (
        download_style_encoder_weights,
        download_unet_weights,
        load_tokenizer,
        load_unet,
        load_vae,
    )

    device = "cuda"
    style_ckpt = download_style_encoder_weights()
    encoder = StyleEncoder(checkpoint_path=style_ckpt).to(device)

    import cv2
    from reforge.preprocess.normalize import preprocess_words
    from reforge.preprocess.segment import segment_sentence_image

    style_img = cv2.imread("styles/hw-sample.png", cv2.IMREAD_GRAYSCALE)
    word_imgs = segment_sentence_image(style_img)
    style_tensors = preprocess_words(word_imgs)
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
        "device": device,
    }


def generate_raw_word(word, model_suite):
    """Generate a single word and return BOTH raw VAE output and postprocessed."""
    from reforge.model.generator import (
        compute_canvas_width,
        ddim_sample,
        postprocess_word,
    )

    canvas_width = compute_canvas_width(len(word))
    text_ctx = model_suite["tokenizer"](
        word, return_tensors="pt", padding="max_length", max_length=16
    )

    raw_img = ddim_sample(
        model_suite["unet"],
        model_suite["vae"],
        text_ctx,
        model_suite["style_features"],
        uncond_context=model_suite["uncond_context"],
        canvas_width=canvas_width,
        device=model_suite["device"],
    )

    postprocessed = postprocess_word(raw_img)
    return raw_img, postprocessed


def test_diagnose_word_clipping(model_suite):
    """Run diagnostic on demo words, log which layers cause clipping."""
    from reforge.evaluate.diagnostic import diagnose_postprocessing, format_diagnostic

    results = []
    clipping_causes = {
        "generation": 0,      # ink near edge in raw (canvas too narrow)
        "layer2_body_zone": 0,
        "layer3_cluster": 0,
        "layer3b_gray_cleanup": 0,
    }

    # Test at least 10 words as required by spec
    test_words = DEMO_WORDS[:12]

    for word in test_words:
        raw_img, postprocessed = generate_raw_word(word, model_suite)
        diag = diagnose_postprocessing(raw_img, target_word=word)
        summary = diag["summary"]

        print(f"\n{format_diagnostic(diag)}")

        result = {
            "word": word,
            "raw_ink_width": summary["raw_ink_width"],
            "final_ink_width": summary["final_ink_width"],
            "ink_width_lost": summary["ink_width_lost"],
            "ink_near_left_edge": summary["ink_near_left_edge"],
            "ink_near_right_edge": summary["ink_near_right_edge"],
        }

        if "ocr_before" in summary:
            result["ocr_before"] = summary["ocr_before"]
            result["ocr_after"] = summary["ocr_after"]

        # Classify cause
        if summary["ink_near_left_edge"] or summary["ink_near_right_edge"]:
            clipping_causes["generation"] += 1

        for layer in ("layer2_body_zone", "layer3_cluster", "layer3b_gray_cleanup"):
            removed = (diag[layer].get("cols_removed_left25", 0) +
                       diag[layer].get("cols_removed_right25", 0))
            if removed > 3:
                clipping_causes[layer] += 1

        results.append(result)

    # Log summary
    print("\n\n=== CLIPPING CAUSE SUMMARY ===")
    for cause, count in sorted(clipping_causes.items(), key=lambda x: -x[1]):
        print(f"  {cause}: {count}/{len(test_words)} words affected")

    # Save results for analysis
    output = {
        "words": results,
        "clipping_causes": clipping_causes,
    }
    with open("tests/medium/diagnostic_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to tests/medium/diagnostic_results.json")

    # This test is diagnostic -- it always passes but logs findings
    # The assertion is just that we successfully analyzed 10+ words
    assert len(results) >= 10, f"Expected 10+ words analyzed, got {len(results)}"
