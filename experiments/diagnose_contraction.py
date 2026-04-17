"""Diagnose the "cantt"/"itss" failure mode by capturing every contraction
intermediate as a separate image. Throwaway: identifies which component
(left DP word, synthetic apostrophe, right DP word, or stitching geometry)
contributes the extra-letter read.

At fixed seed 42, for each of can't / it's / don't / they'd / we'll:
    1. Generate left part via DP + postprocess + descender pad
    2. Generate right part via DP + postprocess + descender pad
    3. Render synthetic apostrophe from left part's ink properties
    4. Stitch left + apostrophe + right

Each intermediate + a side-by-side sheet are saved under
experiments/output/cantt_diagnosis/. Run qpeek --batch on the sheets to
inspect.
"""

import os
import sys

import cv2
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reforge.config import PRESET_QUALITY, WIDTH_MULTIPLE, MAX_CANVAS_WIDTH  # noqa: E402
from reforge.model.encoder import StyleEncoder  # noqa: E402
from reforge.model.generator import (  # noqa: E402
    compute_canvas_width,
    ddim_sample,
    is_contraction,
    make_synthetic_apostrophe,
    pad_clipped_descender,
    postprocess_word,
    split_contraction,
    stitch_contraction,
)
from reforge.model.weights import (  # noqa: E402
    download_style_encoder_weights,
    download_unet_weights,
    load_tokenizer,
    load_unet,
    load_vae,
)
from reforge.preprocess.normalize import preprocess_words  # noqa: E402
from reforge.preprocess.segment import segment_sentence_image  # noqa: E402
from reforge.quality.ink_metrics import compute_x_height  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLE_PATH = os.path.join(REPO, "styles", "hw-sample.png")
OUT_DIR = os.path.join(REPO, "experiments", "output", "cantt_diagnosis")
WORDS = ["can't", "it's", "don't", "they'd", "we'll"]
SEED = 42


def _pad_to_height(img: np.ndarray, h: int) -> np.ndarray:
    if img.shape[0] >= h:
        return img
    pad = h - img.shape[0]
    top = pad // 2
    bot = pad - top
    return cv2.copyMakeBorder(img, top, bot, 0, 0, cv2.BORDER_CONSTANT, value=255)


def _sheet(stages: list[tuple[str, np.ndarray]]) -> np.ndarray:
    """Horizontal side-by-side strip with labels above each stage."""
    max_h = max(img.shape[0] for _, img in stages)
    padded = [_pad_to_height(img, max_h) for _, img in stages]
    gap = 255 * np.ones((max_h, 20), dtype=np.uint8)
    strips = []
    for p in padded:
        strips.append(p)
        strips.append(gap)
    strips.pop()
    row = np.concatenate(strips, axis=1)
    label_h = 24
    label_row = 255 * np.ones((label_h, row.shape[1]), dtype=np.uint8)
    x_off = 0
    for (name, img), p in zip(stages, padded):
        cv2.putText(
            label_row, name, (x_off + 4, 16),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, 80, 1, cv2.LINE_AA,
        )
        x_off += p.shape[1] + 20
    return np.concatenate([label_row, row], axis=0)


def gen_part(
    text: str,
    unet,
    vae,
    tokenizer,
    style_features,
    uncond_context,
    is_right_side: bool,
    num_steps: int,
    guidance_scale: float,
    device: str,
) -> np.ndarray:
    """Mirror of _generate_contraction._gen_part with num_candidates=1 for
    reproducibility. The candidate best-of-N is a separate axis; isolating
    single-candidate output shows what DP's raw generation looks like.
    """
    from reforge.config import CONTRACTION_RIGHT_SIDE_WIDTH

    canvas_width = compute_canvas_width(len(text))
    if is_right_side and CONTRACTION_RIGHT_SIDE_WIDTH is not None and len(text) <= 2:
        override = CONTRACTION_RIGHT_SIDE_WIDTH
        override = ((override + WIDTH_MULTIPLE - 1) // WIDTH_MULTIPLE) * WIDTH_MULTIPLE
        override = max(WIDTH_MULTIPLE * 4, min(override, MAX_CANVAS_WIDTH))
        canvas_width = override
    text_ctx = tokenizer(text, return_tensors="pt", padding="max_length", max_length=16)
    img = ddim_sample(
        unet, vae, text_ctx, style_features,
        uncond_context=uncond_context,
        canvas_width=canvas_width,
        num_steps=num_steps,
        guidance_scale=guidance_scale,
        device=device,
    )
    img = postprocess_word(img)
    img = pad_clipped_descender(img)
    return img


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device != "cuda":
        print("WARNING: running on CPU; will be very slow", file=sys.stderr)

    os.makedirs(OUT_DIR, exist_ok=True)

    print("Loading models...", file=sys.stderr)
    style_img = cv2.imread(STYLE_PATH, cv2.IMREAD_GRAYSCALE)
    words = segment_sentence_image(style_img)
    assert len(words) == 5
    style_tensors = preprocess_words(words)

    encoder = StyleEncoder(checkpoint_path=download_style_encoder_weights()).to(device)
    style_features = encoder.encode(style_tensors)

    unet = load_unet(download_unet_weights(), device=device)
    vae = load_vae(device=device)
    tokenizer = load_tokenizer()
    uncond_context = tokenizer(" ", return_tensors="pt", padding="max_length", max_length=16)

    preset = PRESET_QUALITY
    notes = []
    notes.append(f"# Contraction diagnosis — seed {SEED}\n")
    notes.append(f"preset: steps={preset['steps']} guidance={preset['guidance_scale']} candidates=1\n")
    notes.append("")
    notes.append("Each row is one contraction. Columns: DP left, synthetic apostrophe, DP right, stitched.\n")
    notes.append("")

    for word in WORDS:
        assert is_contraction(word), f"{word} is not detected as a contraction"
        left_text, right_text = split_contraction(word)

        torch.manual_seed(SEED)
        np.random.seed(SEED)

        left_img = gen_part(
            left_text, unet, vae, tokenizer, style_features, uncond_context,
            is_right_side=False,
            num_steps=preset["steps"], guidance_scale=preset["guidance_scale"],
            device=device,
        )
        right_img = gen_part(
            right_text, unet, vae, tokenizer, style_features, uncond_context,
            is_right_side=True,
            num_steps=preset["steps"], guidance_scale=preset["guidance_scale"],
            device=device,
        )

        ink_pixels = left_img[left_img < 180]
        ink_intensity = int(np.median(ink_pixels)) if len(ink_pixels) > 0 else 60
        body_h = compute_x_height(left_img)
        apostrophe_img = make_synthetic_apostrophe(ink_intensity, body_h)

        stitched = stitch_contraction(
            left_img, apostrophe_img, right_img,
            right_part_len=len(right_text),
        )

        safe_name = word.replace("'", "_")
        cv2.imwrite(os.path.join(OUT_DIR, f"{safe_name}_1_left.png"), left_img)
        cv2.imwrite(os.path.join(OUT_DIR, f"{safe_name}_2_apostrophe.png"), apostrophe_img)
        cv2.imwrite(os.path.join(OUT_DIR, f"{safe_name}_3_right.png"), right_img)
        cv2.imwrite(os.path.join(OUT_DIR, f"{safe_name}_4_stitched.png"), stitched)

        sheet = _sheet([
            (f"{left_text} (DP)", left_img),
            ("' (synth)", apostrophe_img),
            (f"{right_text} (DP)", right_img),
            (f"{word} (stitched)", stitched),
        ])
        cv2.imwrite(os.path.join(OUT_DIR, f"{safe_name}_sheet.png"), sheet)

        notes.append(f"## {word}")
        notes.append("")
        notes.append(f"- left: {left_text} ({left_img.shape[1]}x{left_img.shape[0]}, ink intensity median {ink_intensity})")
        notes.append(f"- apostrophe: body_h={body_h}, size {apostrophe_img.shape[1]}x{apostrophe_img.shape[0]}")
        notes.append(f"- right: {right_text} ({right_img.shape[1]}x{right_img.shape[0]})")
        notes.append(f"- stitched: {stitched.shape[1]}x{stitched.shape[0]}")
        notes.append("- observation: TODO (fill in after qpeek)")
        notes.append("")

        print(f"{word}: left={left_img.shape} apostrophe={apostrophe_img.shape} "
              f"right={right_img.shape} stitched={stitched.shape}", file=sys.stderr)

    note_path = os.path.join(OUT_DIR, "cantt_diagnosis.md")
    with open(note_path, "w") as f:
        f.write("\n".join(notes))

    print("", file=sys.stderr)
    print(f"Images: {OUT_DIR}/*_sheet.png", file=sys.stderr)
    print(f"Notes:  {note_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
