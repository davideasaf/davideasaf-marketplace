#!/usr/bin/env python3
"""
Edit images using Gemini API with OAuth credentials.
Self-bootstrapping: creates venv with uv if needed.
"""

import argparse
import base64
import os
import subprocess
import sys
from datetime import datetime
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

from google import genai
from google.genai import types
from PIL import Image

# Import from auth.py (same package now)
from auth import require_correct_account

# Configuration
DEFAULT_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")

# Valid resolution options
VALID_RESOLUTIONS = ["1k", "2k", "4k"]


def create_client():
    """Create Gemini client using Application Default Credentials."""
    require_correct_account()
    return genai.Client()


def edit_image(
    input_path: str,
    instruction: str,
    output_path: str = None,
    model: str = None,
    resolution: str = None
) -> str:
    """
    Edit an image based on natural language instructions.

    Args:
        input_path: Path to the input image
        instruction: What to change about the image
        output_path: Where to save the result (optional)
        model: Model to use (optional)
        resolution: Output resolution - 1k, 2k, or 4k (optional)

    Returns:
        Path to the saved edited image
    """
    client = create_client()
    model_name = model or DEFAULT_MODEL

    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Image not found: {input_path}")

    print(f"Using model: {model_name}")
    if resolution:
        print(f"Resolution: {resolution.upper()}")
    print(f"Editing: {input_path}")
    print(f"Instruction: {instruction[:80]}{'...' if len(instruction) > 80 else ''}")

    # Load image
    image = Image.open(input_path)

    # Create edit prompt
    edit_prompt = f"Edit this image: {instruction}"

    # Build generation config
    config_kwargs = {"response_modalities": ["IMAGE"]}
    if resolution:
        config_kwargs["image_size"] = resolution.upper()

    response = client.models.generate_content(
        model=model_name,
        contents=[edit_prompt, image],
        config=types.GenerateContentConfig(**config_kwargs)
    )

    # Determine output path
    if output_path is None:
        timestamp = datetime.now().strftime("%H%M%S")
        output_path = f"{input_path.stem}_edited_{timestamp}.png"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Extract and save
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            image_data = part.inline_data.data
            if isinstance(image_data, str):
                image_data = base64.b64decode(image_data)
            output_path.write_bytes(image_data)
            print(f"Saved: {output_path}")
            return str(output_path)

    raise RuntimeError("Model did not return an edited image")


def main():
    parser = argparse.ArgumentParser(description="Edit images using Gemini API")
    parser.add_argument("input", help="Input image file")
    parser.add_argument("instruction", help="What to change")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("--model", help=f"Model (default: {DEFAULT_MODEL})")
    parser.add_argument(
        "-r", "--resolution",
        choices=VALID_RESOLUTIONS,
        help="Output resolution: 1k, 2k, or 4k"
    )

    args = parser.parse_args()

    try:
        edit_image(args.input, args.instruction, args.output, args.model, args.resolution)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
