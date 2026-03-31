"""Model weight loading and HuggingFace download utilities.

State dict loading strips both `module.` prefixes from DataParallel-wrapped
checkpoint keys.
"""

import os
from pathlib import Path
from types import SimpleNamespace

import torch
from huggingface_hub import hf_hub_download

from reforge.config import (
    CANINE_MODEL_ID,
    HF_REPO_ID,
    SD_MODEL_ID,
    STYLE_ENCODER_TRIPLET_PATH,
    UNET_ATTENTION_RESOLUTIONS,
    UNET_CHANNEL_MULT,
    UNET_CONTEXT_DIM,
    UNET_IMAGE_SIZE,
    UNET_IN_CHANNELS,
    UNET_MODEL_CHANNELS,
    UNET_NUM_CLASSES,
    UNET_NUM_HEADS,
    UNET_NUM_RES_BLOCKS,
    UNET_OUT_CHANNELS,
    UNET_VOCAB_SIZE,
    UNET_WEIGHT_PATH,
)


def strip_module_prefix(state_dict: dict) -> dict:
    """Strip `module.` prefixes from DataParallel-wrapped state dict keys.

    Handles double-wrapped keys like `module.text_encoder.module.char_embeddings.*`.
    """
    cleaned = {}
    for key, value in state_dict.items():
        new_key = key
        # Strip all occurrences of `module.` prefix at any level
        while ".module." in new_key:
            new_key = new_key.replace(".module.", ".")
        if new_key.startswith("module."):
            new_key = new_key[len("module."):]
        cleaned[new_key] = value
    return cleaned


def download_unet_weights() -> str:
    """Download UNet checkpoint from HuggingFace. Returns local path."""
    return hf_hub_download(repo_id=HF_REPO_ID, filename=UNET_WEIGHT_PATH)


def download_style_encoder_weights(variant: str = "triplet") -> str:
    """Download style encoder weights. variant is 'triplet' or 'class'."""
    if variant == "triplet":
        filename = STYLE_ENCODER_TRIPLET_PATH
    elif variant == "class":
        from reforge.config import STYLE_ENCODER_CLASS_PATH
        filename = STYLE_ENCODER_CLASS_PATH
    else:
        raise ValueError(f"Unknown variant: {variant}")
    return hf_hub_download(repo_id=HF_REPO_ID, filename=filename)


def load_unet(checkpoint_path: str, device: str = "cuda") -> "UNetModel":
    """Load the DiffusionPen UNet with proper state dict handling."""
    from transformers import CanineModel
    from reforge.diffusionpen.unet import UNetModel

    text_encoder = CanineModel.from_pretrained(CANINE_MODEL_ID)

    args = SimpleNamespace(interpolation=False, mix_rate=0.0)
    model = UNetModel(
        image_size=UNET_IMAGE_SIZE,
        in_channels=UNET_IN_CHANNELS,
        model_channels=UNET_MODEL_CHANNELS,
        out_channels=UNET_OUT_CHANNELS,
        num_res_blocks=UNET_NUM_RES_BLOCKS,
        attention_resolutions=UNET_ATTENTION_RESOLUTIONS,
        channel_mult=UNET_CHANNEL_MULT,
        num_heads=UNET_NUM_HEADS,
        num_classes=UNET_NUM_CLASSES,
        context_dim=UNET_CONTEXT_DIM,
        vocab_size=UNET_VOCAB_SIZE,
        text_encoder=text_encoder,
        args=args,
    )

    state_dict = torch.load(checkpoint_path, map_location="cpu")
    cleaned = strip_module_prefix(state_dict)
    model.load_state_dict(cleaned, strict=False)
    model = model.to(device)
    model.eval()
    return model


def load_vae(device: str = "cuda"):
    """Load the SD 1.5 VAE."""
    from diffusers import AutoencoderKL
    vae = AutoencoderKL.from_pretrained(SD_MODEL_ID, subfolder="vae")
    vae = vae.to(device)
    vae.eval()
    return vae


def load_tokenizer():
    """Load the Canine-C tokenizer."""
    from transformers import CanineTokenizer
    return CanineTokenizer.from_pretrained(CANINE_MODEL_ID)
