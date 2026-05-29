# Nanobanana Prompting Strategy Guide

Comprehensive guide for crafting effective image generation prompts.

## The Golden Rule

> **"Describe the scene, don't just list keywords."**
>
> A narrative, descriptive paragraph will almost always produce a better, more coherent image than a list of disconnected words.
>
> — Google AI Documentation

**Bad:** `dog, park, 4k, realistic`

**Good:** `A golden retriever playing fetch in a sun-dappled park, warm afternoon light filtering through oak trees, joyful expression, photorealistic, shallow depth of field`

---

## Prompt Structure: Subject + Context + Style

Every effective prompt has three components:

| Element | What to Include | Example |
|---------|-----------------|---------|
| **Subject** | Main focus, materials, colors, details | "a ceramic coffee cup with steam rising" |
| **Context** | Background, setting, environment, props | "on a rustic wooden table in a cozy café" |
| **Style** | Artistic direction, mood, lighting, quality | "warm morning light, photorealistic, 85mm lens" |

### Full Example

```
A ceramic coffee cup with steam rising,
on a rustic wooden table in a cozy café,
warm morning light streaming through the window,
photorealistic, shallow depth of field, 85mm lens
```

---

## When to Use Each Approach

### Natural Language (Default)

**Best for:** Creative exploration, artistic images, one-offs

```bash
generate.py "A whimsical treehouse in an ancient oak, fairy lights glowing at dusk,
watercolor painting style, soft dreamy atmosphere"
```

**Why it works:** The model understands intent, composition, and physics. It can make intelligent creative decisions.

### JSON Structured

**Best for:** Product photography, brand consistency, batch workflows

```bash
batch.py --json prompts.json -r 4k
```

**Why it works:** Prevents concept bleeding, ensures exact repeatability across many images.

### Edit (The 80% Rule)

**Best for:** When an image is 80%+ correct

```bash
edit.py image.png "make the lighting warmer and remove the background object"
```

**Why it works:** Faster than regenerating, preserves the good elements you want to keep.

---

## Photography Terminology

Use these terms to control specific aspects of your image:

### Camera Position

| Term | Effect |
|------|--------|
| close-up | Fills frame with subject |
| zoomed out | Shows more context |
| aerial / bird's eye | Looking down from above |
| from below / worm's eye | Looking up at subject |
| eye level | Natural human perspective |
| dutch angle | Tilted frame for tension |

### Lighting

| Term | Effect |
|------|--------|
| natural light | Realistic outdoor lighting |
| golden hour | Warm orange tones, long shadows |
| blue hour | Cool tones, pre-dawn or post-sunset |
| studio lighting | Controlled, even illumination |
| dramatic / side lighting | Strong shadows, high contrast |
| backlit / rim lighting | Subject silhouetted or glowing edges |
| soft / diffused | Gentle shadows, flattering |
| harsh / direct | Sharp shadows, contrasty |

### Lens & Camera Effects

| Term | Effect |
|------|--------|
| 35mm | Standard wide angle |
| 50mm | Natural perspective |
| 85mm | Portrait lens, flattering |
| macro | Extreme close-up detail |
| fisheye | Distorted wide angle |
| shallow depth of field | Blurred background (bokeh) |
| motion blur | Sense of movement |
| long exposure | Smooth water, light trails |
| HDR | Extended dynamic range |

### Film & Style

| Term | Effect |
|------|--------|
| photorealistic | Looks like a real photo |
| polaroid | Vintage instant camera look |
| black and white | Monochrome |
| film grain | Analog texture |
| cinematic | Movie-like composition |
| editorial | Magazine quality |

---

## Lens Selection by Subject

Match lens focal length to your subject type:

| Subject Type | Focal Length | Why |
|--------------|--------------|-----|
| Portraits | 85mm, 105mm | Flattering compression, nice bokeh |
| Products / Macro | 60-105mm | Detail without distortion |
| Landscapes | 16-35mm | Wide field of view |
| Architecture | 24mm | Minimal distortion for buildings |
| Action / Sports | 70-200mm | Reach with compression |
| Street | 35mm, 50mm | Natural perspective |

---

## Quality Modifiers

Add these terms to enhance output quality:

- `4K` or `high resolution` - Sharper detail
- `HDR` - Extended dynamic range
- `high-quality` - General quality boost
- `professional photography` - Commercial standard
- `sharp focus` - Crisp subject
- `detailed` - More fine details

---

## JSON Prompt Schema

For product photography and batch workflows, use structured JSON:

```json
{
  "subject": {
    "main": "wireless headphones",
    "material": "matte black finish",
    "color": "charcoal gray accents",
    "details": "visible texture on ear cups"
  },
  "context": {
    "setting": "clean white surface",
    "background": "gradient to light gray",
    "props": "subtle shadow below"
  },
  "style": {
    "aesthetic": "minimalist product photography",
    "lighting": "soft studio lighting from left",
    "mood": "premium and sophisticated"
  },
  "technical": {
    "lens": "85mm f/2.8",
    "resolution": "4K",
    "focus": "sharp throughout"
  }
}
```

### Supported Fields

**subject:** main, material, color, texture, details
**context:** setting, environment, background, props
**style:** aesthetic, mood, lighting, colors
**technical:** lens, camera, aperture, focus, resolution

---

## Common Mistakes to Avoid

### 1. Tag Soup
❌ `dog, happy, park, sunny, 4k, realistic, hdr, beautiful`
✅ `A happy golden retriever running through a sunny park, photorealistic, warm afternoon light`

### 2. Conflicting Instructions
❌ `A dark moody image with bright cheerful lighting`
✅ Pick one mood and be consistent

### 3. Too Vague
❌ `A nice picture of food`
✅ `Close-up of fresh sushi on black slate, overhead view, restaurant lighting, food photography style`

### 4. Over-Specifying
❌ `ISO 400, f/2.8, 1/250s, Canon 5D Mark IV, 85mm L lens`
✅ `85mm portrait lens, shallow depth of field` (let the model handle technical details)

### 5. Regenerating Instead of Editing
If an image is 80% correct, use `edit.py` with specific instructions rather than starting over.

---

## Prompt Templates by Use Case

### Product Photography
```
[Product name] with [material/finish],
on [surface/background],
[lighting description],
product photography, [resolution]
```

### Portrait
```
[Portrait type] of [subject description],
[setting/environment],
[lighting], [lens], [mood]
```

### Landscape
```
[Scene description] at [time of day],
[weather/atmosphere],
[compositional element], [style], [resolution]
```

### Icon/Logo
```
[Icon type] representing [concept],
[style: flat/3d/minimalist],
[colors], [size/format requirements]
```

---

## Technical Constraints

| Constraint | Value |
|------------|-------|
| Max prompt length | 480 tokens |
| Text in images | Keep to 25 characters max, 2-3 phrases |
| Resolutions | 1K (default), 2K, 4K (uppercase K) |
| Aspect ratios | 1:1, 4:3, 3:4, 16:9, 9:16, 21:9 |

---

## Sources

- [Google AI: Image Generation](https://ai.google.dev/gemini-api/docs/image-generation)
- [Google AI: Imagen Prompt Guide](https://ai.google.dev/gemini-api/docs/imagen-prompt-guide)
- [Leonardo.ai Nano Banana Guide](https://leonardo.ai/news/nano-banana-prompt-guide/)
- [DEV.to Nano-Banana Pro Strategies](https://dev.to/googleai/nano-banana-pro-prompting-guide-strategies-1h9n)
