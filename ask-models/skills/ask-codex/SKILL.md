---
name: ask-codex
description: Consult OpenAI's Codex CLI (GPT-5.5, high reasoning effort) for a second opinion on plans, architecture, debugging, or code review. The wrapper is built for orchestration — start partners in the background, watch the JSONL event stream live to detect hangs vs. real thinking, then collect final results.
---

# ask-codex

A second-opinion partner from OpenAI's Codex (GPT-5.5, high reasoning effort),
designed to be **driven by your Claude Code session as orchestrator**. The
wrapper runs `codex exec --json` so you can watch the partner's reasoning,
tool calls, and final answer stream in live, distinguish real progress from a
hang, and collect the clean final response.

## Always use the wrapper

```
~/.claude/skills/ask-codex/scripts/ask.sh
```

Never call `codex exec` directly — the wrapper enforces model + reasoning
effort, runs in `read-only` sandbox by default, captures the JSONL stream,
manages the per-run state directory, and gives you a uniform orchestration
surface that matches `ask-claude` and `ask-gemini`.

## Two ways to use it

### Mode 1 — short one-shot (blocking, simplest)

For a quick second opinion that should return in under a minute:

```bash
~/.claude/skills/ask-codex/scripts/ask.sh "Why might this migration fail?"
~/.claude/skills/ask-codex/scripts/ask.sh "Review the auth flow." /path/to/project
echo "$LONG_PROMPT" | ~/.claude/skills/ask-codex/scripts/ask.sh - /path/to/project
```

Equivalent: `ask.sh ask "..."` (the explicit subcommand).

### Mode 2 — orchestrated (background + live introspection)

For anything non-trivial — and Codex with `effort=high` often takes 30s–3min
of reasoning — **start the partner in the background and watch it work**.

```bash
# 1. Kick off — returns immediately with a RUN_ID
~/.claude/skills/ask-codex/scripts/ask.sh start "Trace why orders 12345 and 12346 ended up duplicated." /path/to/project
# → RUN_ID=20260501-101234-a1b2c3
# → EVENTS=~/.cache/ask-runs/codex/20260501-101234-a1b2c3/events.jsonl

# 2. Spot-check status while it's thinking.
~/.claude/skills/ask-codex/scripts/ask.sh status latest
# → status: running, pid alive, last_event 2s ago, 18 events

# 3. See what the partner is doing.
~/.claude/skills/ask-codex/scripts/ask.sh tail latest -n 15
# → [thread.started] 019de446-...
# → [item.completed] reasoning
# → [command] status=success cmd=grep -rn "order_id" ...
# → [agent_message] Looking at this, the duplication likely happens because...

# 4. Block on completion.
~/.claude/skills/ask-codex/scripts/ask.sh wait latest
```

## Orchestrator playbook (you, Claude Code)

1. **`start`** the run; capture `RUN_ID` from output.
2. **Watch live.** Two options:
   - **Notification stream via `Monitor`** — tail `events.jsonl` for the
     events you'd act on:
     ```
     Monitor command: tail -f $(ask.sh events <RUN_ID>) \
       | grep --line-buffered -E '"type":"turn.completed"|"type":"turn.failed"|"type":"item.completed"|"type":"error"'
     ```
   - **Polled status** — `ask.sh status <RUN_ID>` shows `last_event` age and
     event count. Codex emits `item.completed` events whenever it finishes a
     reasoning chunk or tool call, so a healthy run shows fresh events every
     few seconds.
3. **Decide hung vs. thinking.** Codex `effort=high` does long silent
   reasoning between events. A 30–60s gap with `pid alive` is normal,
   especially after a complex tool call. >2 minutes silence with no
   `turn.completed` yet is suspicious.
4. **Cancel if needed:** `ask.sh cancel <RUN_ID>`.
5. **Collect:** `ask.sh wait <RUN_ID> [--timeout N]` blocks and prints the
   final answer. `ask.sh result <RUN_ID>` prints the cached final without
   blocking.

### Parallel partners

Each run has its own state dir under `~/.cache/ask-runs/codex/<run-id>/`,
parallel-safe by construction. Run multiple Codex prompts simultaneously
when you want fan-out analysis.

## Subcommand reference

| Subcommand | What it does | Blocks? |
|---|---|---|
| `start [opts] "prompt" [project-dir]` | Spawns child, prints `RUN_ID` and run dir | No |
| `status <run-id\|latest>` | Liveness summary: state, pid, thread_id, last_event age | No |
| `tail <run-id\|latest> [-n N]` | Last N events (reasoning, commands, agent_message), pretty-printed | No |
| `events <run-id\|latest>` | Prints absolute path to `events.jsonl` | No |
| `wait <run-id\|latest> [--timeout S]` | Block until done, print final response | Yes |
| `result <run-id\|latest>` | Print final response (errors if still running) | No |
| `cancel <run-id\|latest>` | Kill the child | No |
| `list [-n 10]` | Recent runs with status | No |
| `ask [opts] "prompt" [project-dir]` | Convenience: `start` + `wait` | Yes |

`<run-id>` accepts the literal `latest` or any unique prefix.

## Start/ask options

| Flag | Effect |
|---|---|
| `--resume <thread-id>` | Resume an existing codex thread (preserves full conversation) |
| `--resume-last` | Resume the most recent codex thread |
| `--sandbox <mode>` | `read-only` (default) / `workspace-write` / `danger-full-access` |
| `--model <name>` | Override model (default: `gpt-5.5`) |
| `--effort <level>` | Reasoning effort (default: `high`) |

**Note on resume:** `codex exec resume` does not accept `-s`; the resumed
session inherits the sandbox from the original run.

## Run state layout

```
~/.cache/ask-runs/codex/<run-id>/
  prompt.txt        # the prompt sent to codex
  cmd.txt           # exact CLI invocation
  events.jsonl      # streaming JSONL events from --json
  stderr.log        # everything codex wrote to stderr
  final.txt         # clean final agent_message (written by codex's -o flag)
  meta.json         # {tool, model, status, pid, session_id (codex thread_id),
                    #  started_at, ended_at, exit_code,
                    #  input_tokens, cached_input_tokens, output_tokens,
                    #  reasoning_output_tokens}
```

`status` values: `running` → `done` | `failed` | `cancelled`. A run is
marked `failed` when codex emits `turn.failed`/`error` even if exit code is 0.

## Continuation: drilling deeper

```bash
TID=$(jq -r .session_id ~/.cache/ask-runs/codex/<run-id>/meta.json)
~/.claude/skills/ask-codex/scripts/ask.sh start --resume "$TID" "Now focus on migration safety." /path/to/project
```

Use plain `start`/`ask` for parallel-safe stateless calls. Use `--resume`
when you want stateful follow-up — the prior context is reused, no need to
re-send large diffs.

## Hang detection rules of thumb (codex-specific)

- **Healthy run:** `item.completed` events every 5–30s. `last_event` ages
  fluctuate as the model reasons silently between events.
- **Long silent reasoning:** With `effort=high`, codex can go 30–90s
  between events while building a long chain of thought. Don't cancel based
  on a single quiet minute — check whether the last event was a `command`
  (tool just ran), `reasoning` (mid-thought), or `agent_message` (about
  to wrap up).
- **Truly hung:** >3 minutes with `pid alive` and no new events. Use
  `cancel` and inspect `stderr.log` and `events.jsonl` for clues.
- **`turn.failed`:** terminal error from codex; final.txt may be empty.
  Wrapper marks `status: failed`.

## Sandbox modes

- **`read-only`** (default): Codex can read the workspace but not modify
  anything. Use for opinions, reviews, analysis.
- **`workspace-write`**: Codex can write files. Only when you want it to
  generate code or apply a fix.
- **`danger-full-access`**: Full system access. Only for explicit user
  request.
