#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.31"]
# ///
"""
Transcribe audio/video files with speaker diarization using xAI Speech-to-Text.

Cheap and fast alternative to Deepgram (~$0.10/hr REST vs Deepgram's ~$0.258/hr).
Supports keyterm biasing (same shape as Deepgram), word-level diarization, and
ITN-formatted output. Single model — there is no `--model` flag; xAI exposes one
STT model behind /v1/stt.

Usage:
    uv run transcribe_xai.py <file_path> [options]

Options:
    --output PATH         Output file path (default: <input>.transcript.md)
    --keyterms PATH       Keyterms file (one term per line, '#' comments)
    --no-keyterms         Run without keyterm biasing (default ON if file exists)
    --language LANG       Language code (default: en)
    --no-diarize          Disable diarization (default ON for multi-speaker)
    --no-format           Disable ITN formatting (default ON)

Always writes a raw JSON sidecar (<output>.json) alongside the markdown.

Requires: XAI_API_KEY environment variable.

xAI returns word-level results with a `speaker` field per word (when diarize=true).
This script groups consecutive same-speaker words into utterance lines so the
output matches the Deepgram script's `[mm:ss] Speaker X:` shape.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

XAI_URL = "https://api.x.ai/v1/stt"

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

# Keep xAI well under the documented 100-term cap; 60 already exercises the
# bias surface without saturating it.
MAX_KEYTERMS = 100


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
    return terms[:MAX_KEYTERMS]


def discover_keyterms_file(explicit: Path | None) -> Path | None:
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


def group_words_to_utterances(words: list[dict]) -> list[dict]:
    """Collapse consecutive same-speaker words into utterance dicts.

    A new utterance fires when speaker changes or when a silence gap > 1.5s
    appears between adjacent words from the same speaker (so long monologues
    still break into readable paragraphs).
    """
    if not words:
        return []
    utterances: list[dict] = []
    GAP = 1.5
    cur: dict | None = None
    for w in words:
        spk = w.get("speaker")
        text = (w.get("text") or w.get("word") or "").strip()
        if not text:
            continue
        start = float(w.get("start", 0.0))
        end = float(w.get("end", start))
        if cur is None or cur["speaker"] != spk or (start - cur["end"]) > GAP:
            if cur is not None:
                utterances.append(cur)
            cur = {"speaker": spk, "start": start, "end": end, "tokens": [text]}
        else:
            cur["tokens"].append(text)
            cur["end"] = end
    if cur is not None:
        utterances.append(cur)
    for u in utterances:
        u["transcript"] = " ".join(u.pop("tokens"))
    return utterances


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcribe with xAI Speech-to-Text + diarization")
    ap.add_argument("input", type=Path)
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--keyterms", type=Path, default=None,
                    help="Keyterms file (one term per line). If unset, auto-discover via "
                         "$TRANSCRIBE_KEYTERMS or .transcribe-keyterms.txt walking up from CWD.")
    ap.add_argument("--no-keyterms", action="store_true")
    ap.add_argument("--language", default="en")
    ap.add_argument("--no-diarize", action="store_true")
    ap.add_argument("--no-format", action="store_true")
    args = ap.parse_args()

    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        print("Error: XAI_API_KEY not set in environment", file=sys.stderr)
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
    if size_mb > 500:
        print(f"Error: file is {size_mb:.1f} MB; xAI STT max is 500 MB", file=sys.stderr)
        return 2

    keyterm_msg = f" + {len(keyterms)} keyterms" if keyterms else " (no keyterm biasing)"
    print(f"Uploading {audio.name} ({size_mb:.1f} MB) to xAI STT{keyterm_msg}...", file=sys.stderr)

    form_fields: list[tuple[str, tuple[None, str]]] = []
    if not args.no_format:
        form_fields.append(("format", (None, "true")))
    form_fields.append(("language", (None, args.language)))
    if not args.no_diarize:
        form_fields.append(("diarize", (None, "true")))
    for kt in keyterms:
        form_fields.append(("keyterm", (None, kt)))

    started = time.time()
    with audio.open("rb") as fh:
        # `file` must be the LAST field in the multipart body per xAI docs.
        files = form_fields + [("file", (audio.name, fh, mime))]
        resp = requests.post(
            XAI_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files=files,
            timeout=1800,
        )
    elapsed = time.time() - started

    if resp.status_code >= 300:
        print(f"Error: xAI STT returned {resp.status_code}: {resp.text[:1000]}", file=sys.stderr)
        return 3

    payload = resp.json()
    json_path.write_text(json.dumps(payload, indent=2))

    duration = float(payload.get("duration", 0.0))
    raw_text = (payload.get("text") or "").strip()
    words = payload.get("words") or []
    word_count = len(words) if words else len(raw_text.split())

    utterances = group_words_to_utterances(words) if words else []
    speakers: set[int] = set()
    lines: list[str] = []
    if utterances:
        for utt in utterances:
            spk = utt["speaker"]
            if spk is not None:
                speakers.add(int(spk))
            ts = fmt_ts(utt["start"])
            label = (
                f"Speaker {chr(ord('A') + int(spk))}" if spk is not None else "Unknown"
            )
            lines.append(f"\n\n**[{ts}] {label}:**\n{utt['transcript']}")
    else:
        # No word-level results — fall back to dumping the full text block.
        lines.append(f"\n\n{raw_text}")

    md = [
        f"# Transcript: {audio.name}",
        "",
        f"- **Transcribed**: {time.strftime('%Y-%m-%d %H:%M')}",
        f"- **Duration**: {fmt_ts(duration)}",
        f"- **Engine**: xAI Speech-to-Text (POST /v1/stt)",
        f"- **Speakers detected**: {len(speakers)}",
        f"- **Language**: {args.language}",
        f"- **Word count**: {word_count:,}",
        f"- **Wall-clock latency**: {elapsed:.1f}s",
        f"- **Keyterms loaded**: {len(keyterms)}"
        + (f" (from {keyterms_path})" if keyterms_path else ""),
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
