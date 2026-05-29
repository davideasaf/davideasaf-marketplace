#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.31"]
# ///
"""
Transcribe audio/video files with speaker diarization using Deepgram Nova-3.

Default engine for multi-speaker recordings. Supports keyterm biasing — load a
keyterms file (one term per line) to boost recognition of recurring participants
and domain jargon.

Usage:
    uv run transcribe_deepgram.py <file_path> [options]

Options:
    --output PATH         Output file path (default: <input>.transcript.md)
    --keyterms PATH       Keyterms file (one term per line, '#' comments)
    --no-keyterms         Run without keyterm biasing (default ON if file exists)
    --language LANG       Language code (default: en)
    --model MODEL         Deepgram model (default: nova-3)

Always writes a raw JSON sidecar (<output>.json) alongside the markdown.

Requires: DEEPGRAM_API_KEY environment variable.

Exits non-zero on any error. Caller (the transcribe skill) should NOT auto-fall-back
to AssemblyAI — per user policy, that requires explicit confirmation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

DG_URL = "https://api.deepgram.com/v1/listen"

MIME = {
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
    ".aac": "audio/aac",
}


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def load_keyterms(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    terms: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(line)
    return terms


def discover_keyterms_file(explicit: Path | None) -> Path | None:
    """Find the keyterms file to use.

    Priority:
      1. Explicit --keyterms PATH (returned even if missing — let caller error)
      2. $TRANSCRIBE_KEYTERMS environment variable
      3. .transcribe-keyterms.txt in CWD or any parent (walk up to /)
      4. None (no biasing)
    """
    if explicit is not None:
        return explicit
    env = os.environ.get("TRANSCRIBE_KEYTERMS")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    cur = Path.cwd().resolve()
    for d in [cur, *cur.parents]:
        candidate = d / ".transcribe-keyterms.txt"
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcribe with Deepgram Nova-3 + diarization")
    ap.add_argument("input", type=Path)
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--keyterms", type=Path, default=None,
                    help="Keyterms file (one term per line). If unset, auto-discover via "
                         "$TRANSCRIBE_KEYTERMS or .transcribe-keyterms.txt walking up from CWD.")
    ap.add_argument("--no-keyterms", action="store_true")
    ap.add_argument("--language", default="en")
    ap.add_argument("--model", default="nova-3")
    args = ap.parse_args()

    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        print("Error: DEEPGRAM_API_KEY not set in environment", file=sys.stderr)
        return 2

    audio: Path = args.input
    if not audio.exists():
        print(f"Error: file not found: {audio}", file=sys.stderr)
        return 2

    output: Path = args.output or audio.with_suffix(".transcript.md")
    json_path = output.with_suffix(output.suffix + ".json")

    keyterms_path = None if args.no_keyterms else discover_keyterms_file(args.keyterms)
    keyterms = load_keyterms(keyterms_path)

    mime = MIME.get(audio.suffix.lower(), "application/octet-stream")
    size_mb = audio.stat().st_size / (1024 * 1024)
    keyterm_msg = f" + {len(keyterms)} keyterms" if keyterms else " (no keyterm biasing)"
    print(f"Uploading {audio.name} ({size_mb:.1f} MB) to Deepgram {args.model}{keyterm_msg}...", file=sys.stderr)

    params: list[tuple[str, str]] = [
        ("model", args.model),
        ("language", args.language),
        ("diarize", "true"),
        ("smart_format", "true"),
        ("punctuate", "true"),
        ("utterances", "true"),
        ("paragraphs", "true"),
    ]
    for kt in keyterms:
        params.append(("keyterm", kt))

    started = time.time()
    with audio.open("rb") as fh:
        resp = requests.post(
            DG_URL,
            params=params,
            headers={"Authorization": f"Token {api_key}", "Content-Type": mime},
            data=fh,
            timeout=900,
        )
    elapsed = time.time() - started

    if resp.status_code >= 300:
        print(f"Error: Deepgram returned {resp.status_code}: {resp.text[:1000]}", file=sys.stderr)
        return 3

    payload = resp.json()
    json_path.write_text(json.dumps(payload, indent=2))

    metadata = payload.get("metadata", {}) or {}
    duration = float(metadata.get("duration", 0.0))
    model_info = metadata.get("model_info", {}) or {}
    model_label = args.model
    for info in model_info.values():
        model_label = f"{info.get('arch', args.model)} ({info.get('name', '?')})"
        break

    results = payload.get("results", {}) or {}
    utterances = results.get("utterances") or []
    speakers: set[int] = set()
    word_count = 0
    lines: list[str] = []
    last_speaker: int | None = None

    for utt in utterances:
        spk = utt.get("speaker")
        text = (utt.get("transcript") or "").strip()
        if not text:
            continue
        if spk is not None:
            speakers.add(int(spk))
        word_count += len(text.split())
        ts = fmt_ts(float(utt.get("start", 0.0)))
        label = f"Speaker {chr(ord('A') + int(spk))}" if spk is not None else "Unknown"
        if spk == last_speaker:
            lines.append(f"\n{text}")
        else:
            lines.append(f"\n\n**[{ts}] {label}:**\n{text}")
        last_speaker = spk

    md = [
        f"# Transcript: {audio.name}",
        "",
        f"- **Transcribed**: {time.strftime('%Y-%m-%d %H:%M')}",
        f"- **Duration**: {fmt_ts(duration)}",
        f"- **Engine**: Deepgram {model_label}",
        f"- **Speakers detected**: {len(speakers)}",
        f"- **Language**: {args.language}",
        f"- **Word count**: {word_count:,}",
        f"- **Wall-clock latency**: {elapsed:.1f}s",
        f"- **Keyterms loaded**: {len(keyterms)}" + (f" (from {keyterms_path})" if keyterms_path else ""),
        "",
        "---",
        "",
        "## Transcript",
        "".join(lines).lstrip(),
    ]
    output.write_text("\n".join(md))
    print(f"Transcription complete in {elapsed:.1f}s.", file=sys.stderr)
    print(f"Saved to: {output}", file=sys.stderr)
    print(f"Raw JSON: {json_path}", file=sys.stderr)
    print(str(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
