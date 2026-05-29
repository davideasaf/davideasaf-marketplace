#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["assemblyai"]
# ///
"""
Transcribe audio/video files with speaker diarization using AssemblyAI.

Usage:
    uv run transcribe.py <file_path> [options]

Options:
    --speakers N        Expected number of speakers (improves accuracy)
    --language LANG     Language code (default: en)
    --chapters          Add auto-chapter detection (billed as Speech Understanding)
    --entities          Add entity detection (billed as Speech Understanding)
    --output PATH       Output file path (default: <input>.transcript.md)
    --model MODEL       universal-3-pro (default) or universal-2

Always writes a raw JSON sidecar (<output>.json) alongside the markdown.

Requires: ASSEMBLYAI_API_KEY environment variable
"""

import argparse
import json
import os
import sys
import time
from datetime import timedelta
from pathlib import Path


def format_timestamp(ms: int) -> str:
    """Convert milliseconds to HH:MM:SS format."""
    td = timedelta(milliseconds=ms)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_duration(ms: int) -> str:
    """Convert milliseconds to human-readable duration."""
    td = timedelta(milliseconds=ms)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def _serialize_transcript(transcript):
    """Pull AssemblyAI Transcript fields into a plain dict for the JSON sidecar."""
    for attr in ("json_response", "_json_response"):
        raw = getattr(transcript, attr, None)
        if isinstance(raw, dict):
            return raw

    def safe(obj):
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, list):
            return [safe(x) for x in obj]
        if isinstance(obj, dict):
            return {k: safe(v) for k, v in obj.items()}
        if hasattr(obj, "__dict__"):
            return {k: safe(v) for k, v in vars(obj).items() if not k.startswith("_")}
        return str(obj)

    return safe(transcript)


def transcribe(file_path: str, speakers: int | None, language: str, chapters: bool, entities: bool, output: str | None, model: str = "universal-3-pro"):
    import assemblyai as aai

    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        print("Error: ASSEMBLYAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    aai.settings.api_key = api_key

    input_path = Path(file_path)
    if not input_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(output) if output else input_path.with_suffix(".transcript.md")
    json_path = output_path.with_suffix(".json")

    config_kwargs = {
        "speaker_labels": True,
        "language_code": language,
        "speech_models": [model],
    }

    if speakers:
        config_kwargs["speakers_expected"] = speakers

    if chapters:
        config_kwargs["auto_chapters"] = True

    if entities:
        config_kwargs["entity_detection"] = True

    config = aai.TranscriptionConfig(**config_kwargs)

    # Upload and transcribe
    file_size_mb = input_path.stat().st_size / (1024 * 1024)
    print(f"Uploading {input_path.name} ({file_size_mb:.1f} MB)...", file=sys.stderr)

    transcriber = aai.Transcriber()
    start_time = time.time()
    transcript = transcriber.transcribe(str(input_path), config)
    elapsed = time.time() - start_time

    if transcript.status == aai.TranscriptStatus.error:
        print(f"Error: Transcription failed: {transcript.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Transcription complete in {format_duration(int(elapsed * 1000))}.", file=sys.stderr)

    # Count unique speakers
    speaker_set = set()
    if transcript.utterances:
        for u in transcript.utterances:
            speaker_set.add(u.speaker)

    # Build output
    lines = []
    lines.append(f"# Transcript: {input_path.name}")
    lines.append("")
    lines.append(f"- **Transcribed**: {time.strftime('%Y-%m-%d %H:%M')}")
    if transcript.audio_duration:
        lines.append(f"- **Duration**: {format_duration(transcript.audio_duration * 1000)}")
    lines.append(f"- **Speakers**: {len(speaker_set)}")
    lines.append(f"- **Language**: {language}")
    if speakers:
        lines.append(f"- **Expected speakers**: {speakers}")
    lines.append(f"- **Word count**: {len(transcript.words) if transcript.words else 'N/A'}")
    lines.append("")

    if chapters and transcript.chapters:
        lines.append("---")
        lines.append("")
        lines.append("## Chapters")
        lines.append("")
        for ch in transcript.chapters:
            ts = format_timestamp(ch.start)
            lines.append(f"### [{ts}] {ch.headline}")
            lines.append("")
            lines.append(ch.summary)
            lines.append("")

    if entities and transcript.entities:
        lines.append("---")
        lines.append("")
        lines.append("## Entities")
        lines.append("")
        grouped: dict[str, list] = {}
        for ent in transcript.entities:
            ent_type = getattr(ent.entity_type, "value", str(ent.entity_type))
            grouped.setdefault(ent_type, []).append(ent)
        for ent_type in sorted(grouped):
            lines.append(f"### {ent_type}")
            lines.append("")
            for ent in grouped[ent_type]:
                ts = format_timestamp(ent.start)
                lines.append(f"- **[{ts}]** {ent.text}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Transcript")
    lines.append("")

    if transcript.utterances:
        for u in transcript.utterances:
            ts = format_timestamp(u.start)
            lines.append(f"**[{ts}] Speaker {u.speaker}:**")
            lines.append(u.text)
            lines.append("")
    else:
        lines.append(transcript.text or "(No transcript text available)")
        lines.append("")

    content = "\n".join(lines)
    output_path.write_text(content, encoding="utf-8")
    print(f"Saved to: {output_path}", file=sys.stderr)

    raw = _serialize_transcript(transcript)
    json_path.write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")
    print(f"Raw JSON: {json_path}", file=sys.stderr)

    # Print the path to stdout for the skill to capture
    print(str(output_path))


def main():
    parser = argparse.ArgumentParser(description="Transcribe audio with speaker diarization")
    parser.add_argument("file", help="Path to audio/video file")
    parser.add_argument("--speakers", type=int, help="Expected number of speakers")
    parser.add_argument("--language", default="en", help="Language code (default: en)")
    parser.add_argument("--chapters", action="store_true", help="Add auto-chapters (billed as Speech Understanding)")
    parser.add_argument("--entities", action="store_true", help="Add entity detection (billed as Speech Understanding)")
    parser.add_argument("--output", help="Output file path (default: <input>.transcript.md)")
    parser.add_argument("--model", default="universal-3-pro", choices=["universal-2", "universal-3-pro"],
                        help="Speech model (default: universal-3-pro, $0.21/hr; universal-2 $0.15/hr)")

    args = parser.parse_args()
    transcribe(args.file, args.speakers, args.language, args.chapters, args.entities, args.output, args.model)


if __name__ == "__main__":
    main()
