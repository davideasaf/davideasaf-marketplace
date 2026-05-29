---
name: transcribe
description: >-
  Transcribe audio/video files — voice notes, recordings, meetings, conversations.
  Uses Groq Whisper (fast, free) by default for single-speaker audio under 25 MB,
  xAI Speech-to-Text for single-speaker audio over 25 MB, and Deepgram Nova-3 with
  keyterm biasing for multi-speaker diarization. Use this skill whenever
  the user wants to transcribe a recording, diarize speakers, convert a meeting to
  text, or process any audio/video file (.m4a, .mp4, .wav, .mp3, .webm, .ogg, etc.)
  into a readable transcript. Also use when the user mentions "transcribe", "diarize",
  "meeting notes from recording", "who said what", or wants to analyze/summarize an
  audio file.
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
2. **For diarized transcripts** — If the user mentioned participant names, show
   sample utterances from each speaker label and ask who is who. Then
   find-and-replace `Speaker A` → name throughout (use `replace_all: true`).
3. **For Ford meetings — prefer the Teams VTT for speaker identity.** If a
   Teams VTT exists for the same meeting (run through `/vtt-processor`), the
   VTT wins on speaker identity (real names baked into cue tags); the Deepgram
   transcript wins on audio fidelity. Per the David memory
   `feedback_prefer_teams_vtt_for_speakers` — VTT is canonical for *who*; ASR
   is canonical for *what*.
4. **Ask what analysis they need** — summarize, extract action items, find
   topics, etc.

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
