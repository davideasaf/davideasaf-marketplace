# Nanobanana Command Reference

Complete reference for all nanobanana image generation scripts.

---

## generate.py - Image Generation

Create images from text prompts using the Gemini API.

### Syntax

```bash
python scripts/generate.py "prompt" [-o OUTPUT] [-r RESOLUTION] [-a ASPECT] [-t] [--model MODEL]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `prompt` | Yes | Text description of the image to generate |
| `-o, --output` | No | Output file path (default: auto-generated timestamp) |
| `-r, --resolution` | No | Resolution: `1k` (default), `2k`, `4k` |
| `-a, --aspect-ratio` | No | Aspect ratio: `1:1`, `4:3`, `3:4`, `16:9`, `9:16`, `21:9` |
| `-t, --transparent` | No | Generate with transparent background |
| `--model` | No | Model to use (default: gemini-3-pro-image-preview) |

### Examples

```bash
# Basic generation
python scripts/generate.py "a cozy cabin in the woods"

# With resolution and aspect ratio
python scripts/generate.py "product shot of headphones" -o headphones.png -r 4k -a 16:9

# Transparent background
python scripts/generate.py "a coffee cup" -o cup.png --transparent

# High-res portrait
python scripts/generate.py "professional headshot, studio lighting" -r 4k -a 3:4

# Landscape banner
python scripts/generate.py "mountain sunset panorama" -r 4k -a 21:9
```

---

## edit.py - Image Editing

Modify existing images using natural language instructions.

### Syntax

```bash
python scripts/edit.py INPUT "instruction" [-o OUTPUT] [-r RESOLUTION] [--model MODEL]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `INPUT` | Yes | Path to input image file |
| `instruction` | Yes | What to change about the image |
| `-o, --output` | No | Output file path (default: {input}_edited_{timestamp}.png) |
| `-r, --resolution` | No | Output resolution: `1k`, `2k`, `4k` |
| `--model` | No | Model to use |

### Examples

```bash
# Add elements
python scripts/edit.py photo.jpg "add a rainbow in the sky"

# Remove elements
python scripts/edit.py portrait.png "remove the background"

# Color adjustments with higher resolution
python scripts/edit.py image.png "make the colors warmer" -r 4k

# Style transfer
python scripts/edit.py landscape.jpg "make it look like a Van Gogh painting"

# Lighting changes
python scripts/edit.py photo.jpg "add dramatic side lighting"
```

---

## batch.py - Batch Generation

Generate multiple images from variations, a prompts file, or structured JSON.

### Syntax

```bash
# Variations mode
python scripts/batch.py --variations "base prompt" "var1" "var2" [-o DIR] [-r RES] [-a ASPECT]

# File mode (text or simple JSON)
python scripts/batch.py --file prompts.txt [-o DIR] [-r RES] [-a ASPECT]

# JSON mode (structured prompts)
python scripts/batch.py --json prompts.json [-o DIR] [-r RES] [-a ASPECT]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--variations` | One of three | Base prompt + variation strings |
| `--file, -f` | One of three | File containing prompts (text or JSON) |
| `--json, -j` | One of three | JSON file with structured prompts |
| `-o, --output` | No | Output directory (default: batch_{timestamp}) |
| `-r, --resolution` | No | Resolution: `1k`, `2k`, `4k` |
| `-a, --aspect-ratio` | No | Aspect ratio: `1:1`, `4:3`, `3:4`, `16:9`, `9:16`, `21:9` |
| `--model` | No | Model to use |

### Prompts File Formats

**Plain text** (one prompt per line):
```
a sunset over mountains
a cozy cabin in the woods
abstract geometric pattern
```

**Simple JSON array**:
```json
{
  "prompts": [
    "a sunset over mountains",
    "a cozy cabin in the woods"
  ]
}
```

**Structured JSON** (for product/brand consistency):
```json
{
  "prompts": [
    {
      "subject": {"main": "wireless headphones", "material": "matte black"},
      "context": {"setting": "white surface"},
      "style": {"aesthetic": "minimalist", "lighting": "soft studio"},
      "technical": {"lens": "85mm f/2.8"}
    },
    {
      "subject": {"main": "wireless headphones", "material": "matte black"},
      "context": {"setting": "dark surface"},
      "style": {"aesthetic": "dramatic", "lighting": "side lighting"},
      "technical": {"lens": "85mm f/2.8"}
    }
  ]
}
```

### Examples

```bash
# Lighting variations
python scripts/batch.py --variations "mountain landscape" "at sunrise" "at noon" "at sunset"

# Product shots with consistency (JSON)
python scripts/batch.py --json product-shots.json -r 4k -o ./product-images

# Style variations
python scripts/batch.py --variations "portrait of a cat" "watercolor" "oil painting" "sketch"

# From text file with resolution
python scripts/batch.py --file prompts.txt -r 2k -o ./output
```

---

## prompts.py - Prompt Library

Search, browse, and build prompts from curated examples.

### Syntax

```bash
python scripts/prompts.py <command> [options]
```

### Commands

| Command | Description |
|---------|-------------|
| `categories` | List all prompt categories |
| `search QUERY` | Search prompts by keyword |
| `example CATEGORY` | Get random example from category |
| `list CATEGORY` | List all prompts in a category |
| `build` | Build a prompt from components |

### Examples

```bash
# List categories
python scripts/prompts.py categories

# Search for prompts
python scripts/prompts.py search "product photography"
python scripts/prompts.py search "minimalist" --limit 20

# Get example from category
python scripts/prompts.py example product
python scripts/prompts.py example landscape --index 0

# List all prompts in category
python scripts/prompts.py list portrait

# Build a prompt
python scripts/prompts.py build --subject "coffee cup" --style "minimalist" --lighting "soft studio"

# Build as JSON
python scripts/prompts.py build --subject "headphones" --material "matte black" --style "product" --json
```

### Build Options

| Option | Description |
|--------|-------------|
| `--subject, -s` | Main subject |
| `--material, -m` | Material/texture |
| `--setting` | Environment/setting |
| `--style` | Artistic style |
| `--lighting, -l` | Lighting description |
| `--lens` | Camera lens (e.g., "85mm f/2.8") |
| `--json, -j` | Output as JSON structure |

---

## remove_bg.py - Background Removal

Remove backgrounds from existing images using rembg.

### Syntax

```bash
python scripts/remove_bg.py INPUT [-o OUTPUT] [--model MODEL] [--alpha-matting]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `INPUT` | Yes | Input image file |
| `-o, --output` | No | Output file path |
| `--model` | No | rembg model: `u2net` (default), `birefnet-general`, `isnet-anime` |
| `--alpha-matting` | No | Better edges for complex images |

### Examples

```bash
# Basic background removal
python scripts/remove_bg.py photo.png -o cutout.png

# Higher quality
python scripts/remove_bg.py photo.png --model birefnet-general

# For anime/illustrations
python scripts/remove_bg.py illustration.png --model isnet-anime
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_IMAGE_MODEL` | `gemini-3-pro-image-preview` | Default model |

---

## Authentication

Uses the gcloud configuration named by `$NANOBANANA_GCLOUD_CONFIG` (default `default`).
Alternatively set `GEMINI_API_KEY` / `GOOGLE_API_KEY` to skip gcloud entirely.

### Verify Setup

```bash
python scripts/auth.py
```

### If Configuration Doesn't Exist

```bash
gcloud config configurations create "${NANOBANANA_GCLOUD_CONFIG:-default}"
gcloud auth login --configuration="${NANOBANANA_GCLOUD_CONFIG:-default}"
```

---

## Resolution & Aspect Ratio Reference

### Resolutions

| Value | Size | Use Case |
|-------|------|----------|
| `1k` | 1024px | Default, web use |
| `2k` | 2048px | Print, detailed work |
| `4k` | 4096px | High-res prints, products |

### Aspect Ratios

| Value | Proportion | Use Case |
|-------|------------|----------|
| `1:1` | Square | Social media, icons |
| `4:3` | Standard | General purpose |
| `3:4` | Portrait | Mobile, portraits |
| `16:9` | Widescreen | Video thumbnails, banners |
| `9:16` | Vertical | Stories, mobile |
| `21:9` | Ultrawide | Panoramas, headers |

---

## See Also

- [Prompting Strategy Guide](prompting-strategy.md) - Comprehensive prompting techniques
- [Prompt Library](prompts/) - Curated prompt examples by category
