---
name: yt-search
description: >-
  Search YouTube directly from Claude Code using `/yt-search`. Returns structured
  results with titles, channels, view counts, duration, and dates — filtered to the
  last 6 months by default with automatic insights highlighting notable content.
  Use this skill whenever the user wants to search YouTube, find videos, look up
  tutorials, discover content creators, or asks "are there any videos about X".
  Also triggers on phrases like "youtube search", "find me a video", "what videos
  exist about", or any mention of searching for video content.
---

# YouTube Search

Search YouTube from the terminal via `yt-dlp`. Returns structured results with metadata and highlights notable finds.

## Prerequisites

`yt-dlp` must be installed: `brew install yt-dlp`

## How to use

Run the bundled search script:

```bash
uv run python <skill-path>/scripts/search.py <query> [options]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-n`, `--count` | 20 | Number of results |
| `-t`, `--time` | 6months | Time filter: `week`, `month`, `3months`, `6months`, `year`, `all` |
| `--sort` | relevance | Sort by: `relevance`, `views`, `date` |
| `--json` | off | Output raw JSON (for programmatic use) |
| `--no-insights` | off | Skip the insights summary |

### Examples

```bash
# Basic search (20 results, last 6 months)
uv run python <skill-path>/scripts/search.py claude code skills

# Fewer results, last month only
uv run python <skill-path>/scripts/search.py react server components -n 10 -t month

# Sort by views, no time filter
uv run python <skill-path>/scripts/search.py kubernetes tutorial --sort views -t all

# Raw JSON for processing
uv run python <skill-path>/scripts/search.py "machine learning" --json -n 5
```

## Interpreting the user's request

When the user asks to search YouTube, extract:

1. **Search query** — the core topic (required)
2. **Result count** — if they say "top 5" or "a few", adjust `-n` accordingly
3. **Time range** — "recent" = `month`, "this week" = `week`, "latest" = `3months`. Default to `6months` if unspecified.
4. **Sort preference** — "most popular" or "most viewed" = `--sort views`, "newest" = `--sort date`

If the user's intent is ambiguous (e.g., "find me something about X"), default to a standard search and let the insights guide them.

## After presenting results

The script automatically appends an **Insights** section that highlights:
- **Most viewed** — the breakout hit in the result set
- **Most recent** — freshest content
- **Deep dive** — best long-form video (>20 min) by views
- **Quick watch** — best short video (<10 min) by views
- **Average views** — gives a sense of topic popularity

Present the full output to the user. If they ask for more detail on a specific video, you can re-run with `--json` and extract the description, or use the URL to fetch more info.

## Performance note

Full metadata extraction takes ~2-3 seconds per video. A 20-result search typically completes in 40-60 seconds. Let the user know it'll take a moment if they seem impatient — this is the tradeoff for getting accurate dates and view counts.
