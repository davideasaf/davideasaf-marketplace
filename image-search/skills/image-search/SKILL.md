---
name: Stock Image Search
description: Use when you need to find a stock image.
---

# Stock Image Search

## Instructions

inputs:

- image_description: the user will describe the image they want to search for.
- output_path: the path where the image will be downloaded to.
- image_size: Default: `regular`
  Available sizes from Unsplash:
  - raw - Original unprocessed (largest, slower)
  - full - Full quality JPEG (very large)
  - regular - 1080px width ✓ BEST CHOICE
  - small - 400px width (too small for most uses)
  - thumb - 200px width (thumbnail only)

## Search Strategy

When the user describes the image they want, use the curl command to search Unsplash API directly.

## Prerequisites

**IMPORTANT:** The environment variable `UNSPLASH_ACCESS_KEY` must be set with your Unsplash API access key.

If you encounter an authorization error, tell the user:

```
Please set the UNSPLASH_ACCESS_KEY environment variable with your Unsplash API access key:
export UNSPLASH_ACCESS_KEY="your_access_key_here"
```

## Searching for Images

Use curl to query the Unsplash API:

```bash
# Basic search
curl -H "Authorization: Client-ID $UNSPLASH_ACCESS_KEY" \
  "https://api.unsplash.com/search/photos?query=mountain+sunset&per_page=10&order_by=relevant"

# With additional filters
curl -H "Authorization: Client-ID $UNSPLASH_ACCESS_KEY" \
  "https://api.unsplash.com/search/photos?query=ocean&per_page=15&orientation=landscape&color=blue&order_by=relevant"
```

## Query Construction Guidelines

**Query Construction:**

- Use clear, descriptive keywords for the `query` parameter
- Combine multiple relevant terms (e.g., "mountain sunset" instead of just "mountain")
- Use specific rather than generic terms for better results
- URL-encode query parameters (spaces become `+` or `%20`)

**Available Parameters:**

- `query` (required) - The search terms describing the image
- `page` (optional) - Page number for pagination (default: 1)
- `per_page` (optional) - Results per page, 1-30 (default: 10)
- `order_by` (optional) - Sort by "relevant" (default) or "latest"
- `color` (optional) - Filter by color: black_and_white, black, white, yellow, orange, red, purple, magenta, green, teal, blue
- `orientation` (optional) - Filter by orientation: landscape, portrait, squarish

**Best Practices:**

- Start with `order_by=relevant` for best matching results
- Use 10-15 results per page for good selection without overwhelming
- Apply `orientation` filter if the use case requires specific dimensions
- Use `color` filter when color palette is important for the project
- URL-encode query parameters (spaces become `+` or `%20`)

## Presenting Results to the User

When showing search results to the user, always include:

- A numbered list of options with descriptions
- The Unsplash page URL for each image (from the `links.html` field in the API response)
- This allows users to preview images before downloading

Example format:

```
1. **White and brown cow** on green grass field
   https://unsplash.com/photos/[photo-slug]
2. **Seal on rocks** (described as "so cute")
   https://unsplash.com/photos/[photo-slug]
```

Once you find an image that matches the description, download that image to where the user requested it to be downloaded to.

## Downloading the image

```bash
curl -L "URL" -o "/path/to/file.jpg"
```
