# Origin

Extracted 2026-05-13 from the `atd-b2c` plugin (atd-claude-plugins marketplace, v1.37.0):
`~/.claude/plugins/cache/atd-claude-plugins/atd-b2c/1.37.0/skills/vtt-processor/`

## To install on a new machine as a standalone user-level skill

```
mkdir -p ~/.claude/skills
cp -r vtt-processor ~/.claude/skills/
```

Then restart Claude Code — it will appear as `vtt-processor` (no plugin prefix).

## What it does

Cleans WebVTT (`.vtt`) transcript files into token-efficient, speaker-attributed
text. Reduces file size by ~62% by removing timestamps, UUIDs, and metadata
while preserving speaker labels. Useful for `.vtt` files from Teams, Zoom, or
other meeting recordings.

`scripts/clean_vtt.py` is the runner.
