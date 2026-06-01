#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Video intake orchestrator: split a video into audio + candidate frames, then transcribe.

This is the entry point for VIDEO recordings (.mp4/.mov/.mkv/.webm) — e.g. an OBS
screen-recording of a Teams 1:1, or any recording where the screen-share matters.
It does the mechanical work an agent needs to do a full vault intake:

  1. Split the audio out of the video (mono mp3, speech-grade).
  2. Transcribe that audio via the chosen engine script (reuses the tested
     transcribe_deepgram.py / transcribe.py[AssemblyAI] / transcribe_groq.py / transcribe_xai.py).
  3. Extract CANDIDATE frames from the video at scene changes (screen swaps,
     new slides) and write a manifest correlating each frame to a timestamp.

What it deliberately does NOT do: decide which frames are "relevant". That is the
agent's job a turn later, in context — view the candidates, keep the vault-worthy
ones (slides, diagrams, forms), extract info from the rest, discard noise. The
agent also has the full video + audio left in place to grab a frame at any exact
timestamp the transcript points to.

Usage:
    uv run transcribe_video.py <video> [options]

Options:
    --engine {deepgram,assemblyai,groq,xai}  Transcription engine (default: deepgram).
                                             1:1s diarize cleaner with assemblyai (see ASR comparison).
    --output PATH         Transcript output path (default: <video>.transcript.md).
    --frames-dir PATH     Where to write candidate frames (default: <video-stem>-frames/ beside the video).
    --scene-threshold F   Scene-change sensitivity 0..1, lower = more frames (default: 0.4).
    --max-frames N        Cap on candidate frames kept (default: 60). Excess = highest scene-score kept.
    --min-gap S           Minimum seconds between kept frames, dedupes near-identical (default: 8).
    --interval S          Fallback: if scene detection finds < 3 frames, sample 1 frame / S seconds (default: 120).
    --no-frames           Skip frame extraction (audio + transcript only).
    --no-transcribe       Split audio + frames only, skip transcription.
    --no-keep-audio       Delete the extracted audio file after transcription.
    --language LANG       Forwarded to the engine (default: en).
    --speakers N          Forwarded to assemblyai engine (expected speaker count).
    --engine-args "..."   Raw extra args appended to the engine command (advanced).

Requires: ffmpeg + ffprobe on PATH, uv on PATH, and the chosen engine's API key
(DEEPGRAM_API_KEY / ASSEMBLYAI_API_KEY / GROQ_API_KEY / XAI_API_KEY).

Exits non-zero on any error. Per skill policy, does NOT auto-fall-back between engines.
"""

from __future__ import annotations

import argparse
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}

ENGINE_SCRIPTS = {
    "deepgram": "transcribe_deepgram.py",
    "assemblyai": "transcribe.py",
    "groq": "transcribe_groq.py",
    "xai": "transcribe_xai.py",
}


def die(msg: str, code: int = 2) -> "NoReturn":  # type: ignore[name-defined]
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def has_video_stream(video: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True,
    )
    return "video" in out.stdout


def extract_audio(video: Path, audio_out: Path) -> None:
    print(f"Splitting audio → {audio_out.name} (mono mp3)...", file=sys.stderr)
    r = subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(video),
         "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k", str(audio_out)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        die(f"audio extraction failed: {r.stderr[:500]}", 3)


def detect_scene_timestamps(video: Path, threshold: float) -> list[float]:
    """Return timestamps (seconds) of frames whose scene-change score exceeds threshold.

    Uses the `select='gt(scene,TH)',showinfo` idiom and parses `pts_time` from
    showinfo's log lines. (NB: `metadata=print` does NOT export the scene score —
    only `showinfo`/`scdet` surface it — so showinfo is the reliable parse target.)
    Detection runs on a downscaled copy for speed; timestamps map back to the source.
    """
    print(f"Detecting scene changes (threshold {threshold})...", file=sys.stderr)
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "info", "-i", str(video),
         "-vf", f"scale=640:-2,select='gt(scene,{threshold})',showinfo",
         "-an", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    times: list[float] = []
    for line in proc.stderr.splitlines():
        if "showinfo" not in line:
            continue
        m = re.search(r"pts_time:([0-9.]+)", line)
        if m:
            times.append(float(m.group(1)))
    return sorted(times)


def thin_by_gap(times: list[float], min_gap: float) -> list[float]:
    kept: list[float] = []
    last = -1e9
    for t in sorted(times):
        if t - last >= min_gap:
            kept.append(t)
            last = t
    return kept


def cap_evenly(times: list[float], max_frames: int) -> list[float]:
    """If over the cap, keep an evenly-spaced subset across the timeline."""
    if len(times) <= max_frames:
        return times
    step = len(times) / max_frames
    return [times[int(i * step)] for i in range(max_frames)]


def interval_timestamps(video: Path, interval: float) -> list[float]:
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(video)],
        capture_output=True, text=True,
    ).stdout.strip() or 0.0)
    out: list[float] = []
    t = interval
    while t < dur:
        out.append(t)
        t += interval
    return out


def grab_frame(video: Path, t: float, dest: Path) -> bool:
    r = subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{t:.3f}",
         "-i", str(video), "-frames:v", "1", "-q:v", "3", str(dest)],
        capture_output=True, text=True,
    )
    return r.returncode == 0 and dest.exists()


def extract_frames(video: Path, frames_dir: Path, threshold: float,
                   max_frames: int, min_gap: float, interval: float) -> list[tuple[float, Path]]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    times = detect_scene_timestamps(video, threshold)
    times = thin_by_gap(times, min_gap)
    if len(times) < 3:
        print(f"  Only {len(times)} scene change(s) found — adding interval samples "
              f"every {int(interval)}s for coverage.", file=sys.stderr)
        merged = {round(t): t for t in times}
        for t in interval_timestamps(video, interval):
            merged.setdefault(round(t), t)
        times = sorted(merged.values())
    times = cap_evenly(times, max_frames)

    saved: list[tuple[float, Path]] = []
    for t in times:
        dest = frames_dir / f"frame-{int(round(t)):05d}s.png"
        if grab_frame(video, t, dest):
            saved.append((t, dest))
    print(f"Saved {len(saved)} candidate frame(s) → {frames_dir}", file=sys.stderr)
    return saved


def write_manifest(frames_dir: Path, video: Path, transcript: Path | None,
                   frames: list[tuple[float, Path]], threshold: float) -> Path:
    manifest = frames_dir / "manifest.md"
    rows = [f"| `{p.name}` | {fmt_ts(t)} | {t:.1f} |" for t, p in frames]
    transcript_line = f"[[{transcript.stem}]]" if transcript else "(none — run with transcription)"
    body = [
        f"# Candidate frames — {video.name}",
        "",
        f"Scene-change frames (threshold {threshold}). **These are candidates, not curated.**",
        "Correlate the timestamps below with the transcript's `[MM:SS]` tags to find what was",
        "on screen when something was said.",
        "",
        f"- **Video:** `{video}`",
        f"- **Transcript:** {transcript_line}",
        f"- **Frame count:** {len(frames)}",
        "",
        "| Frame | Timestamp | Seconds |",
        "|---|---|---|",
        *rows,
        "",
        "## Agent intake steps",
        "1. Read the transcript; note moments where a speaker references on-screen content "
        "(\"let me show you\", \"see here\", \"this dashboard/diagram/form\").",
        "2. View the nearest candidate frame(s) to those timestamps. To grab an EXACT moment "
        "not in this set, run: "
        "`ffmpeg -ss <seconds> -i \"<video>\" -frames:v 1 -q:v 2 out.png`.",
        "3. **Keep only vault-worthy frames** (slides, diagrams, org charts, forms) — crop out "
        "webcam tiles / app chrome, rename descriptively, save into the note's `- photos/` folder, "
        "embed with `![[name.png]]`.",
        "4. For transient frames (cursors, half-loaded pages), extract the info into prose and "
        "discard the image.",
        "5. Delete this `-frames/` working dir once the keepers are in the vault.",
    ]
    manifest.write_text("\n".join(body))
    return manifest


def run_engine(engine: str, audio: Path, output: Path, language: str,
               speakers: int | None, engine_args: str | None) -> None:
    script = Path(__file__).resolve().parent / ENGINE_SCRIPTS[engine]
    if not script.exists():
        die(f"engine script not found: {script}", 2)
    uv = shutil.which("uv") or "uv"
    cmd = [uv, "run", str(script), str(audio), "--output", str(output), "--language", language]
    if engine == "assemblyai" and speakers:
        cmd += ["--speakers", str(speakers)]
    elif speakers and engine != "assemblyai":
        print(f"Note: --speakers is only used by the assemblyai engine; ignoring for {engine}.",
              file=sys.stderr)
    if engine_args:
        cmd += shlex.split(engine_args)
    print(f"Transcribing audio via {engine}: {' '.join(shlex.quote(c) for c in cmd)}", file=sys.stderr)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        die(f"{engine} transcription failed (exit {r.returncode}). "
            f"Per policy, NOT auto-falling-back to another engine — surface this and ask.", r.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description="Split a video into audio + frames, then transcribe.")
    ap.add_argument("video", type=Path)
    ap.add_argument("--engine", choices=list(ENGINE_SCRIPTS), default="deepgram")
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--frames-dir", type=Path, default=None)
    ap.add_argument("--scene-threshold", type=float, default=0.4)
    ap.add_argument("--max-frames", type=int, default=60)
    ap.add_argument("--min-gap", type=float, default=8.0)
    ap.add_argument("--interval", type=float, default=120.0)
    ap.add_argument("--no-frames", action="store_true")
    ap.add_argument("--no-transcribe", action="store_true")
    ap.add_argument("--no-keep-audio", action="store_true")
    ap.add_argument("--language", default="en")
    ap.add_argument("--speakers", type=int, default=None)
    ap.add_argument("--engine-args", default=None)
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            die(f"{tool} not found on PATH (needed to split video).", 2)

    video: Path = args.video
    if not video.exists():
        die(f"file not found: {video}")
    if video.suffix.lower() not in VIDEO_SUFFIXES and not has_video_stream(video):
        die(f"{video.name} has no video stream — use an engine script directly for audio-only files.")

    output: Path = args.output or video.with_suffix(".transcript.md")
    audio_out = video.with_suffix(".audio.mp3")
    frames_dir: Path = args.frames_dir or video.with_name(f"{video.stem}-frames")

    # 1. Split audio.
    extract_audio(video, audio_out)

    # 2. Transcribe (unless skipped).
    transcript: Path | None = None
    if not args.no_transcribe:
        run_engine(args.engine, audio_out, output, args.language, args.speakers, args.engine_args)
        transcript = output

    # 3. Candidate frames (unless skipped).
    frames: list[tuple[float, Path]] = []
    manifest: Path | None = None
    if not args.no_frames:
        frames = extract_frames(video, frames_dir, args.scene_threshold,
                                args.max_frames, args.min_gap, args.interval)
        manifest = write_manifest(frames_dir, video, transcript, frames, args.scene_threshold)

    if args.no_keep_audio and audio_out.exists():
        audio_out.unlink()

    # Summary for the calling agent.
    print("\n=== Video intake complete ===", file=sys.stderr)
    print(f"Video:      {video}", file=sys.stderr)
    if not args.no_keep_audio:
        print(f"Audio:      {audio_out}", file=sys.stderr)
    if transcript:
        print(f"Transcript: {transcript}", file=sys.stderr)
    if manifest:
        print(f"Frames:     {len(frames)} in {frames_dir} (see manifest.md)", file=sys.stderr)
    # stdout = the transcript path (or video) so callers can capture it.
    print(str(transcript or video))
    return 0


if __name__ == "__main__":
    sys.exit(main())
