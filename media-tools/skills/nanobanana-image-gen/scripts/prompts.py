#!/usr/bin/env python3
"""
Prompt library tools for nanobanana image generation.
Search, browse, and build prompts from curated examples.
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path

# Skill directory (parent of scripts/)
SKILL_DIR = Path(__file__).parent.parent
PROMPTS_DIR = SKILL_DIR / "references" / "prompts"


def load_prompts() -> dict:
    """Load all prompts from the library."""
    prompts = {}
    if not PROMPTS_DIR.exists():
        return prompts

    for json_file in PROMPTS_DIR.glob("*.json"):
        category = json_file.stem
        try:
            with open(json_file) as f:
                prompts[category] = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse {json_file}", file=sys.stderr)

    return prompts


def cmd_categories(args):
    """List all available prompt categories."""
    prompts = load_prompts()

    if not prompts:
        print("No prompt categories found.")
        print(f"Add JSON files to: {PROMPTS_DIR}")
        return

    print("Available categories:\n")
    for category, items in sorted(prompts.items()):
        count = len(items) if isinstance(items, list) else len(items.get("prompts", []))
        print(f"  {category:<20} ({count} prompts)")


def cmd_search(args):
    """Search prompts by keyword."""
    prompts = load_prompts()
    query = args.query.lower()
    results = []

    for category, items in prompts.items():
        prompt_list = items if isinstance(items, list) else items.get("prompts", [])
        for prompt in prompt_list:
            # Handle both string and dict prompts
            if isinstance(prompt, str):
                text = prompt
            else:
                text = json.dumps(prompt)

            if query in text.lower():
                results.append({
                    "category": category,
                    "prompt": prompt
                })

    if not results:
        print(f"No prompts found matching: {args.query}")
        return

    print(f"Found {len(results)} prompts matching '{args.query}':\n")

    limit = args.limit or 10
    for i, result in enumerate(results[:limit], 1):
        print(f"[{result['category']}]")
        if isinstance(result["prompt"], str):
            print(f"  {result['prompt'][:100]}{'...' if len(result['prompt']) > 100 else ''}")
        else:
            print(f"  {json.dumps(result['prompt'], indent=2)[:200]}")
        print()

    if len(results) > limit:
        print(f"... and {len(results) - limit} more. Use --limit to show more.")


def cmd_example(args):
    """Get an example prompt from a category."""
    prompts = load_prompts()
    category = args.category

    if category not in prompts:
        print(f"Category not found: {category}")
        print(f"Available: {', '.join(sorted(prompts.keys()))}")
        return

    items = prompts[category]
    prompt_list = items if isinstance(items, list) else items.get("prompts", [])

    if not prompt_list:
        print(f"No prompts in category: {category}")
        return

    # Get random or specific index
    if args.index is not None:
        if args.index >= len(prompt_list):
            print(f"Index {args.index} out of range (0-{len(prompt_list)-1})")
            return
        prompt = prompt_list[args.index]
    else:
        prompt = random.choice(prompt_list)

    print(f"Example from '{category}':\n")
    if isinstance(prompt, str):
        print(prompt)
    else:
        print(json.dumps(prompt, indent=2))


def cmd_build(args):
    """Build a prompt from components."""
    # Prompt structure template
    template = {
        "subject": {
            "main": args.subject or "",
            "material": args.material or "",
        },
        "context": {
            "setting": args.setting or "",
        },
        "style": {
            "aesthetic": args.style or "",
            "lighting": args.lighting or "",
        },
        "technical": {
            "lens": args.lens or "",
        }
    }

    # Remove empty values
    def clean_dict(d):
        return {k: (clean_dict(v) if isinstance(v, dict) else v)
                for k, v in d.items() if v and (not isinstance(v, dict) or clean_dict(v))}

    cleaned = clean_dict(template)

    if args.json:
        print(json.dumps(cleaned, indent=2))
    else:
        # Convert to text prompt
        parts = []
        for section in ["subject", "context", "style", "technical"]:
            if section in cleaned:
                section_parts = [v for v in cleaned[section].values() if v]
                if section_parts:
                    parts.append(", ".join(section_parts))
        print(", ".join(parts))


def cmd_list(args):
    """List all prompts in a category."""
    prompts = load_prompts()
    category = args.category

    if category not in prompts:
        print(f"Category not found: {category}")
        print(f"Available: {', '.join(sorted(prompts.keys()))}")
        return

    items = prompts[category]
    prompt_list = items if isinstance(items, list) else items.get("prompts", [])

    print(f"Prompts in '{category}' ({len(prompt_list)} total):\n")

    limit = args.limit or 20
    for i, prompt in enumerate(prompt_list[:limit], 1):
        if isinstance(prompt, str):
            display = prompt[:80] + ("..." if len(prompt) > 80 else "")
        else:
            display = json.dumps(prompt)[:80] + "..."
        print(f"  {i:3}. {display}")

    if len(prompt_list) > limit:
        print(f"\n... and {len(prompt_list) - limit} more. Use --limit to show more.")


def main():
    parser = argparse.ArgumentParser(
        description="Prompt library tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List categories
  prompts.py categories

  # Search for prompts
  prompts.py search "product photography"

  # Get random example from category
  prompts.py example product

  # Build a prompt
  prompts.py build --subject "coffee cup" --style "minimalist" --lighting "soft studio"

  # Build as JSON
  prompts.py build --subject "headphones" --material "matte black" --style "product" --json
"""
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # categories command
    subparsers.add_parser("categories", help="List all prompt categories")

    # search command
    search_parser = subparsers.add_parser("search", help="Search prompts by keyword")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", "-l", type=int, help="Max results (default: 10)")

    # example command
    example_parser = subparsers.add_parser("example", help="Get example from category")
    example_parser.add_argument("category", help="Category name")
    example_parser.add_argument("--index", "-i", type=int, help="Specific index (default: random)")

    # list command
    list_parser = subparsers.add_parser("list", help="List all prompts in a category")
    list_parser.add_argument("category", help="Category name")
    list_parser.add_argument("--limit", "-l", type=int, help="Max results (default: 20)")

    # build command
    build_parser = subparsers.add_parser("build", help="Build a prompt from components")
    build_parser.add_argument("--subject", "-s", help="Main subject")
    build_parser.add_argument("--material", "-m", help="Material/texture")
    build_parser.add_argument("--setting", help="Environment/setting")
    build_parser.add_argument("--style", help="Artistic style")
    build_parser.add_argument("--lighting", "-l", help="Lighting description")
    build_parser.add_argument("--lens", help="Camera lens (e.g., 85mm f/2.8)")
    build_parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    commands = {
        "categories": cmd_categories,
        "search": cmd_search,
        "example": cmd_example,
        "list": cmd_list,
        "build": cmd_build,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
