#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx"]
# ///
"""
Transcribe audio/video files using Groq's Whisper API.
Fast, simple transcription without speaker diarization.

Usage:
    uv run transcribe_groq.py <file_path> [options]

Options:
    --language LANG     Language code (default: auto-detect)
    --output PATH       Output file path (default: <input>.transcript.md)

Requires: GROQ_API_KEY environment variable
"""

import argparse
import os
import sys
import time
from pathlib import Path


def format_duration(seconds: float) -> str:
    """Convert seconds to human-readable duration."""
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS or MM:SS format."""
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def transcribe(file_path: str, language: str | None, output: str | None):
    import httpx

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    input_path = Path(file_path)
    if not input_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(output) if output else input_path.with_suffix(".transcript.md")

    # Groq Whisper API has a 25MB limit — check file size
    file_size_mb = input_path.stat().st_size / (1024 * 1024)
    if file_size_mb > 25:
        print(f"Error: File is {file_size_mb:.1f} MB — Groq Whisper limit is 25 MB.", file=sys.stderr)
        print("Use AssemblyAI instead (--engine assemblyai).", file=sys.stderr)
        sys.exit(1)

    print(f"Uploading {input_path.name} ({file_size_mb:.1f} MB) to Groq Whisper...", file=sys.stderr)

    # Build the multipart request
    data = {
        "model": "whisper-large-v3-turbo",
        "response_format": "verbose_json",
        "timestamp_granularities[]": "segment",
    }
    if language:
        data["language"] = language

    start_time = time.time()

    with open(input_path, "rb") as f:
        files = {"file": (input_path.name, f, "audio/ogg")}
        response = httpx.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            data=data,
            files=files,
            timeout=300,
        )

    elapsed = time.time() - start_time

    if response.status_code != 200:
        print(f"Error: Groq API returned {response.status_code}: {response.text}", file=sys.stderr)
        sys.exit(1)

    result = response.json()
    print(f"Transcription complete in {format_duration(elapsed)}.", file=sys.stderr)

    # Build output markdown
    text = result.get("text", "").strip()
    duration = result.get("duration", 0)
    detected_language = result.get("language", language or "unknown")
    segments = result.get("segments", [])
    word_count = len(text.split()) if text else 0

    lines = []
    lines.append(f"# Transcript: {input_path.name}")
    lines.append("")
    lines.append(f"- **Transcribed**: {time.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- **Duration**: {format_duration(duration)}")
    lines.append(f"- **Engine**: Groq Whisper V3 Turbo")
    lines.append(f"- **Language**: {detected_language}")
    lines.append(f"- **Word count**: {word_count}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Transcript")
    lines.append("")

    if segments:
        for seg in segments:
            ts = format_timestamp(seg.get("start", 0))
            lines.append(f"**[{ts}]** {seg.get('text', '').strip()}")
            lines.append("")
    else:
        lines.append(text)
        lines.append("")

    content = "\n".join(lines)
    output_path.write_text(content, encoding="utf-8")
    print(f"Saved to: {output_path}", file=sys.stderr)
    print(str(output_path))


def main():
    parser = argparse.ArgumentParser(description="Transcribe audio with Groq Whisper")
    parser.add_argument("file", help="Path to audio/video file")
    parser.add_argument("--language", default=None, help="Language code (default: auto-detect)")
    parser.add_argument("--output", help="Output file path (default: <input>.transcript.md)")

    args = parser.parse_args()
    transcribe(args.file, args.language, args.output)


if __name__ == "__main__":
    main()
