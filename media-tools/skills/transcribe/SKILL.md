---
name: transcribe
version: '1.1.0'
description: >-
  Transcribe audio/video files — voice notes, recordings, meetings, conversations.
  Uses Groq Whisper (fast, free) by default for single-speaker audio under 25 MB,
  xAI Speech-to-Text for single-speaker audio over 25 MB, and Deepgram Nova-3 with
  keyterm biasing for multi-speaker diarization. Use this skill whenever
  the user wants to transcribe a recording, diarize speakers, convert a meeting to
  text, or process any audio/video file (.m4a, .mp4, .wav, .mp3, .webm, .ogg, etc.)
  into a readable transcript. Also use when the user mentions "transcribe", "diarize",
  "meeting notes from recording", "who said what", or wants to analyze/summarize an
  audio file. For VIDEO recordings (screen-shares, OBS/Teams captures), it also splits
  the audio out and extracts candidate screenshot frames at scene changes so an agent
  lands with transcript + audio + video + timestamped frames to intake — and, for
  meeting-app video (Teams/Zoom/Meet), can resolve diarized speaker labels to real names
  from the on-screen participant gallery instead of asking.
---

# Transcribe Audio

Transcribes audio/video files with automatic engine selection based on the task.

## Operating assumption

The user will always do post-analysis with Claude on the resulting transcript.
That changes the math: the engine's job is the **audio-domain** work
(transcription + diarization). Anything language-domain (summary, entity
extraction, topic detection) is Claude's job a turn later, in context. So this
skill defaults to **diarization only** — no chapters / entities / summaries.

## Engine Selection — Deepgram is the multi-speaker default

Pick the right engine from context — don't ask unless genuinely ambiguous:

| Context | Engine | Why |
|---------|--------|-----|
| Voice note, single speaker, quick transcription | **Groq** | Fast, free, no diarization needed |
| Discord voice message | **Groq** | Always single speaker |
| Short clip, podcast excerpt, dictation | **Groq** | Simple transcription |
| **Meeting with 2+ speakers** | **Deepgram Nova-3** | Speaker diarization + keyterm biasing toward Ford vocabulary |
| **Interview, conversation, 1:1** | **Deepgram Nova-3** | Need to know who said what |
| User says "diarize" or "who said what" | **Deepgram Nova-3** | Explicit diarization request |
| Single-speaker file > 25 MB (long monologue, podcast, lecture) | **xAI STT** | Up to 500 MB at $0.10/hr; avoids ffmpeg transcoding for Groq's cap |
| Multi-speaker file > 25 MB (any length) | **Deepgram Nova-3** | Zero-decision, diarized regardless of length |
| User explicitly requests an engine | **That engine** | User override |

**Default for multi-speaker is Deepgram.** Default for single-speaker is Groq (or xAI if > 25 MB).
**AssemblyAI is NOT in the routing table** — see policy below.

**xAI multi-speaker caveat (verified 2026-05-19):** xAI diarization works on clips up to ~45 min (returned 1, 2, 7, 9, 10, 11 distinct speakers at 60s/90s/10/25/35/45 min respectively on the AI Tech Guild recording). On the same source audio at 57 min, xAI silently drops the `speaker` field from the response entirely — no error, no warning. For multi-speaker work over ~45 min, route to Deepgram OR chunk the audio at ~40-min boundaries with ffmpeg before sending to xAI. Short 1:1s and standups can route to xAI directly if cost matters.

## 🎥 Video intake — split audio + transcribe + candidate frames

When the input is a **video** (`.mp4`, `.mov`, `.mkv`, `.webm`) — especially a
screen-recording (OBS, Teams) where the shared screen carries information — use the
**`transcribe_video.py`** orchestrator instead of an engine script directly. One command:

1. **Splits** the audio out to a mono mp3 (so you have audio + video separately).
2. **Transcribes** that audio via the chosen engine (reuses the engine scripts below).
3. **Extracts candidate frames** at scene changes (slide/screen swaps) + writes a
   `manifest.md` correlating each frame to a timestamp you can match against the
   transcript's `[MM:SS]` tags.

```bash
uv run ~/.claude/skills/transcribe/scripts/transcribe_video.py <video> [options]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--engine {deepgram,assemblyai,groq,xai}` | Transcription engine | `deepgram` |
| `--output PATH` | Transcript path | `<video>.transcript.md` |
| `--frames-dir PATH` | Where candidate frames go | `<video-stem>-frames/` beside the video |
| `--scene-threshold F` | Scene sensitivity 0–1, lower = more frames | `0.4` |
| `--max-frames N` | Cap on candidate frames (evenly sampled if exceeded) | `60` |
| `--min-gap S` | Min seconds between kept frames (dedupe) | `8` |
| `--interval S` | Fallback: if <3 scene changes, sample 1 frame / S sec | `120` |
| `--speakers N` | Forwarded to the assemblyai engine | — |
| `--no-frames` / `--no-transcribe` / `--no-keep-audio` | Skip a stage | off |

**Engine choice for video:** default `deepgram` (keyterm-biased, multi-speaker). For a
**clean 1:1**, use `--engine assemblyai` — it diarizes cross-talk noticeably better on
low-speaker-count audio (see ASR comparison artifact, Round 4). Then relabel speakers
(see "After Transcription").

### How to use the frames — transcript-guided is PRIMARY

The scene-detected + interval frames are a **coverage net, not a curated set.** The
reliable way to capture screen content is **transcript-guided**:

1. Read the transcript; find moments where a speaker references on-screen content
   ("let me show you", "see here", "this dashboard/diagram/form").
2. View the nearest candidate frame(s). To grab an **exact** moment not in the set:
   `ffmpeg -ss <seconds> -i "<video>" -frames:v 1 -q:v 2 out.png`.
3. **Keep only vault-worthy frames** (slides, diagrams, org charts, forms) — crop out
   webcam tiles / app chrome, rename descriptively, save into the note's `- photos/`
   folder, embed `![[name.png]]`. Extract info from transient frames and discard them.

**Scene-detection caveat:** windowed shares (a meeting window with static chrome + a
small changing sub-region) produce low whole-frame scene scores — `0.4` catches the
big screen swaps; lower `--scene-threshold` (e.g. `0.2`) for more granularity, or just
rely on transcript-guided extraction. (Full-screen slide decks register cleanly at `0.4`.)

### Identify speakers from the frames FIRST — before asking the user

For a video from a meeting app (Teams / Zoom / Meet / Webex) the **participant gallery
is on screen**, so the diarized `Speaker A/B/C…` labels can usually be resolved to real
names **deterministically from the video** — don't jump straight to asking the user. The
gallery gives you three independent signals:

1. **Name labels** under each tile → the roster of who's actually present (often fewer
   than the invite list — no-shows and listen-only attendees show here).
2. **Active-speaker highlight** — most clients draw a colored border / ring around the
   tile of whoever is currently talking. Sample a frame at a timestamp where one diarized
   speaker has a clean solo stretch, and the highlighted tile names them.
3. **Mute icons** — a muted tile cannot be the active speaker. This breaks ties and
   catches diarization *conflations* (when one bucket merges two voices): if the
   diarizer attributes a line to someone whose tile is muted at that timestamp, the line
   belongs to the other unmuted participant.

**Workflow:**

1. Pick 1-2 clean solo stretches per diarized speaker from the transcript's `[MM:SS]` tags.
2. Extract the exact frame and a zoomed crop of the gallery strip:
   ```bash
   ffmpeg -ss <seconds> -i "<video>" -frames:v 1 -q:v 2 /tmp/frame.png
   # gallery strip only (top band), upscaled so labels are legible:
   ffmpeg -ss <seconds> -i "<video>" -frames:v 1 -vf "crop=iw:ih*0.16:0:ih*0.09,scale=1920:-1" /tmp/strip.png
   ```
   (Adjust the crop band to where the client renders tiles — top for Teams, can be a
   side rail for Zoom speaker view.)
3. Read the highlighted tile + name label at each speaker's solo moment → build the
   `Speaker X → Name` map. Cross-check mute state to resolve any conflation.
4. Relabel the transcript with the confirmed names (`Speaker A` → `Name`, `replace_all`),
   and add a short speaker-key note recording how you resolved it + any known conflation.
5. **Only fall back to asking the user** when the gallery is unavailable — names hidden,
   a full-bleed screen-share covers the tiles for the whole call, or the highlight is
   ambiguous (heavy cross-talk, gallery paged). Then show sample utterances per label and
   ask, as for audio-only.

## ⛔️ AssemblyAI is permission-gated, never auto-fallback

User policy (set 2026-05-15): **if Deepgram fails, do NOT silently fall back to
AssemblyAI.** Stop, surface the failure, and ask the user whether to retry with
AssemblyAI before doing so.

The only exception: if the user has explicitly said they're walking away or
have given a blanket "operate autonomously" instruction *for this session*,
then fallback is permitted — note the fallback in your reply when they return.

This policy exists because the 2026-05-15 ASR comparison showed AssemblyAI
universal-3-pro **degrades when keyterms are loaded** (overcorrects, e.g.
substituted "Ankit" for the Napoleon Dynamite character "Kip"; substituted
"agent-skills" for the spoken word "agentic"). Routing meetings through it
silently would risk hallucinations David then has to clean up. See
`🎨 Artifacts/2026-05-15 ASR comparison — AssemblyAI vs Deepgram.md` in the
Ford vault for the full empirical comparison.

## Keyterm biasing — Deepgram only

Deepgram Nova-3's `keyterm` parameter is a scoped acoustic boost — it raises
the probability of listed terms without aggressively substituting other words.
Tested empirically (5/15) to fix dropped proper nouns and acronyms without
introducing new failures.

The skill ships **no keyterms by default** — the global skill is project-agnostic.
Each project supplies its own keyterm vocabulary. The Deepgram script discovers
the active keyterms file in this order:

1. **Explicit `--keyterms PATH`** — caller-supplied
2. **`$TRANSCRIBE_KEYTERMS` environment variable** — session-scoped
3. **`.transcribe-keyterms.txt` walking up from CWD** — project-scoped
   (drop a file at the project root and it gets auto-loaded)
4. **None** — no biasing, plain Nova-3 + diarization

Format is one term per line; lines starting with `#` are comments. Hand-edit
freely; per-project, you can also wire up an auto-refresh script that derives
terms from project state (people directory, glossary, etc.) — see the Ford vault
for an example at `Ford/.claude/transcribe-keyterms/refresh_keyterms.py`.

**Cap keyterms at ~60 total** to stay safely under Deepgram's
biasing-degradation threshold. (Tested at 60; works fine. AssemblyAI's same
feature degrades at much smaller counts — see comparison artifact.)

Pass `--no-keyterms` to skip biasing for a single run.

## Before Running

**For Groq (single-speaker default):** No questions — just transcribe.

**For xAI (single-speaker > 25 MB):** No questions — just transcribe. Same
keyterm auto-discovery as Deepgram.

**For Deepgram (multi-speaker default):** No questions — just transcribe.
Keyterms auto-discover from the project (CWD-walk-up `.transcribe-keyterms.txt`
or `$TRANSCRIBE_KEYTERMS`). If none found, runs without biasing — that's fine.

**For AssemblyAI:** **Never run without asking first.** If a Deepgram run
fails, surface the error and ask before retrying with AssemblyAI.

## Running Transcription

### Groq (default — single speaker)

```bash
uv run ~/.claude/skills/transcribe/scripts/transcribe_groq.py <file_path> [options]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--language LANG` | Language code (e.g., `en`, `es`) | Auto-detect |
| `--output PATH` | Output file path | `<input>.transcript.md` |

**Requirements:** `GROQ_API_KEY` env var, file under 25 MB

### Deepgram Nova-3 (default — multi-speaker)

```bash
uv run ~/.claude/skills/transcribe/scripts/transcribe_deepgram.py <file_path> [options]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--output PATH` | Output file path | `<input>.transcript.md` |
| `--keyterms PATH` | Keyterms file (one term per line) | Auto-discover via CWD-walk-up `.transcribe-keyterms.txt` or `$TRANSCRIBE_KEYTERMS` |
| `--no-keyterms` | Run without keyterm biasing | Off (biasing is on by default) |
| `--language LANG` | Language code | `en` |
| `--model MODEL` | Deepgram model | `nova-3` |

**Requirements:** `DEEPGRAM_API_KEY` env var. Cost ~$0.258/hr. Latency typically
3× faster than AssemblyAI on the same file (5/15 test: 9.8s vs 35s for 56:50 audio).

### xAI Speech-to-Text (single-speaker, large files)

```bash
uv run ~/.claude/skills/transcribe/scripts/transcribe_xai.py <file_path> [options]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--output PATH` | Output file path | `<input>.transcript.md` |
| `--keyterms PATH` | Keyterms file (one term per line) | Auto-discover via CWD-walk-up `.transcribe-keyterms.txt` or `$TRANSCRIBE_KEYTERMS` |
| `--no-keyterms` | Run without keyterm biasing | Off (biasing is on by default) |
| `--language LANG` | Language code | `en` |
| `--no-diarize` | Disable diarization request | Off (we still send `diarize=true` even though xAI currently ignores it — if/when xAI ships it, no skill update needed) |
| `--no-format` | Disable ITN formatting | Off |

**Requirements:** `XAI_API_KEY` env var. Cost ~$0.10/hr (REST). 500 MB max file
size. Single STT model behind `/v1/stt` — no `--model` flag. Latency on a 57-min
file: ~45s (3.6× slower than Deepgram, 7× faster than wall-clock would suggest
for the file's duration).

**Known limitation:** xAI diarization works on audio up to ~45 minutes. Past
that, the `speaker` key silently disappears from word objects (the rest of the
response is fine). For multi-speaker work over 45 min, either route to
Deepgram or chunk the audio at ~40-min boundaries with ffmpeg first. See
`🎨 Artifacts/2026-05-15 ASR comparison …` Round 3 for the empirical evidence,
including the per-duration test grid.

### AssemblyAI (permission-gated fallback only)

Reserve for:
- Explicit user request (`/transcribe ... --engine assemblyai` or "use AssemblyAI")
- Deepgram outage / 5xx — **after asking the user**

```bash
uv run ~/.claude/skills/transcribe/scripts/transcribe.py <file_path> [options]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--speakers N` | Expected number of speakers | Auto-detect |
| `--language LANG` | Language code | `en` |
| `--output PATH` | Output file path | `<input>.transcript.md` |
| `--model MODEL` | `universal-3-pro` ($0.21/hr) or `universal-2` ($0.15/hr) | `universal-3-pro` |

**Important:** the legacy `transcribe.py` script does NOT load keyterms because
AssemblyAI's `keyterms_prompt` causes overcorrections (see comparison artifact).
If you must use AssemblyAI, run *without* keyterm biasing and accept that
recurring names may be misheard.

**Requirements:** `ASSEMBLYAI_API_KEY` env var

## Output Format

All engines produce structured markdown with the same shape:

```markdown
# Transcript: recording.m4a

- **Transcribed**: 2026-03-21 14:30
- **Duration**: 5m 32s
- **Engine**: Deepgram nova-3 (general-nova-3)
- **Speakers detected**: 4
- **Language**: en
- **Word count**: 1,250
- **Wall-clock latency**: 9.8s
- **Keyterms loaded**: 60 (from keyterms.txt)

---

## Transcript

**[00:00] Speaker A:**
First segment of text...

**[00:15] Speaker B:**
Next segment...
```

A raw JSON sidecar is **always** written alongside the markdown
(`<output>.json`) — full API response including word-level timestamps,
confidences, and any add-on data. Co-located with the markdown so it follows
the transcript wherever it goes.

## After Transcription

1. **Read the file** to load it into context
2. **For a diarized VIDEO from a meeting app (Teams / Zoom / Meet / Webex) — resolve
   speakers from the participant gallery FIRST.** Read the on-screen tile name labels +
   active-speaker highlight + mute icons at each speaker's solo moment (see "Identify
   speakers from the frames FIRST" in the Video intake section) and relabel `Speaker A`
   → name (`replace_all: true`). This is deterministic and beats asking. Only fall back
   to asking the user when the gallery is unavailable (names hidden, full-bleed
   screen-share, ambiguous highlight).
3. **For a diarized AUDIO-ONLY transcript** — if the user mentioned participant names,
   show sample utterances from each speaker label and ask who is who, then
   find-and-replace `Speaker A` → name throughout (`replace_all: true`).
4. **If a meeting-platform VTT exists for the same recording, prefer it for speaker
   identity.** When the meeting client also exported a WebVTT caption file (run it
   through `/vtt-processor`), the VTT wins on speaker identity (real names baked into
   cue tags) while the ASR transcript wins on audio fidelity — VTT is canonical for
   *who*, ASR for *what*. (This is an alternative to the gallery method in step 2 — use
   whichever signal you have.)
5. **For video intake (screen content)** — open the frames `manifest.md`, then do
   transcript-guided triage (see the Video intake section): keep the vault-/note-worthy
   frames (slides, diagrams), extract info from the rest, and delete the `-frames/`
   working dir once keepers are saved.
6. **Ask what analysis they need** — summarize, extract action items, find topics, etc.

## Supported Formats

`.m4a`, `.mp4`, `.mp3`, `.wav`, `.flac`, `.ogg`, `.webm`, `.aac`, `.wma`

## Troubleshooting

- **Groq 25 MB limit**: For single-speaker, route to **xAI STT** (500 MB ceiling,
  $0.10/hr) — that's exactly the lane xAI was added for. For multi-speaker, route
  to **Deepgram** (no practical size limit, working diarization).
- **Missing API key**: Ensure `DEEPGRAM_API_KEY` / `GROQ_API_KEY` / `XAI_API_KEY` /
  `ASSEMBLYAI_API_KEY` is exported in `~/.zshenv`
- **Deepgram failure**: Surface the error to the user. **Do not auto-fallback
  to AssemblyAI** — ask first per user policy.
- **Poor diarization**: Deepgram auto-detects speaker count; if it undercounts
  badly, check the audio (overlapping speech / acoustic similarity confuses
  every diarizer). For really hard cases, the Teams VTT is canonical anyway.
- **Keyterms misfiring** (rare with Deepgram, common with AssemblyAI): edit
  the project's `.transcribe-keyterms.txt` and remove the offending term. If
  the project ships an auto-refresh script (e.g. the Ford vault's), add the
  term to that script's blacklist so future refreshes exclude it.

## Why this skill made these choices

The 2026-05-15 ASR comparison (full report:
`🎨 Artifacts/2026-05-15 ASR comparison — AssemblyAI vs Deepgram.md` in the
Ford vault) ran AssemblyAI universal-3-pro and Deepgram Nova-3 head-to-head on
the same Ford meeting audio — first at default settings, then maxed out with
keyterm biasing. Findings:
- **Deepgram Nova-3 + keyterms**: 3 fixes vs default, 0 new breaks. 3.5×
  faster than AssemblyAI. Comparable cost. No proper-noun hallucinations.
- **AssemblyAI universal-3-pro + keyterms**: 1 fix vs default, **3 new
  breaks** (substituted listed keyterms for acoustically similar non-listed
  words, e.g. "Kip" → "Ankit", "agentic" → "agent-skills"). This matches
  AssemblyAI's own docs warning that *"Including a large number of terms
  could lead to overcorrections and hallucinations."*

Hence: Deepgram default + keyterm biasing on; AssemblyAI permission-gated.

**Round 3 (2026-05-19) added xAI Speech-to-Text:**
- xAI is the cheapest engine in the table at $0.10/hr (~60% cheaper than Deepgram)
  and handles files up to 500 MB.
- xAI diarization works at any duration ≤45 min but silently drops the
  `speaker` field for longer audio (no error, key just absent). Verified on the
  same source audio at 60s/90s/10/25/35/45/57 min — speaker counts of 1/2/7/9/10/11/**0**.
  Peer review (Grok 4.3 + Composer 2.5) flagged the original "broken" claim;
  the small-clip control test surfaced the duration boundary.
- Single proper-noun preservation matches Deepgram (Jensen, Kip, John+Sid all
  correct) but compound tech tokens degrade — *OpenCode* splits into "Open Code",
  *MCPJam* drops entirely, even with both in the keyterms file.
- Net: xAI is a viable Deepgram alternative for short-to-medium meetings at 60%
  lower cost, **the** right engine for single-speaker > 25 MB, and the wrong
  choice for one-shot multi-speaker over 45 min (chunk first or use Deepgram).
