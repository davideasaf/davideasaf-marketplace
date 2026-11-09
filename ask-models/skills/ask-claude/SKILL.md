---
name: ask-claude
description: Use when a second opinion from Claude Opus 5.5, Sonnet 5.5, or Fable 5.2 would help with code, debugging, design, refactors, or planning.
---

# ask-claude

A second-opinion partner from Claude Opus 5.5, Sonnet 5.5, or Fable 5.2, designed to be
**driven by your own Claude Code session as orchestrator**. The wrapper defaults
to Opus 5.5 and runs `claude --print
--output-format stream-json` so you can watch the partner think token-by-token,
distinguish real progress from a hang, and collect the clean final answer.

## Always use the wrapper

```
~/.claude/skills/ask-claude/scripts/ask.sh
```

Never call `claude` directly — the wrapper enforces the model, sets up the
JSONL stream, manages the per-run state directory, and gives you a uniform
orchestration surface.

## Requirements and platforms

- `claude` (Claude Code CLI), signed in; `bash`, `jq`, `python3`, and `uuidgen` on `PATH`.
- macOS or Linux. **On Windows, run it inside WSL** (WSL2 Ubuntu works): install
  Claude Code inside the distro, sign in there, and copy the skill into the WSL
  home (`~/.claude/skills/ask-claude`). The supervisor uses POSIX file locks and
  process groups, so native Windows Python, PowerShell, and Git Bash are not supported.
- Ubuntu/WSL: `sudo apt install jq uuid-runtime` provides `jq` and `uuidgen`.
- Keep `ask.sh` with LF line endings; a CRLF copy fails with `bash\r` errors.

## Choose the mode by shell lifetime

**In a short-lived tool shell (including Codex `exec_command`), use blocking
`ask.sh ask` in one tool command.** For a long answer, keep that command's
session alive and poll its session ID. Do not use `start` in one tool call and
`wait` in another: the tool may stop background children when the first shell
exits, leaving empty `events.jsonl` and `final.txt` files. An empty result or
`done` with zero events is not a successful Claude response.

Use `start`/`status`/`wait` only when the shell or process supervisor is known
to keep the background child alive after `start` returns.

## Model selection

| Request | Exact model | How to invoke |
|---|---|---|
| No model specified | Opus 5.5 (`claude-opus-5-5`) | Omit `--model`; this is the default |
| Opus or Opus 5.5 | `claude-opus-5-5` | Omit `--model`, pass `--model opus`, or pass the exact ID |
| Sonnet or Sonnet 5.5 | `claude-sonnet-5-5` | Pass `--model sonnet` or the exact ID |
| Opus 5 | `claude-opus-5` | Pass `--model opus-5` or the exact ID |
| Fable or Fable 5.2 | `claude-fable-5-2` | Pass `--model fable` or the exact ID |
| Fable 5.1 | `claude-fable-5-1` | Pass `--model fable-5.1` or the exact ID |

The wrapper pins the human aliases `opus`, `sonnet`, and `fable` to the exact identifiers
above, so requests remain reproducible even if Claude Code's own moving aliases
change later. Other explicit model identifiers pass through unchanged.

```bash
# Default: Opus 5.5
~/.claude/skills/ask-claude/scripts/ask.sh ask "Review this migration."

# Alternate: Fable 5.2
~/.claude/skills/ask-claude/scripts/ask.sh ask --model fable "Review this migration."
```

## Two ways to use it

### Mode 1 — blocking (default for tool shells)

Use the explicit `ask` subcommand or legacy positional form. Both block until
the partner finishes and print the answer. For work lasting more than a tool's
initial yield time, poll the same running tool session rather than starting a
new shell command.

```bash
~/.claude/skills/ask-claude/scripts/ask.sh "Why might this migration fail?"
~/.claude/skills/ask-claude/scripts/ask.sh "Review the auth flow." /path/to/project
echo "$LONG_PROMPT" | ~/.claude/skills/ask-claude/scripts/ask.sh - /path/to/project
```

Equivalent: `ask.sh ask "..."` (the explicit subcommand).

### Mode 2 — persistent shell only (background + live introspection)

When a persistent shell or process supervisor keeps background children alive,
you can start the partner in the background and watch it work. This lets you
distinguish "still thinking" from "hung" and collect the result when ready.

```bash
# 1. Kick off — returns immediately with a RUN_ID
~/.claude/skills/ask-claude/scripts/ask.sh start "Review the migration in /tmp/diff.patch and identify the riskiest change." /path/to/project
# → RUN_ID=20260501-101234-a1b2c3
# → EVENTS=~/.cache/ask-runs/claude/20260501-101234-a1b2c3/events.jsonl

# 2. While the partner thinks, do something else, then check on it.
~/.claude/skills/ask-claude/scripts/ask.sh status latest
# → status: running, pid alive, last_event 0s ago, 47 events

# 3. Spot-check what it's doing right now.
~/.claude/skills/ask-claude/scripts/ask.sh tail latest -n 15
# → [delta] The first risk I see is that...
# → [tool_use] Read
# → [delta] Looking at line 142...

# 4. Block on completion when you need the answer.
~/.claude/skills/ask-claude/scripts/ask.sh wait latest
# → prints the clean final response
```

## Orchestrator playbook (you, Claude Code)

In a persistent shell, the background loop is:

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
| `start [opts] "prompt" [project-dir]` | Spawns child; requires persistent shell or supervisor | No |
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
| `--model <name>` | Override model (default: `claude-opus-5-5`; `fable` pins Fable 5.2, `sonnet` pins Sonnet 5.5, and `opus` pins Opus 5.5) |
| `--safe-mode` | Disable customizations while retaining normal authentication. |
| `--restricted` | Apply Claude Code restricted mode. |
| `--tools <list>` | Select built-in tools; pass `--tools ""` to disable them. |
| `--allowedTools <list>`, `--disallowedTools <list>` | Forward tool permission lists as a single quoted argument. |
| `--permission-mode <mode>`, `--permission-prompts <target>` | Forward permission controls; `bypassPermissions` is rejected. |
| `--max-budget-usd <amount>`, `--effort <level>` | Forward cost and effort controls. Budget is the CLI's control, not a guaranteed billing ceiling. |
| `--strict-mcp-config`, `--mcp-config <json-or-path>` | Restrict MCP loading and optionally specify explicit servers. |
| `--disable-slash-commands`, `--no-chrome` | Disable skills or Chrome integration. |
| `--no-session-persistence` | Avoid saved sessions; these calls cannot subsequently resume. |
| `--system-prompt <text>`, `--setting-sources <sources>` | Forward explicit prompt and configuration-source controls. |
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
~/.claude/skills/ask-claude/scripts/ask.sh ask - /path/to/project < "$TMP"
rm -f "$TMP"
```

## Continuation: drilling deeper into the same conversation

The wrapper preserves the full claude continuation API. Capture the
`session_id` from a previous run's `meta.json`, then resume:

```bash
SID=$(jq -r .session_id ~/.cache/ask-runs/claude/<run-id>/meta.json)
~/.claude/skills/ask-claude/scripts/ask.sh ask --resume "$SID" "Now propose the smallest safe fix." /path/to/project
```

Use plain `ask` for stateless calls in tool shells; use `start` only with a
persistent shell or process supervisor. Use
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

## Completion and cancellation contract

A Python supervisor launches Claude in a separate process group, records the child
exit, reaps Claude, and publishes the final response before terminal metadata under
one lock. `wait` and `result` return nonzero for failed or cancelled runs, including
empty output or a missing terminal result event. Partial streaming text remains
available for diagnosis and does not establish successful completion. Response model
metadata is recorded separately from the requested model when emitted by Claude.

`wait --timeout N` returns 124 without stopping the run. `cancel` requests shutdown
from the live supervisor, sends TERM then KILL to the contained process group, and
waits for acknowledgement; cancelled results return 130. Missing acknowledgement
is an error, not confirmed cancellation. Old runs created before this supervisor
was installed do not gain process ownership retroactively. Processes that detach
into another session are outside this containment contract.

Run files include `ready`, `supervisor.done`, `supervisor.log`, and (when requested)
`cancel.request`. `pid` identifies the supervisor; `child_pid` identifies Claude.
Background survival still depends on the execution host. No sleep/reboot restart
or hours-long inference guarantee is implied. Use a persistent supervisor for workers.

For a tools-disabled consultation in an empty scratch directory, while retaining
normal OAuth authentication:

```bash
~/.claude/skills/ask-claude/scripts/ask.sh ask --model sonnet \
  --safe-mode --restricted --tools "" --strict-mcp-config \
  --disable-slash-commands --permission-mode dontAsk --permission-prompts none \
  --no-session-persistence --no-chrome --max-budget-usd 0.10 \
  --system-prompt "Reply only to the supplied readiness prompt." \
  "Return READY." /path/to/empty/scratch
```

Unknown options are rejected; use `--` before a prompt beginning with a dash.
Controls are passed as individual shell arguments, without shell evaluation.
Offline verification:

```bash
ASK_RUN_ROOT=/tmp/ask-claude-tests python3 -m unittest discover -s ~/.claude/skills/ask-claude/scripts -p 'test_*.py' -v
```
