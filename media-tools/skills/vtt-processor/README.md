# 🎙️ VTT Transcript Processor

A utility skill for cleaning WebVTT transcript files into token-efficient, speaker-attributed text.

---

## ✨ What It Does

Converts verbose `.vtt` files (from Microsoft Teams, Zoom, etc.) into clean, readable transcripts with **~62% token reduction**. Strips timestamps, UUIDs, and metadata while preserving speaker attribution.

---

## 🚀 Quick Start

No environment variables or setup required - just Python 3.10+.

```bash
# Process a VTT file and save cleaned output
python3 scripts/clean_vtt.py meeting.vtt -o meeting-clean.txt --stats
# Output: meeting.vtt: 149,815 -> 57,291 bytes (61.8% reduction)
```

---

## 💬 Usage Examples

| Task | Command |
|------|---------|
| Print to stdout | `python3 scripts/clean_vtt.py meeting.vtt` |
| Save to file | `python3 scripts/clean_vtt.py meeting.vtt -o clean.txt` |
| In-place conversion | `python3 scripts/clean_vtt.py meeting.vtt --in-place` |
| Batch process | `python3 scripts/clean_vtt.py *.vtt --in-place --stats` |

---

## 📊 Before & After

**Before** (~150KB VTT):
```
43e1361d-9fd2-4a60-b986-3bc18bb263f1/7-0
00:00:03.451 --> 00:00:07.449
<v Jane Doe (Marketing)>We need to discuss the Q1 roadmap
and priorities.</v>

43e1361d-9fd2-4a60-b986-3bc18bb263f1/7-1
00:00:07.449 --> 00:00:12.322
<v Jane Doe (Marketing)>I think we should focus on
the installer network first.</v>
```

**After** (~57KB clean text):
```
Jane Doe (Marketing): We need to discuss the Q1 roadmap and priorities. I think we should focus on the installer network first.
```

---

## 🔗 Used By

This skill provides VTT processing for other skills:

- 🟣 [`talent-hiring`](../talent-hiring/README.md) - Interview transcript processing

---

## 📁 Structure

```
vtt-processor/
├── SKILL.md           # Skill definition
├── README.md          # This file
└── scripts/
    └── clean_vtt.py   # VTT cleaning utility (no dependencies)
```
