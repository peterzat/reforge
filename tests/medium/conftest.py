"""Shared fixtures for medium tests. Models load once per session."""

import pytest
import torch
import cv2

SKIP_REASON = "Requires CUDA GPU"


def pytest_addoption(parser):
    parser.addoption(
        "--update-baseline", action="store_true", default=False,
        help="Regenerate quality_baseline.json unconditionally",
    )
    parser.addoption(
        "--update-reference", action="store_true", default=False,
        help="Regenerate reference_output.png unconditionally",
    )


@pytest.fixture(scope="session")
def device():
    if not torch.cuda.is_available():
        pytest.skip(SKIP_REASON)
    return "cuda"


@pytest.fixture(scope="session")
def style_word_images():
    """Segmented style reference word images (numpy grayscale arrays)."""
    from reforge.preprocess.segment import segment_sentence_image
    style_img = cv2.imread("styles/hw-sample.png", cv2.IMREAD_GRAYSCALE)
    words = segment_sentence_image(style_img)
    assert len(words) == 5
    return words


@pytest.fixture(scope="session")
def style_features(device):
    from reforge.model.encoder import StyleEncoder
    from reforge.model.weights import download_style_encoder_weights
    from reforge.preprocess.normalize import preprocess_words
    from reforge.preprocess.segment import segment_sentence_image

    style_img = cv2.imread("styles/hw-sample.png", cv2.IMREAD_GRAYSCALE)
    words = segment_sentence_image(style_img)
    assert len(words) == 5
    style_tensors = preprocess_words(words)

    style_ckpt = download_style_encoder_weights()
    encoder = StyleEncoder(checkpoint_path=style_ckpt).to(device)
    features = encoder.encode(style_tensors)
    return features


@pytest.fixture(scope="session")
def unet(device):
    from reforge.model.weights import download_unet_weights, load_unet
    ckpt = download_unet_weights()
    return load_unet(ckpt, device=device)


@pytest.fixture(scope="session")
def vae(device):
    from reforge.model.weights import load_vae
    return load_vae(device=device)


@pytest.fixture(scope="session")
def tokenizer():
    from reforge.model.weights import load_tokenizer
    return load_tokenizer()


@pytest.fixture(scope="session")
def uncond_context(tokenizer):
    return tokenizer(" ", return_tensors="pt", padding="max_length", max_length=16)
