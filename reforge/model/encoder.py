"""StyleEncoder: MobileNetV2 backbone producing raw (5, 1280) features.

Returns raw features WITHOUT mean-pooling. The UNet does its own
reshape(b, 5, -1) + mean internally.
"""

import torch
import torch.nn as nn

from reforge.config import NUM_STYLE_WORDS, STYLE_FEATURE_DIM


class StyleEncoder(nn.Module):
    """Wraps the DiffusionPen ImageEncoder (timm MobileNetV2).

    Encodes 5 style word images into (5, 1280) raw features.
    """

    def __init__(self, checkpoint_path: str | None = None):
        super().__init__()
        from reforge.diffusionpen.feature_extractor import ImageEncoder

        self.encoder = ImageEncoder(model_name="mobilenetv2_100", pretrained=False)
        if checkpoint_path is not None:
            state_dict = torch.load(checkpoint_path, map_location="cpu")
            self.encoder.load_state_dict(state_dict)
        self.encoder.eval()

    @torch.no_grad()
    def encode(self, style_tensors: list[torch.Tensor]) -> torch.Tensor:
        """Encode 5 style word tensors into raw features.

        Args:
            style_tensors: List of 5 tensors, each (1, 3, 64, 256).

        Returns:
            Tensor of shape (5, 1280) -- raw features, no mean-pooling.
        """
        assert len(style_tensors) == NUM_STYLE_WORDS, (
            f"Expected {NUM_STYLE_WORDS} style tensors, got {len(style_tensors)}"
        )

        # Stack into (5, 3, 64, 256)
        batch = torch.cat(style_tensors, dim=0)
        device = next(self.encoder.parameters()).device
        batch = batch.to(device)

        # ImageEncoder returns (5, 1280)
        features = self.encoder(batch)
        assert features.shape == (NUM_STYLE_WORDS, STYLE_FEATURE_DIM), (
            f"Expected ({NUM_STYLE_WORDS}, {STYLE_FEATURE_DIM}), got {features.shape}"
        )

        return features
