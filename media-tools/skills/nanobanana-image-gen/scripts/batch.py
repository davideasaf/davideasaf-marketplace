#!/usr/bin/env python3
"""
Batch generate multiple images.
Self-bootstrapping: creates venv with uv if needed.
"""

import argparse
import json
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

# Import from generate.py (same package now)
from generate import generate_image, VALID_RESOLUTIONS, VALID_ASPECT_RATIOS


def json_prompt_to_text(prompt_obj: dict) -> str:
    """
    Convert a structured JSON prompt to natural language text.

    Supports schema:
    {
        "subject": {"main": "...", "material": "...", ...},
        "context": {"setting": "...", "props": "...", ...},
        "style": {"aesthetic": "...", "lighting": "...", ...},
        "technical": {"lens": "...", "camera": "...", ...}
    }

    Or simple flat structure:
    {"subject": "...", "style": "...", "lighting": "..."}
    """
    parts = []

    # Handle nested structure
    if isinstance(prompt_obj.get("subject"), dict):
        subject = prompt_obj.get("subject", {})
        context = prompt_obj.get("context", {})
        style = prompt_obj.get("style", {})
        technical = prompt_obj.get("technical", {})

        # Build subject description
        if subject:
            subject_parts = [subject.get("main", "")]
            for key in ["material", "color", "texture", "details"]:
                if key in subject:
                    subject_parts.append(subject[key])
            parts.append(", ".join(filter(None, subject_parts)))

        # Build context description
        if context:
            context_parts = []
            for key in ["setting", "environment", "background", "props"]:
                if key in context:
                    context_parts.append(context[key])
            if context_parts:
                parts.append(", ".join(context_parts))

        # Build style description
        if style:
            style_parts = []
            for key in ["aesthetic", "mood", "lighting", "colors"]:
                if key in style:
                    style_parts.append(style[key])
            if style_parts:
                parts.append(", ".join(style_parts))

        # Build technical description
        if technical:
            tech_parts = []
            for key in ["lens", "camera", "aperture", "focus"]:
                if key in technical:
                    tech_parts.append(technical[key])
            if tech_parts:
                parts.append(", ".join(tech_parts))
    else:
        # Handle flat structure - just join all values
        for key in ["subject", "style", "lighting", "mood", "background", "camera", "quality"]:
            if key in prompt_obj and prompt_obj[key]:
                parts.append(str(prompt_obj[key]))

    return ", ".join(filter(None, parts))


def generate_variations(
    base_prompt: str,
    variations: list[str],
    output_dir: str = None,
    model: str = None,
    resolution: str = None,
    aspect_ratio: str = None
) -> list[str]:
    """Generate multiple variations of a base prompt."""
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"batch_{timestamp}"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, variation in enumerate(variations, 1):
        prompt = f"{base_prompt}, {variation}"
        output_path = output_dir / f"variation_{i:02d}.png"

        print(f"\n[{i}/{len(variations)}] {variation}")
        try:
            path = generate_image(
                prompt,
                str(output_path),
                model,
                transparent=False,
                resolution=resolution,
                aspect_ratio=aspect_ratio
            )
            results.append(path)
        except Exception as e:
            print(f"  Failed: {e}")
            results.append(None)

    return results


def generate_from_file(
    prompts_file: str,
    output_dir: str = None,
    model: str = None,
    resolution: str = None,
    aspect_ratio: str = None
) -> list[str]:
    """Generate images from a file of prompts (text or JSON)."""
    path = Path(prompts_file)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {prompts_file}")

    # Try JSON, then plain text
    try:
        with open(path) as f:
            data = json.load(f)
        prompts = data if isinstance(data, list) else data.get("prompts", [])
    except json.JSONDecodeError:
        with open(path) as f:
            prompts = [line.strip() for line in f if line.strip()]

    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"batch_{timestamp}"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, prompt in enumerate(prompts, 1):
        output_path = output_dir / f"image_{i:02d}.png"
        # Handle string or dict prompts
        if isinstance(prompt, str):
            prompt_text = prompt
        else:
            prompt_text = json_prompt_to_text(prompt)
        print(f"\n[{i}/{len(prompts)}] {prompt_text[:60]}...")
        try:
            path = generate_image(
                prompt_text,
                str(output_path),
                model,
                transparent=False,
                resolution=resolution,
                aspect_ratio=aspect_ratio
            )
            results.append(path)
        except Exception as e:
            print(f"  Failed: {e}")
            results.append(None)

    return results


def generate_from_json(
    json_file: str,
    output_dir: str = None,
    model: str = None,
    resolution: str = None,
    aspect_ratio: str = None
) -> list[str]:
    """
    Generate images from structured JSON prompts.

    JSON file format - array of structured prompts:
    [
        {
            "subject": {"main": "coffee cup", "material": "ceramic"},
            "context": {"setting": "marble surface"},
            "style": {"aesthetic": "minimalist", "lighting": "soft studio"},
            "technical": {"lens": "85mm f/2.8"}
        },
        ...
    ]

    Or object with prompts array:
    {"prompts": [...]}
    """
    path = Path(json_file)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {json_file}")

    with open(path) as f:
        data = json.load(f)

    # Handle both array and {prompts: [...]} formats
    prompts = data if isinstance(data, list) else data.get("prompts", [])

    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"batch_json_{timestamp}"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"JSON mode: Processing {len(prompts)} structured prompts")

    results = []
    for i, prompt_obj in enumerate(prompts, 1):
        # Convert JSON structure to text prompt
        prompt_text = json_prompt_to_text(prompt_obj)
        output_path = output_dir / f"image_{i:02d}.png"

        print(f"\n[{i}/{len(prompts)}] {prompt_text[:60]}...")
        try:
            path = generate_image(
                prompt_text,
                str(output_path),
                model,
                transparent=False,
                resolution=resolution,
                aspect_ratio=aspect_ratio
            )
            results.append(path)
        except Exception as e:
            print(f"  Failed: {e}")
            results.append(None)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Batch generate images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Variations mode
  batch.py --variations "mountain landscape" "at sunset" "at night" "in winter"

  # File mode (plain text, one prompt per line)
  batch.py --file prompts.txt

  # JSON mode (structured prompts for product/brand consistency)
  batch.py --json prompts.json -r 4k

  # With resolution and aspect ratio
  batch.py --variations "product shot" "white bg" "black bg" -r 4k -a 16:9
"""
    )
    parser.add_argument("--variations", nargs="+", metavar=("BASE", "VAR"),
                        help="Base prompt + variations")
    parser.add_argument("--file", "-f", help="File with prompts (text or JSON)")
    parser.add_argument("--json", "-j", help="JSON file with structured prompts")
    parser.add_argument("-o", "--output", help="Output directory")
    parser.add_argument("--model", help="Model to use")
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

    if not args.variations and not args.file and not args.json:
        parser.error("One of --variations, --file, or --json required")

    try:
        if args.json:
            results = generate_from_json(
                args.json,
                args.output,
                args.model,
                args.resolution,
                args.aspect_ratio
            )
        elif args.variations:
            if len(args.variations) < 2:
                parser.error("Need base prompt + at least one variation")
            results = generate_variations(
                args.variations[0],
                args.variations[1:],
                args.output,
                args.model,
                args.resolution,
                args.aspect_ratio
            )
        else:
            results = generate_from_file(
                args.file,
                args.output,
                args.model,
                args.resolution,
                args.aspect_ratio
            )

        success = sum(1 for r in results if r)
        print(f"\n{'='*40}")
        print(f"Generated: {success}/{len(results)} images")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
