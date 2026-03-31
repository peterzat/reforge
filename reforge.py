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
        "--steps", type=int, default=50,
        help="DDIM sampling steps (default: 50)."
    )
    parser.add_argument(
        "--guidance-scale", type=float, default=3.0,
        help="CFG guidance scale (default: 3.0, set 1.0 to disable)."
    )
    parser.add_argument(
        "--candidates", type=int, default=3,
        help="Best-of-N candidates per word (default: 3)."
    )
    parser.add_argument(
        "--device", type=str, default="cuda",
        help="Torch device (default: cuda)."
    )

    args = parser.parse_args()

    # Handle escaped newlines in text
    text = args.text.replace("\\n", "\n")

    from reforge.pipeline import run

    result = run(
        style_path=args.style,
        style_image_paths=args.style_images,
        text=text,
        output_path=args.output,
        num_steps=args.steps,
        guidance_scale=args.guidance_scale,
        num_candidates=args.candidates,
        device=args.device,
    )

    print(f"Output saved to: {result['output_path']}")
    print("Quality scores:")
    for k, v in result["quality_scores"].items():
        print(f"  {k}: {v:.3f}")


if __name__ == "__main__":
    main()
