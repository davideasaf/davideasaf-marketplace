---
name: vtt-processor
description: Cleans WebVTT (.vtt) transcript files into token-efficient, speaker-attributed text. Reduces file size by ~62% by removing timestamps, UUIDs, and metadata while preserving speaker labels. Use when processing .vtt files from Teams, Zoom, or other meeting/interview recordings.
---

# VTT Transcript Processor

Converts verbose WebVTT files into clean, token-efficient transcripts. Removes timestamps, UUIDs, and metadata while preserving speaker attribution and merging consecutive segments from the same speaker.

## When to Use

- Processing `.vtt` files from Microsoft Teams, Zoom, or other meeting recordings
- Preparing transcripts for LLM analysis (reduces token usage by ~62%)
- Converting raw VTT to readable, speaker-labeled text

## Prerequisites

- Python 3.10+ (no external dependencies)

## Usage

### Basic: Print to stdout

```bash
python3 scripts/clean_vtt.py meeting.vtt
```

### Save to file

```bash
python3 scripts/clean_vtt.py meeting.vtt -o meeting-clean.txt
```

### In-place (creates .txt alongside .vtt)

```bash
python3 scripts/clean_vtt.py meeting.vtt --in-place
```

### Batch process multiple files

```bash
python3 scripts/clean_vtt.py transcripts/*.vtt --in-place --stats
```

### Show token reduction stats

```bash
python3 scripts/clean_vtt.py meeting.vtt -o meeting-clean.txt --stats
# Output: meeting.vtt: 149,815 -> 57,291 bytes (61.8% reduction)
```

## How It Works

1. Parses VTT content, extracting speaker tags (`<v Speaker Name>text</v>`)
2. Strips timestamps, UUID segment identifiers, and WEBVTT headers
3. Merges consecutive segments from the same speaker into single paragraphs
4. Outputs clean `Speaker Name: Their text` format

## Example

**Before (VTT - ~150KB):**
```
WEBVTT

43e1361d-9fd2-4a60-b986-3bc18bb263f1/7-0
00:00:03.451 --> 00:00:07.449
<v John Smith (Engineering)>I heard from you that you will be doing
white labeling and all.</v>

43e1361d-9fd2-4a60-b986-3bc18bb263f1/7-1
00:00:07.449 --> 00:00:12.322
<v John Smith (Engineering)>So present I was working in a company
called Acme Solutions.</v>
```

**After (Clean - ~57KB, 62% reduction):**
```
John Smith (Engineering): I heard from you that you will be doing white labeling and all. So present I was working in a company called Acme Solutions.
```

## CLI Reference

```
usage: clean_vtt.py [-h] [-o OUTPUT] [--in-place] [--unknown-speaker LABEL] [--stats] input_files [input_files ...]

positional arguments:
  input_files           VTT file(s) to process

options:
  -o, --output          Output file path (single input only)
  --in-place            Create .txt file alongside each .vtt
  --unknown-speaker     Label for cues without speaker (default: Unknown)
  --stats               Show token reduction statistics
```
