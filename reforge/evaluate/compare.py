"""A/B comparison image generation with labels."""

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def create_comparison_image(
    images: list[np.ndarray],
    labels: list[str],
    scores: list[dict] | None = None,
    title: str = "",
) -> Image.Image:
    """Create a labeled comparison PNG from multiple generated images.

    Args:
        images: List of grayscale uint8 arrays to compare.
        labels: Label for each image.
        scores: Optional quality score dicts for each image.
        title: Optional title at top.

    Returns:
        PIL Image with labeled comparison grid.
    """
    if not images:
        return Image.new("L", (400, 100), 255)

    label_height = 30
    score_height = 20 if scores else 0
    spacing = 10
    max_w = max(img.shape[1] for img in images)
    total_h = sum(img.shape[0] + label_height + score_height + spacing for img in images)

    if title:
        total_h += 40

    canvas = Image.new("L", (max_w + 20, total_h + 20), 255)
    draw = ImageDraw.Draw(canvas)

    y = 10
    if title:
        draw.text((10, y), title, fill=0)
        y += 40

    for i, (img, label) in enumerate(zip(images, labels)):
        # Label
        draw.text((10, y), label, fill=0)
        y += label_height

        # Score
        if scores and i < len(scores):
            score_text = "  ".join(f"{k}={v:.2f}" for k, v in scores[i].items() if k != "overall")
            overall = scores[i].get("overall", 0)
            score_text = f"overall={overall:.2f}  {score_text}"
            draw.text((10, y), score_text, fill=80)
            y += score_height

        # Image
        pil_img = Image.fromarray(img, mode="L")
        canvas.paste(pil_img, (10, y))
        y += img.shape[0] + spacing

    return canvas
