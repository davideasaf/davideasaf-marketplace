---
name: ask-codex
description: Consult OpenAI's Codex CLI for a second opinion on plans, architecture, design, debugging, or code review. Defaults to GPT-6.1-Sol at xhigh reasoning effort, with aliases for GPT-6-Astra, GPT-6.1-Terra and GPT-6-Luna. Computer use defaults to GPT-6.1-Terra at max effort. Use when the user says "/ask-codex", "ask codex", "ask astra", "ask sol", "ask terra", or names a Codex model. The wrapper is built for orchestration — run partners through the host agent's managed background facility, watch the JSONL event stream live to detect hangs vs. real thinking, then collect final results.
---

# ask-codex

A second-opinion partner from OpenAI's Codex (GPT-6.1-Sol, xhigh reasoning effort),
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

Normal `run` and blocking `ask` execution never register a dynamic macOS job.
The host agent owns the foreground wrapper through its managed background
facility. Missing exit code or output still fails closed, and cancellation
remains terminal across later finalization. Legacy `start` is disabled unless
the Security-approved `ASK_ALLOW_LAUNCHCTL=1` compatibility opt-in is present.

When Fable Orchestrator invokes the wrapper, each run also receives a private
`HOME` and `CODEX_HOME`. Only a mode-`0600` copy of `auth.json` is carried in;
user config, MCP servers, plugins, and global skills are not inherited. Apps,
the remote plugin catalog, multi-agent delegation, hooks, goals, and web search
are explicitly disabled, and repository `AGENTS.md` instructions are excluded
so the controller-authored worker brief remains the only task authority. The
temporary auth copy is removed when the worker reaches a terminal state.

## Models

The default is GPT-6.1-Sol at xhigh effort. Pick another model by task when needed. Check the live
catalog with `jq -r '.models[]|select(.visibility=="list")|.slug' ~/.codex/models_cache.json`
when this table looks stale.

| Alias | Model | Use for |
|---|---|---|
| `astra` | `gpt-6-astra` | Hardest work: architecture, design, deep review |
| `sol` (default) | `gpt-6.1-sol` | Latest workhorse: everyday coding and quick opinions |
| `terra` | `gpt-6.1-terra` | Computer use and browser missions (default with `--computer-use`) |
| `luna` | `gpt-6-luna` | Fast and cheap: simple checks, fan-out |

Reasoning efforts on Astra, Sol and Terra: `low`, `medium`, `high`, `xhigh`, `max`,
`ultra`. Luna stops at `max`. `gpt-5.5` and the 5.6 family are older generations.

## Additional capabilities

### Defaults and models

- The default is unchanged: `gpt-6.1-sol` at effort `xhigh`, read-only sandbox.
- The aliases `sol`, `astra`, `terra` and `luna` are case-insensitive.

### Lifecycle

- `run` runs in the foreground and is managed by the host.
- `ask` blocks until it finishes.
- `start` is gated and is not a default.

### Computer use

- `--computer-use` explicitly selects `danger-full-access`.
- It defaults to `gpt-6.1-terra` at effort `max` (David, 2026-10-27). Each default applies only when `--model` or `--effort` is absent, whatever the flag order. An explicit model or effort is kept.
- Why Terra: in David's 2026-10-26 Best Buy add-to-cart test, the time to confirmation was Terra High 13.4 s, Astra High 17.6 s and Sol High 21.9 s. That was one run per model in different browsers, not a controlled benchmark. Log each computer-use run's model, effort, wall time and outcome in `references/computer-use-evals.md`, and revisit the default once there are a few comparable runs.
- A new computer-use prompt starts with `references/computer-use-mission.md`. If that preamble is missing, the run fails before the provider launches.

### Inputs and environment

- `--image FILE` and `--config KEY=VALUE` can be repeated, and each keeps its argument boundaries.
- `ASK_CODEX_BIN` overrides the executable. `CODEX_CONFIG` is an optional config path used by preflight.
- `codex exec` refuses a working directory that is neither inside a git repo nor listed as trusted in `config.toml`. When the project dir (or `$PWD` when none is given) is in that state, the wrapper adds `--skip-git-repo-check` and records `skip_git_repo_check: true` in meta. An isolated Fable run has no user config, so only git counts there. This lets a scratch folder serve as the project dir. The sandbox setting is unchanged.

### Preflight

Preflight checks the CLI, the configured computer-use plugin, the support app, git and trust settings (reporting when the wrapper will add `--skip-git-repo-check`), and the current screen-lock signal. It changes nothing. Its results are readiness indicators, not proof that a live run will work.

### Reply

`reply RUN_ID [--wait] MESSAGE` reuses the recorded thread ID, model, effort, project and computer-use mode. By default it runs as a managed foreground run. With `--wait`, it returns only the final result. A reply is a follow-up request and does not grant human authorization on its own.

### Metadata and exit codes

- Metadata includes `computer_use` and `screen_locked`.
- It also includes `outcome`, parsed from `DONE`, `BLOCKED`, `NEEDS_CONFIRMATION` or `WAITING_FOR_HUMAN` in the successful final text.
- Empty output is recorded as `empty-output`.
- `wait`, `result` and `ask` return nonzero for failed, cancelled or empty results.

### Other requirements

- Keep the existing cleanup of isolated Fable auth.
- Do not assume any particular browser or profile exists.

## Two ways to use it

### Mode 1 — short one-shot (blocking, simplest)

For a quick second opinion that should return in under a minute:

```bash
~/.claude/skills/ask-codex/scripts/ask.sh "Why might this migration fail?"
~/.claude/skills/ask-codex/scripts/ask.sh "Review the auth flow." /path/to/project
echo "$LONG_PROMPT" | ~/.claude/skills/ask-codex/scripts/ask.sh - /path/to/project
```

Equivalent: `ask.sh ask "..."` (the explicit subcommand).

### Mode 2 — orchestrated (managed background + live introspection)

For anything non-trivial — and Codex with `effort=xhigh` often takes 30s–3min
of reasoning — invoke **`run` through the host agent's native background
command/session facility** and watch it work.

```bash
# 1. Background this entire command using the host's managed process facility.
# It prints RUN_ID immediately, then stays attached until the child completes.
~/.claude/skills/ask-codex/scripts/ask.sh run "Trace why orders 12345 and 12346 ended up duplicated." /path/to/project
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

1. **Background the entire `run` command using the host agent's managed
   process/session facility.** Capture `RUN_ID` from output. Do not append
   shell `&` and do not call legacy `start`.
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
3. **Decide hung vs. thinking.** Codex `effort=xhigh` does long silent
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
| `run [opts] "prompt" [project-dir]` | Runs child in foreground for host-managed backgrounding | Yes |
| `start [opts] "prompt" [project-dir]` | Legacy `launchctl` detach; explicit Security-approved opt-in only | No |
| `status <run-id\|latest>` | Liveness summary: state, pid, thread_id, last_event age | No |
| `tail <run-id\|latest> [-n N]` | Last N events (reasoning, commands, agent_message), pretty-printed | No |
| `events <run-id\|latest>` | Prints absolute path to `events.jsonl` | No |
| `wait <run-id\|latest> [--timeout S]` | Block until done, print final response | Yes |
| `result <run-id\|latest>` | Print final response (errors if still running) | No |
| `cancel <run-id\|latest>` | Kill the child | No |
| `list [-n 10]` | Recent runs with status | No |
| `ask [opts] "prompt" [project-dir]` | Convenience: managed run + final result | Yes |

`<run-id>` accepts the literal `latest` or any unique prefix.

### Legacy detached compatibility

`start` is disabled by default because it registers a dynamic `launchd` job.
Use blocking `ask` or host-managed `run` instead. Only after explicit Security
approval may one invocation enable the legacy backend:

```bash
ASK_ALLOW_LAUNCHCTL=1 ~/.claude/skills/ask-codex/scripts/ask.sh start "prompt" /path/to/project
```

Do not substitute cron, `nohup`, shell `&`, or another scheduler.

## Run/start/ask options

| Flag | Effect |
|---|---|
| `--resume <thread-id>` | Resume an existing codex thread (preserves full conversation) |
| `--resume-last` | Resume the most recent codex thread |
| `--sandbox <mode>` | `read-only` (default) / `workspace-write` / `danger-full-access` |
| `--model <name>` | Override model (default: `gpt-6.1-sol`). Aliases: `astra`, `sol`, `terra`, `luna` |
| `--effort <level>` | Reasoning effort (default: `xhigh`) |

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
  runner.sh          # private runner owned by the host-managed command session
  runner_pid         # runner PID
  cancelled          # immutable cancellation marker, when applicable
  auth-removed        # proves the temporary Fable auth copy was cleaned up
  runtime-home/      # Fable-only private HOME
    .codex/           # auth-only while running; empty after terminal cleanup
```

`status` values: `running` → `done` | `empty-output` | `failed` | `cancelled`. A run is
marked `failed` when codex emits `turn.failed`/`error` even if exit code is 0.

## Continuation: drilling deeper

```bash
TID=$(jq -r .session_id ~/.cache/ask-runs/codex/<run-id>/meta.json)
~/.claude/skills/ask-codex/scripts/ask.sh run --resume "$TID" "Now focus on migration safety." /path/to/project
```

Use host-managed `run` or blocking `ask` for parallel-safe stateless calls. Use `--resume`
when you want stateful follow-up — the prior context is reused, no need to
re-send large diffs.

## Hang detection rules of thumb (codex-specific)

- **Healthy run:** `item.completed` events every 5–30s. `last_event` ages
  fluctuate as the model reasons silently between events.
- **Long silent reasoning:** With `effort=xhigh`, codex can go 30–90s
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
