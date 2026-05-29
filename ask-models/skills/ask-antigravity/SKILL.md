---
name: ask-antigravity
description: >
  Consult Google's Antigravity CLI (`agy`) — the successor to the Gemini CLI —
  for a second opinion on plans, architecture, UI/UX design, debugging, or code
  generation. Exposes Gemini 3.5 Flash, Gemini 3.1 Pro, Claude Sonnet/Opus 4.6
  Thinking, and GPT-OSS 120B via agy's interactive Switch Model menu (no
  `--model` CLI flag yet). Default is whatever the user has pinned in agy
  (recommended: Gemini 3.5 Flash High). The wrapper is built for orchestration —
  start partners in the background, monitor liveness via output growth, collect
  final results. Triggers — "/ask-antigravity", "ask antigravity", "ask agy",
  "second opinion from antigravity/gemini", "what does Gemini 3.5 Flash say",
  "ask Claude 4.6 thinking via antigravity", or any "ask gemini" request (Google
  transitioned the Gemini CLI to the Antigravity CLI in late 2025).
---

# ask-antigravity

A second-opinion partner from Google's **Antigravity CLI** (`agy`), the
successor to the Gemini CLI announced by Google in late 2025. Designed to be
**driven by your Claude Code session as orchestrator**.

## Always use the wrapper

```
~/.claude/skills/ask-antigravity/scripts/ask.sh
```

Never call `agy` directly — the wrapper manages per-run state, captures
stderr (otherwise lost), exposes a uniform orchestration surface, and gives
you liveness signal during long calls.

## One-time setup (set your default model)

`agy` currently has **no `--model` CLI flag**. Model selection is interactive
only and persists across runs. Set your preferred default once:

```bash
agy                                  # launches the interactive REPL
# Open the Switch Model menu (slash command, or the chevron next to the prompt)
# Select: Gemini 3.5 Flash (High)    ← recommended default
# Quit. Your choice persists.
```

To change models later, re-enter the REPL and switch. The wrapper will
inherit whatever's pinned.

Available models (from your Google AI Pro entitlement):

- Gemini 3.5 Flash (High) — **recommended default**, fast + capable
- Gemini 3.5 Flash (Medium) — even faster, slightly weaker
- Gemini 3.1 Pro (High) — deepest reasoning on the Gemini side
- Gemini 3.1 Pro (Low) — Pro-class with lighter reasoning budget
- Claude Sonnet 4.6 (Thinking) — for Claude-style code review
- Claude Opus 4.6 (Thinking) — heaviest Claude option exposed
- GPT-OSS 120B (Medium) — OpenAI open-weight, hosted via MaaS

## Important: agy's stream is plain text, not JSONL

Unlike `ask-claude`/`ask-codex` (which emit per-token deltas) or `ask-gemini`
(which emits sparse JSON events), `agy -p` writes plain text to stdout. Live
introspection therefore relies on:

- **Process liveness** (pid alive)
- **`output.txt` growth** — mtime + byte count
- **`stderr.log` mtime** for diagnostics

The wrapper's `status` subcommand surfaces all three and adds heuristic hints
when output stalls.

## Two ways to use it

### Mode 1 — short one-shot (blocking, simplest)

```bash
~/.claude/skills/ask-antigravity/scripts/ask.sh "Critique this design and identify the main risk."
~/.claude/skills/ask-antigravity/scripts/ask.sh "Review the auth middleware." /path/to/project
echo "$LONG_PROMPT" | ~/.claude/skills/ask-antigravity/scripts/ask.sh - /path/to/project
```

Equivalent: `ask.sh ask "..."` (the explicit subcommand).

### Mode 2 — orchestrated (background + monitor)

```bash
# 1. Kick off
~/.claude/skills/ask-antigravity/scripts/ask.sh start "Design a checkout review screen layout." /path/to/project
# → RUN_ID=20260520-101234-a1b2c3

# 2. Watch liveness.
~/.claude/skills/ask-antigravity/scripts/ask.sh status latest
# → status: running, pid alive, output_bytes: 1240, last_write 2s ago

# 3. Block on completion.
~/.claude/skills/ask-antigravity/scripts/ask.sh wait latest
```

## Orchestrator playbook (you, Claude Code)

1. **`start`** the run; capture `RUN_ID`.
2. **Watch with Monitor** for live token-ish flow:
   ```
   Monitor command: tail -f $(ask.sh output <RUN_ID>)
   ```
3. **For long runs**, check `status` periodically. If `output_bytes` is `0`
   after 60s with `pid alive`, agy is likely waiting on auth or network —
   inspect `stderr.log`.
4. **Cancel if needed:** `ask.sh cancel <RUN_ID>`.
5. **Collect:** `ask.sh wait <RUN_ID> [--timeout N]`.

### Parallel partners

Each run has its own state dir under
`~/.cache/ask-runs/antigravity/<run-id>/`. Parallel-safe.

## Subcommand reference

| Subcommand | What it does | Blocks? |
|---|---|---|
| `start [opts] "prompt" [project-dir]` | Spawns child, prints `RUN_ID` and run dir | No |
| `status <run-id\|latest>` | Liveness summary + heuristic hints | No |
| `tail <run-id\|latest> [-n N]` | Last N lines of `output.txt` | No |
| `output <run-id\|latest>` | Prints absolute path to `output.txt` | No |
| `wait <run-id\|latest> [--timeout S]` | Block until done, print final response | Yes |
| `result <run-id\|latest>` | Print final response (errors if still running) | No |
| `cancel <run-id\|latest>` | Kill the child | No |
| `list [-n 10]` | Recent runs with status | No |
| `ask [opts] "prompt" [project-dir]` | Convenience: `start` + `wait` | Yes |

## Start/ask options

| Flag | Effect |
|---|---|
| `--continue`, `-c` | Continue agy's most recent conversation |
| `--conversation <id>` | Resume a specific agy conversation by ID |
| `--print-timeout <dur>` | Override agy's print-mode timeout (default `5m`). Examples: `2m`, `10m`, `30m` |
| `--add-dir <path>` | Add a directory to agy's workspace (repeatable) |
| `--sandbox` | Run agy with terminal sandbox restrictions |
| `--yolo` | Set `--dangerously-skip-permissions` (auto-enabled when `project-dir` is supplied) |

When a `project-dir` is supplied, the wrapper passes
`--dangerously-skip-permissions` automatically so agy can freely read files
in the workspace. Pass `--no-auto-yolo` to opt out.

## Run state layout

```
~/.cache/ask-runs/antigravity/<run-id>/
  prompt.txt    # the prompt sent to agy
  cmd.txt       # exact CLI invocation
  output.txt    # stdout (the response — captured live as agy writes it)
  stderr.log    # everything agy wrote to stderr
  final.txt     # copy of output.txt once the run finishes
  meta.json     # {tool, status, pid, started_at, started_epoch, ended_at,
                #  exit_code, duration_ms, project_dir}
```

`status` values: `running` → `done` | `failed` | `cancelled`.

Note: agy currently exposes no token-count telemetry to stdout, so the
wrapper records only wall-clock `duration_ms`. Token usage is visible inside
the agy REPL but not on `-p`.

## Design / code-generation use case

When you want agy to design or build UI, model choice matters:

- **Gemini 3.5 Flash (High)** — best balance of speed + quality, good default
- **Gemini 3.1 Pro (High)** — when you want deeper reasoning on complex layouts
- **Claude Opus/Sonnet 4.6 (Thinking)** — when you want a Claude-style code review of agy's own work

Workflow:

1. **Include project conventions in the prompt.** Tech stack, styling
   system, component library, theming approach.
2. **Pass project dir for file access** (`--dangerously-skip-permissions` is
   auto-enabled).
3. **Ask agy to write files** to specific paths under `src/components/...`.
4. **Capture and review** — read the files back and assess fit.

```bash
~/.claude/skills/ask-antigravity/scripts/ask.sh start - /path/to/project <<'EOF'
You are designing a frontend component for a React 19 + Vite app.

Tech stack: React 19 + TypeScript (strict), TailwindCSS 4 with CSS variables
(dark mode default), shadcn/ui (New York), Zustand, react-router-dom v7.

Task: Design and implement a CheckoutReviewSummary component. Match the
patterns in src/components/. Write to src/components/checkout-review-summary.tsx.
EOF
```

## Hang detection rules of thumb

- **Healthy:** `output_bytes` growing every few seconds; `last_write` < 30s.
- **Suspicious:** `pid alive`, `output_bytes: 0` for >60s. Check `stderr.log`
  — likely auth/network or a slow first-token. `status` will print a hint.
- **Long compute:** Once output begins, agy can pause briefly between
  sections. `last_write` up to ~60s is normal for heavy prompts.
- **Truly hung:** `pid alive` + no growth for >2 minutes → `cancel` and
  retry with a smaller prompt or a lighter model (switch interactively in
  agy first).

## Continuation

```bash
# Continue agy's most recent conversation
ask.sh ask -c "Now add error handling for the case where the API returns 503."

# Resume a specific conversation by ID
ask.sh ask --conversation abc123 "Apply the same pattern to the user settings page."
```

## Relationship to `ask-gemini`

`ask-gemini` is the wrapper for Google's legacy `gemini` CLI. Google has
announced that the Gemini CLI is being transitioned to the Antigravity CLI;
new work should prefer `ask-antigravity`. `ask-gemini` remains usable as
long as the `gemini` binary is installed, but its skill description has
been updated to deprioritize auto-triggering.
