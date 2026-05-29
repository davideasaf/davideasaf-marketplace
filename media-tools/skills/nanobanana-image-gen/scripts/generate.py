#!/usr/bin/env python3
"""
Generate images using Gemini API with OAuth credentials.
Self-bootstrapping: creates venv with uv if needed.
Supports transparent background generation via --transparent flag.
"""

import argparse
import base64
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Skill directory (parent of scripts/)
SKILL_DIR = Path(__file__).parent.parent
VENV_DIR = SKILL_DIR / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"


def ensure_venv():
    """Ensure venv exists and dependencies are installed. Re-exec if needed."""
    # If we're already in the venv, continue
    if sys.prefix == str(VENV_DIR):
        return

    # Check if venv exists
    if not VENV_PYTHON.exists():
        print("Setting up virtual environment...")
        subprocess.run(["uv", "venv", str(VENV_DIR)], cwd=SKILL_DIR, check=True)
        subprocess.run(["uv", "pip", "install", "-e", str(SKILL_DIR)],
                      env={**os.environ, "VIRTUAL_ENV": str(VENV_DIR)},
                      check=True)
        print("Setup complete.\n")

    # Re-exec with venv python
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)


# Bootstrap before imports that need dependencies
ensure_venv()

# Now safe to import dependencies
from google import genai
from google.genai import types
from PIL import Image
from rembg import remove, new_session

# Import from auth.py (same package now)
from auth import require_correct_account

# Configuration
DEFAULT_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image-preview")
TRANSPARENT_BG_MODEL = "u2net"  # Fast and good for most cases

# Valid resolution and aspect ratio options
VALID_RESOLUTIONS = ["1k", "2k", "4k"]
VALID_ASPECT_RATIOS = ["1:1", "4:3", "3:4", "16:9", "9:16", "21:9"]


def create_client():
    """Create Gemini client using Application Default Credentials."""
    require_correct_account()
    return genai.Client()


def generate_image(
    prompt: str,
    output_path: str = None,
    model: str = None,
    transparent: bool = False,
    resolution: str = None,
    aspect_ratio: str = None
) -> str:
    """
    Generate an image from a text prompt.

    Args:
        prompt: Text description of the image to generate
        output_path: Where to save the image (optional, auto-generates if not provided)
        model: Model to use (optional, uses DEFAULT_MODEL)
        transparent: If True, generate with green background and remove it
        resolution: Image resolution - 1k, 2k, or 4k (optional)
        aspect_ratio: Aspect ratio like 1:1, 16:9, etc. (optional)

    Returns:
        Path to the saved image file
    """
    client = create_client()
    model_name = model or DEFAULT_MODEL

    # Modify prompt for transparent background workflow
    actual_prompt = prompt
    if transparent:
        actual_prompt = f"{prompt}. On a solid bright green #00FF00 background, isolated object, no shadows on the background."
        print("Transparent mode: Will generate with green background and remove it")

    print(f"Using model: {model_name}")
    if resolution:
        print(f"Resolution: {resolution.upper()}")
    if aspect_ratio:
        print(f"Aspect ratio: {aspect_ratio}")
    print(f"Generating: {actual_prompt[:80]}{'...' if len(actual_prompt) > 80 else ''}")

    # Build generation config
    config_kwargs = {"response_modalities": ["IMAGE"]}
    if resolution:
        # Gemini requires uppercase K (1K, 2K, 4K)
        config_kwargs["image_size"] = resolution.upper()
    if aspect_ratio:
        config_kwargs["aspect_ratio"] = aspect_ratio

    response = client.models.generate_content(
        model=model_name,
        contents=actual_prompt,
        config=types.GenerateContentConfig(**config_kwargs)
    )

    # Determine output path
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"generated_{timestamp}.png"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Extract the image data
    image_data = None
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            image_data = part.inline_data.data
            if isinstance(image_data, str):
                image_data = base64.b64decode(image_data)
            break

    if image_data is None:
        # If we got text instead
        for part in response.candidates[0].content.parts:
            if part.text:
                print(f"Model returned text: {part.text[:200]}")
        raise RuntimeError("Model did not generate an image")

    # If transparent mode, remove the background
    if transparent:
        print("Removing background...")
        # Save to temp file first
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(image_data)
            tmp_path = tmp.name

        try:
            # Load and remove background
            img = Image.open(tmp_path)
            session = new_session(TRANSPARENT_BG_MODEL)
            result = remove(img, session=session)
            result.save(output_path, "PNG")
            print(f"Saved (transparent): {output_path}")
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
    else:
        # Normal save
        output_path.write_bytes(image_data)
        print(f"Saved: {output_path}")

    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="Generate images using Gemini API")
    parser.add_argument("prompt", help="Text description of the image")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("--model", help=f"Model (default: {DEFAULT_MODEL})")
    parser.add_argument(
        "--transparent", "-t",
        action="store_true",
        help="Generate with transparent background (uses green-screen + rembg)"
    )
    parser.add_argument(
        "-r", "--resolution",
        choices=VALID_RESOLUTIONS,
        help="Image resolution: 1k (default), 2k, or 4k"
    )
    parser.add_argument(
        "-a", "--aspect-ratio",
        choices=VALID_ASPECT_RATIOS,
        help="Aspect ratio: 1:1, 4:3, 3:4, 16:9, 9:16, 21:9"
    )

    args = parser.parse_args()

    try:
        generate_image(
            args.prompt,
            args.output,
            args.model,
            args.transparent,
            args.resolution,
            args.aspect_ratio
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
