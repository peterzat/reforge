"""CLI entry point for reforge."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Generate handwritten text from a style reference image."
    )
    parser.add_argument(
        "--style", type=str, default=None,
        help="Path to a handwritten sentence image (5 words, each >= 4 chars)."
    )
    parser.add_argument(
        "--style-images", type=str, nargs="+", default=None,
        help="Paths to exactly 5 pre-segmented word images."
    )
    parser.add_argument(
        "--text", type=str, required=True,
        help='Text to generate. Use \\n for paragraph breaks.'
    )
    parser.add_argument(
        "--output", type=str, default="result.png",
        help="Output PNG path (default: result.png)."
    )
    parser.add_argument(
        "--preset", type=str, default="quality",
        choices=["draft", "fast", "quality"],
        help="Generation preset (default: quality). Sets steps, guidance, candidates."
    )
    parser.add_argument(
        "--steps", type=int, default=None,
        help="DDIM sampling steps (overrides preset)."
    )
    parser.add_argument(
        "--guidance-scale", type=float, default=None,
        help="CFG guidance scale (overrides preset, set 1.0 to disable)."
    )
    parser.add_argument(
        "--candidates", type=int, default=None,
        help="Best-of-N candidates per word (overrides preset)."
    )
    parser.add_argument(
        "--device", type=str, default=None,
        help="Torch device (default: auto-detect cuda/cpu)."
    )
    parser.add_argument(
        "--page-ratio", type=str, default="auto",
        help="Page aspect ratio mode. 'auto' targets near-square output (default: auto)."
    )

    args = parser.parse_args()

    # Handle escaped newlines in text
    text = args.text.replace("\\n", "\n")

    # Resolve preset + individual overrides
    from reforge.config import PRESETS
    preset = PRESETS[args.preset]
    num_steps = args.steps if args.steps is not None else preset["steps"]
    guidance_scale = args.guidance_scale if args.guidance_scale is not None else preset["guidance_scale"]
    num_candidates = args.candidates if args.candidates is not None else preset["candidates"]

    from reforge.pipeline import run

    run(
        style_path=args.style,
        style_image_paths=args.style_images,
        text=text,
        output_path=args.output,
        num_steps=num_steps,
        guidance_scale=guidance_scale,
        num_candidates=num_candidates,
        device=args.device,
        page_ratio=args.page_ratio,
    )


if __name__ == "__main__":
    main()
