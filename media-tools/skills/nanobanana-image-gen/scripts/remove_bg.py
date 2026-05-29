#!/usr/bin/env python3
"""
Remove background from images using rembg.
Self-bootstrapping: creates venv with uv if needed.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Skill directory (parent of scripts/)
SKILL_DIR = Path(__file__).parent.parent
VENV_DIR = SKILL_DIR / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"


def ensure_venv():
    """Ensure venv exists and dependencies are installed. Re-exec if needed."""
    if sys.prefix == str(VENV_DIR):
        return

    if not VENV_PYTHON.exists():
        print("Setting up virtual environment...")
        subprocess.run(["uv", "venv", str(VENV_DIR)], cwd=SKILL_DIR, check=True)
        subprocess.run(["uv", "pip", "install", "-e", str(SKILL_DIR)],
                      env={**os.environ, "VIRTUAL_ENV": str(VENV_DIR)},
                      check=True)
        print("Setup complete.\n")

    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)


ensure_venv()

# Now safe to import dependencies
from PIL import Image
from rembg import remove, new_session

# Available models (most useful ones)
MODELS = {
    "u2net": "General purpose (default)",
    "u2netp": "Lightweight, faster",
    "u2net_human_seg": "Optimized for humans",
    "isnet-general-use": "High accuracy general",
    "isnet-anime": "Anime characters",
    "birefnet-general": "Best quality, slower",
}

DEFAULT_MODEL = "u2net"


def remove_background(
    input_path: str,
    output_path: str = None,
    model: str = None,
    alpha_matting: bool = False,
) -> str:
    """
    Remove background from an image.

    Args:
        input_path: Path to input image
        output_path: Where to save (optional, auto-generates if not provided)
        model: Model to use (see MODELS dict)
        alpha_matting: Use alpha matting for better edges (slower)

    Returns:
        Path to saved image with transparent background
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Image not found: {input_path}")

    model_name = model or DEFAULT_MODEL
    print(f"Using model: {model_name}")
    print(f"Processing: {input_path}")

    # Load image
    img = Image.open(input_path)

    # Create session with specified model
    session = new_session(model_name)

    # Remove background
    result = remove(
        img,
        session=session,
        alpha_matting=alpha_matting,
        alpha_matting_foreground_threshold=240 if alpha_matting else None,
        alpha_matting_background_threshold=10 if alpha_matting else None,
    )

    # Determine output path
    if output_path is None:
        output_path = input_path.with_stem(f"{input_path.stem}_nobg").with_suffix(".png")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save as PNG with transparency
    result.save(output_path, "PNG")
    print(f"Saved: {output_path}")

    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Remove background from images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Available models:
{chr(10).join(f'  {k}: {v}' for k, v in MODELS.items())}
        """
    )
    parser.add_argument("input", help="Input image file")
    parser.add_argument("-o", "--output", help="Output file path (default: input_nobg.png)")
    parser.add_argument(
        "--model",
        choices=list(MODELS.keys()),
        default=DEFAULT_MODEL,
        help=f"Model to use (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--alpha-matting",
        action="store_true",
        help="Use alpha matting for better edges (slower)"
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available models and exit"
    )

    args = parser.parse_args()

    if args.list_models:
        print("Available models:")
        for name, desc in MODELS.items():
            print(f"  {name}: {desc}")
        return

    try:
        remove_background(
            args.input,
            args.output,
            args.model,
            args.alpha_matting,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
