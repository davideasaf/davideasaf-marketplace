---
name: ask-claude
description: Use when you want a second opinion from Claude Opus on code, debugging, design, refactors, or planning. The wrapper is built for orchestration — start partners in the background, watch their JSONL event stream live to detect hangs vs. real thinking, then collect final results. Pinned to claude-opus-4-8.
---

# ask-claude

A second-opinion partner from Claude Opus, designed to be **driven by your own
Claude Code session as orchestrator**. The wrapper runs `claude --print
--output-format stream-json` so you can watch the partner think token-by-token,
distinguish real progress from a hang, and collect the clean final answer.

## Always use the wrapper

```
~/.claude/skills/ask-claude/scripts/ask.sh
```

Never call `claude` directly — the wrapper enforces the model, sets up the
JSONL stream, manages the per-run state directory, and gives you a uniform
orchestration surface.

## Two ways to use it

### Mode 1 — short one-shot (blocking, simplest)

For a quick second opinion that should return in <30s, use the legacy
positional form. It blocks until the partner finishes, then prints the answer.

```bash
~/.codex/skills/ask-claude/scripts/ask.sh "Why might this migration fail?"
~/.codex/skills/ask-claude/scripts/ask.sh "Review the auth flow." /path/to/project
echo "$LONG_PROMPT" | ~/.codex/skills/ask-claude/scripts/ask.sh - /path/to/project
```

Equivalent: `ask.sh ask "..."` (the explicit subcommand).

### Mode 2 — orchestrated (background + live introspection)

For anything non-trivial, **start the partner in the background and watch it
work**. This is the whole point of the wrapper — you stay in control, you can
tell the difference between "still thinking" and "hung", and you can pull the
result whenever it's ready.

```bash
# 1. Kick off — returns immediately with a RUN_ID
~/.codex/skills/ask-claude/scripts/ask.sh start "Review the migration in /tmp/diff.patch and identify the riskiest change." /path/to/project
# → RUN_ID=20260501-101234-a1b2c3
# → EVENTS=~/.cache/ask-runs/claude/20260501-101234-a1b2c3/events.jsonl

# 2. While the partner thinks, do something else, then check on it.
~/.codex/skills/ask-claude/scripts/ask.sh status latest
# → status: running, pid alive, last_event 0s ago, 47 events

# 3. Spot-check what it's doing right now.
~/.codex/skills/ask-claude/scripts/ask.sh tail latest -n 15
# → [delta] The first risk I see is that...
# → [tool_use] Read
# → [delta] Looking at line 142...

# 4. Block on completion when you need the answer.
~/.codex/skills/ask-claude/scripts/ask.sh wait latest
# → prints the clean final response
```

## Orchestrator playbook (you, Claude Code)

When you delegate to ask-claude as a partner, your loop is:

1. **`start`** the run with the prompt and (optionally) project dir. Capture
   `RUN_ID` from the first line of output.
2. **Watch live.** Two equally good options:
   - **Notification stream** — use the `Monitor` tool to tail `events.jsonl`.
     Each new line becomes a notification, so you literally get pinged as the
     partner produces tokens. Use a filter that matches the events you'd act
     on (errors + final result) plus a sample of progress:
     ```
     Monitor command: tail -f $(ask.sh events <RUN_ID>) \
       | grep --line-buffered -E '"type":"result"|"type":"system"|content_block_start|api_retry|"is_error":true'
     ```
   - **Polled status** — call `ask.sh status <RUN_ID>` whenever you naturally
     re-check. The `last_event` field tells you how stale the stream is —
     anything >60s with no `result` yet is suspicious.
3. **Decide hung vs. thinking.** Hung = pid alive AND `last_event > N
   seconds` AND no `result` event yet. Thinking = events landing every few
   seconds, including `stream_event`/`content_block_delta` lines.
4. **Cancel if needed:** `ask.sh cancel <RUN_ID>`.
5. **Collect:** `ask.sh wait <RUN_ID> [--timeout N]` blocks and prints the
   final answer. `ask.sh result <RUN_ID>` prints the cached final without
   blocking (errors if the run is still going).

### Parallel partners

Each run has its own state dir under `~/.cache/ask-runs/claude/<run-id>/`,
so you can have several runs in flight at once and monitor them
independently. This is the right pattern for adversarial review (two partners
on the same code from different angles) or for fan-out research.

## Subcommand reference

| Subcommand | What it does | Blocks? |
|---|---|---|
| `start [opts] "prompt" [project-dir]` | Spawns child, prints `RUN_ID` and run dir | No |
| `status <run-id\|latest>` | Liveness summary: state, pid, session_id, last_event age | No |
| `tail <run-id\|latest> [-n N]` | Last N events, pretty-printed | No |
| `events <run-id\|latest>` | Prints absolute path to `events.jsonl` (for Monitor/Read) | No |
| `wait <run-id\|latest> [--timeout S]` | Block until done, print final response | Yes |
| `result <run-id\|latest>` | Print final response (errors if still running) | No |
| `cancel <run-id\|latest>` | Kill the child | No |
| `list [-n 10]` | Recent runs with status | No |
| `ask [opts] "prompt" [project-dir]` | Convenience: `start` + `wait` | Yes |

`<run-id>` accepts the literal `latest` or any unique prefix.

## Start/ask options

| Flag | Effect |
|---|---|
| `--continue` | Continue the most recent claude conversation in cwd |
| `--resume <session-id>` | Resume a specific claude session |
| `--session-id <uuid>` | Pin to an explicit session UUID |
| `--fork-session` | Branch from `--resume` into a new session id |
| `--model <name>` | Override model (default: `claude-opus-4-8`) |
| `--bare` | Pass `--bare` to claude — skip CLAUDE.md, hooks, plugins, auto-memory. **Note:** strips OAuth, so requires `ANTHROPIC_API_KEY`. Use only when you want a clean room and have the env set. |

## Run state layout

```
~/.cache/ask-runs/claude/<run-id>/
  prompt.txt        # the prompt sent to claude
  cmd.txt           # exact CLI invocation (for reproduction/debug)
  events.jsonl      # streaming JSONL events from --output-format stream-json
  stderr.log        # everything claude wrote to stderr
  final.txt         # clean final response text (extracted from result event)
  meta.json         # {tool, model, status, pid, session_id, started_at, ended_at,
                    #  exit_code, cost_usd, duration_ms, input_tokens, output_tokens, ...}
```

`status` values: `running` → `done` | `failed` | `cancelled`.

## Long prompts

For long or multi-line prompts, write to a temp file and pipe in via `-`:

```bash
TMP="/tmp/ask-claude-${$}-${RANDOM}.txt"
cat > "$TMP" <<'EOF'
You are reviewing a failing sync job.
Context: ...
Questions:
1. Likely root cause?
2. Smallest safe fix?
EOF
~/.codex/skills/ask-claude/scripts/ask.sh start - /path/to/project < "$TMP"
rm -f "$TMP"
```

## Continuation: drilling deeper into the same conversation

The wrapper preserves the full claude continuation API. Capture the
`session_id` from a previous run's `meta.json`, then resume:

```bash
SID=$(jq -r .session_id ~/.cache/ask-runs/claude/<run-id>/meta.json)
~/.codex/skills/ask-claude/scripts/ask.sh start --resume "$SID" "Now propose the smallest safe fix." /path/to/project
```

Use plain `start`/`ask` for parallel-safe stateless calls. Use
`--resume <id>` (preferred) or `--continue` (most-recent in cwd, less
deterministic) when you want stateful follow-up.

## Hang detection rules of thumb

- **`status: running`, pid alive, `last_event` <30s** → still working, leave it.
- **`last_event` 30–120s, no `result` yet** → likely a slow turn (large
  prompt, deep reasoning) — keep waiting. Check `tail` for any `tool_use`
  events; if the partner is using tools, this is normal.
- **`last_event` >120s, no `result`** → suspicious. Re-check with `tail` for
  the most recent activity. If the last event was `tool_use` against a
  long-running tool, give it more time. Otherwise consider `cancel`.
- **`is_error: true` in the result event** → the partner returned an error
  (auth, max-turns, budget). The wrapper marks `status: failed`; check
  `final.txt` and `stderr.log` for details.
