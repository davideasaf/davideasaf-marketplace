---
name: nanobanana-image-gen
description: Generates images using Gemini API with OAuth. Use when user asks to generate images, create icons, edit photos, or make visual content. Triggers on "generate an image", "create a picture", "make a logo", "edit this photo".
---

# Nanobanana Image Generation

Generate and edit images using the Gemini 3 API with OAuth credentials.

## Prompting Strategy

> **Golden Rule:** "Describe the scene, don't just list keywords. A narrative, descriptive paragraph will almost always produce a better, more coherent image than a list of disconnected words." — Google AI

### Prompt Structure: Subject + Context + Style

| Element | What to include | Example |
|---------|-----------------|---------|
| **Subject** | Main focus, materials, colors | "a ceramic coffee cup with steam rising" |
| **Context** | Background, setting, environment | "on a rustic wooden table in a cozy café" |
| **Style** | Artistic direction, mood, lighting | "warm morning light, photorealistic, shallow depth of field" |

**Full example:**
```
A ceramic coffee cup with steam rising, on a rustic wooden table in a cozy café,
warm morning light streaming through the window, photorealistic, shallow depth of field, 85mm lens
```

### When to Use Each Approach

| Approach | Best For | Command |
|----------|----------|---------|
| **Natural language** | Creative exploration, artistic images | `generate.py "descriptive prompt"` |
| **JSON structured** | Product shots, brand consistency, batch | `batch.py --json prompts.json` |
| **Edit (not regenerate)** | Image is 80%+ correct | `edit.py image.png "specific change"` |

### The 80% Rule
If an image is mostly correct, use `edit.py` with specific changes instead of regenerating:
- "make the lighting warmer"
- "remove the background object"
- "change the color to blue"

### Quality & Resolution

Add quality modifiers: `"4K"`, `"HDR"`, `"high-quality"`, `"professional photography"`

Resolution flags: `-r 1k` (default), `-r 2k`, `-r 4k`

For detailed prompting guidance, see [references/prompting-strategy.md](references/prompting-strategy.md)

---

## Prerequisites

Authenticates one of two ways:

1. **API key (simplest):** set `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) and gcloud is not needed.
2. **gcloud OAuth:** uses a named gcloud configuration. Configure via env vars:
   - `NANOBANANA_GCLOUD_CONFIG` — gcloud configuration name (default: `default`)
   - `NANOBANANA_ACCOUNT` — *(optional)* account email to pin/verify

```bash
# Verify setup (run from the skill directory)
python scripts/auth.py

# If the gcloud config doesn't exist (uses $NANOBANANA_GCLOUD_CONFIG, default "default")
gcloud config configurations create "${NANOBANANA_GCLOUD_CONFIG:-default}"
gcloud auth login --configuration="${NANOBANANA_GCLOUD_CONFIG:-default}"
```

Dependencies are auto-installed on first run (uses `uv`).

---

## Quick Start

### Generate an image

```bash
python ~/.claude/skills/nanobanana-image-gen/scripts/generate.py "a sunset over mountains" -o sunset.png
python ~/.claude/skills/nanobanana-image-gen/scripts/generate.py "product shot of headphones" -o headphones.png -r 4k -a 16:9
```

### Edit an existing image

```bash
python ~/.claude/skills/nanobanana-image-gen/scripts/edit.py photo.jpg "add a rainbow" -o edited.png
```

### Batch generate

```bash
# Variations mode
python ~/.claude/skills/nanobanana-image-gen/scripts/batch.py --variations "landscape" "at sunset" "at night" "in winter"

# JSON mode (for product/brand consistency)
python ~/.claude/skills/nanobanana-image-gen/scripts/batch.py --json prompts.json -r 4k
```

### Search prompts library

```bash
python ~/.claude/skills/nanobanana-image-gen/scripts/prompts.py search "product photography"
python ~/.claude/skills/nanobanana-image-gen/scripts/prompts.py categories
```

---

## Scripts

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `generate.py` | Create images from text | `-r` resolution, `-a` aspect, `-t` transparent |
| `edit.py` | Modify existing images | `-r` resolution |
| `batch.py` | Multiple images | `--json`, `--variations`, `-r` resolution |
| `prompts.py` | Search prompt library | `search`, `categories`, `example` |
| `remove_bg.py` | Remove background | `--model`, `--alpha-matting` |

---

## Transparent Backgrounds

```bash
# Generate with transparent background (green-screen + rembg)
python ~/.claude/skills/nanobanana-image-gen/scripts/generate.py "a coffee cup" -o cup.png --transparent

# Remove background from existing image
python ~/.claude/skills/nanobanana-image-gen/scripts/remove_bg.py photo.png -o cutout.png
```

Options: `--model birefnet-general` (higher quality), `--model isnet-anime` (illustrations)

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_IMAGE_MODEL` | `gemini-3.1-flash-image-preview` | Model to use (Nano Banana 2) |
| `GEMINI_API_KEY` | — | API key auth (skips gcloud OAuth when set) |
| `GOOGLE_API_KEY` | — | Alternative API key (same behavior) |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "gcloud configuration not found" | `gcloud config configurations create "${NANOBANANA_GCLOUD_CONFIG:-default}" && gcloud auth login` |
| "Wrong account" | `gcloud auth login --configuration="${NANOBANANA_GCLOUD_CONFIG:-default}"` |
| First run slow | Normal - initial venv setup |

See [references/command-reference.md](references/command-reference.md) for full CLI docs.
See [references/prompting-strategy.md](references/prompting-strategy.md) for prompting guide.
