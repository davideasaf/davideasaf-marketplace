---
name: ask-cursor
description: >
  Consult Cursor's `agent` CLI to get a second opinion from any model Cursor
  exposes — Opus 4.7, GPT-5.4 1M, Opus 4.6, Gemini 3.1 Pro, Grok 4.3 1M,
  Composer 2.5, and more. Use this skill whenever the user says "/ask-cursor",
  "ask cursor", "what does cursor say", "get a take from cursor", or names a
  specific Cursor-hosted model ("ask opus 4.7", "ask grok", "ask gpt-5.4 via
  cursor"). Also use whenever the user wants a review from a model that isn't
  covered by ask-codex or ask-gemini (notably Opus 4.x, Grok, and Cursor's
  Composer). Supports single-model calls, parallel multi-model panels, and
  per-model session resume. Can run alongside ask-codex and ask-gemini in the
  same response.
---

# Ask Cursor

Route a prompt to one (or several) of Cursor's hosted models via the `agent`
CLI and return the response. Cursor aggregates multiple model families
(Anthropic, OpenAI, Google, xAI, Moonshot, and Cursor's own Composer) behind a
single CLI, which is useful for:

- Getting a take from a model you can't reach through another native CLI
  (Opus 4.x, Grok, Composer)
- Running a **panel review** — same prompt across several models in parallel,
  then synthesizing the answers
- Comparing two versions of the same family (Opus 4.6 vs Opus 4.7) on one question

## When to prefer ask-cursor vs. the native skills

There is overlap — some families are reachable through more than one skill.
Choose based on the user's intent:

| User's phrasing | Skill to use |
|---|---|
| "ask codex", "ask gpt-5" (no client specified) | `ask-codex` (native) |
| "ask gemini" (no client specified) | `ask-gemini` (native) |
| "/ask-cursor", "ask cursor", "ask <model> via cursor" | `ask-cursor` (this skill) |
| "ask opus 4.7", "ask grok", "ask composer" | `ask-cursor` — no native skill for these |
| "ask codex AND gemini AND cursor's opus 4.7" | All three, in parallel |

**Rule of thumb**: Cursor's GPT and Gemini access is a *secondary* path. Only
use ask-cursor for GPT/Gemini families when the user explicitly said "via
cursor" or invoked `/ask-cursor`. Otherwise `ask-codex` and `ask-gemini` are
the correct choice — they're closer to the providers and cheaper.

## Model Selection — Family → Latest, Highest-Reasoning (no Max)

**When the user gives only a family name inside `/ask-cursor`, always pick the
variant with the latest version AND the highest reasoning effort available —
excluding `-max` tiers.** This is non-negotiable. "Gemini" means the user
wants the best Gemini Cursor offers, not a random tier, and not a low-effort
one.

**Never pick `-max` variants.** The user has opted out of Max Mode entirely.
If the only top-tier option for a family is `-max` (e.g., Opus 4.6 has no
`xhigh`), fall back to the next rung down (`-high`, with `-thinking` if
available). If the user explicitly asks for "max" by name, confirm the
substitution in one line ("You've disabled Max Mode for /ask-cursor; using
`<non-max alternative>` instead") and proceed without max.

### Selection algorithm

Apply in this order:

1. **Latest version** — 4.7 > 4.6 > 4.5 for Claude, 5.4 > 5.3 > 5.2 for GPT, etc.
2. **Top non-max effort tier at that version** — `xhigh` > `high` > `medium` > `low`.
   Skip any `-max` variant. (Not every family has every tier. Sonnet 4.6
   currently tops out at `medium`; Codex tops out at `xhigh`. Use the highest
   non-max tier that actually exists.)
3. **Prefer the `-thinking` variant** at that tier when one exists — thinking
   gives more reasoning depth, which is what the user asked for.
4. **Non-`-fast` over `-fast`** — `-fast` trades quality for speed.

### Family mapping

Apply this first; only deviate if the user names a specific tier or flag
explicitly (e.g., "opus 4.7 low thinking", "gpt-5.4 mini", "composer fast"):

| User says (short) | Pick this model | Rationale |
|---|---|---|
| "opus", "claude", "opus 4.7" | `claude-opus-4-7-thinking-xhigh` | Latest Opus, top non-max tier, Thinking on |
| "opus 4.7" (explicitly no thinking) | `claude-opus-4-7-xhigh` | Top non-max tier without thinking overlay |
| "opus 4.6" | `claude-4.6-opus-high-thinking` | Previous-gen flagship; 4.6 has no xhigh, so `-high` is the top non-max tier |
| "gpt", "gpt-5", "gpt-5.4" | `gpt-5.4-xhigh` | Top tier available; GPT-5.4 has no separate thinking flag |
| "codex" (via /ask-cursor) | `gpt-5.4-xhigh` | **"codex" is the user's shorthand for "most advanced GPT for code" — not literally the Codex-branded models.** Prefer the latest GPT top tier (currently `gpt-5.4-xhigh`) over older Codex-branded variants. If/when a newer Codex variant appears *at a higher version than the latest plain GPT*, prefer the Codex variant. See "Codex selection rule" below. |
| "gemini", "gemini pro" | `gemini-3.1-pro` | Only flagship Gemini on Cursor |
| "grok", "grok 4", "grok 4.3" | `grok-4.3` | Latest Grok on Cursor (4.3 1M); no separate thinking variant currently |
| "sonnet" | `claude-4.6-sonnet-medium-thinking` | Latest Sonnet, top available tier, Thinking on |
| "composer", "composer 2", "composer 2.5" | `composer-2.5` | Latest full Composer 2.5 (not `-fast`, which is the lighter default) |
| "kimi" | `kimi-k2.5` | Only Kimi currently |

Max Mode is disabled for /ask-cursor. If the user says "max" explicitly (e.g.,
"opus max"), treat it as a request for the top-quality non-max variant in that
family and flag the substitution in one line.

### Codex selection rule

"Codex" in this project's vocabulary means **"the most advanced GPT-family
reasoning model currently available on Cursor,"** not literally the
`*-codex-*` CLI IDs. OpenAI's Codex branding lags behind their flagship GPT
releases — e.g. at the time of writing the newest `*-codex-*` is
`gpt-5.3-codex-xhigh` (Codex 5.3), but the newest plain GPT is
`gpt-5.4-xhigh` (GPT-5.4 1M Extra High). The latter is newer and more
capable, and is what the user wants when they say "ask codex".

When the user says "codex" (including phrasings like "ask codex via cursor",
"codex 5.4", "codex 5.3 xhigh", etc.), resolve as follows:

1. Find the newest GPT **major.minor** version available (scan `agent
   models` for the highest `gpt-X.Y` prefix).
2. If a `gpt-X.Y-codex-*` variant exists at that version, prefer it at the
   top tier (`-xhigh` > `-high` > `-medium`).
3. Otherwise, fall back to the plain `gpt-X.Y-<top-tier>` (currently
   `gpt-5.4-xhigh`).
4. Only drop to an older Codex-branded variant (e.g. `gpt-5.3-codex-xhigh`)
   if the user *explicitly* pins the version (e.g. "codex 5.3",
   "gpt-5.3-codex"). Otherwise newest GPT wins, even if it doesn't carry
   the "Codex" label.

If the user names a Codex version that doesn't exist (e.g. "codex 5.4" when
no 5.4 Codex variant has shipped), use the newest plain GPT at the same
version (`gpt-5.4-xhigh`) and flag the substitution to the user in one
line ("Heads up: Cursor doesn't have Codex 5.4 yet; using GPT-5.4 1M
Extra High instead").

### Keeping the list current

Cursor's catalog changes frequently — new models appear, old tiers get
deprecated. If the user names a model you don't recognize, or the mapping
above feels stale, fetch the live list and re-run the selection algorithm
(latest version → top non-max tier → thinking variant):

```bash
agent models 2>&1 | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g' | grep -v -- '-max'
```

Each line is `<cli-id> - <display name>`. Scan for the family the user named,
then apply the four-step ordering above. **Ignore `-max` variants entirely.**
If a new non-max tier appears above `xhigh` (e.g. `ultra`), upgrade the
mapping for this conversation.

**Default when no model is specified at all**: `claude-opus-4-7-thinking-xhigh`
(latest Opus, top non-max tier, Thinking on — highest non-max reasoning
Cursor offers).

## Running the CLI

Always use the bundled wrapper at `scripts/ask.sh` (relative to this skill's
directory). The wrapper enforces:

- `-p --output-format json` — headless, JSON out (so we capture `session_id`)
- `--trust` — skip the workspace-trust prompt
- `--yolo --approve-mcps` — **auto-approve all tool calls** (web search,
  shell, file ops, MCP servers). Without this, the agent silently has tools
  rejected and falls back to training-data answers. For an unattended "ask a
  model" workflow this is the right default; don't weaken it.
- `-m <model>` is required, so nothing ever silently falls through to the
  Cursor CLI default (`composer-2-fast`).

Never call `agent` directly — the wrapper exists to prevent misconfiguration.

### Basic query (no codebase access)

```bash
~/.claude/skills/ask-cursor/scripts/ask.sh -m <model-id> "your prompt here"
```

### With codebase access

Pass the project directory as a trailing positional argument:

```bash
~/.claude/skills/ask-cursor/scripts/ask.sh -m claude-opus-4-7-thinking-xhigh \
  "review the auth middleware for security issues" /path/to/project
```

### Long or multi-line prompts

Write the prompt to a unique temp file and pipe it in with `-`. Use `$$`
(shell PID) plus `$RANDOM` for uniqueness — never `mktemp XXXXXX`, because
stale `XXXXXX` files from prior runs can make it fail with "File exists":

```bash
CURSOR_IN="/tmp/cursor-prompt-${$}-${RANDOM}.txt"
# ... write prompt to $CURSOR_IN ...
cat "$CURSOR_IN" | ~/.claude/skills/ask-cursor/scripts/ask.sh \
  -m gpt-5.4-xhigh - /path/to/project
```

### Capturing long responses to a file

```bash
CURSOR_OUT="/tmp/cursor-response-${$}-${RANDOM}.txt"
~/.claude/skills/ask-cursor/scripts/ask.sh -m claude-opus-4-7-thinking-xhigh \
  "your prompt" /path/to/project > "$CURSOR_OUT"
```

Then read `$CURSOR_OUT` with the Read tool.

## Session Continuation (important)

Every call automatically captures the chat's `session_id` into a **per-model**
file at `/tmp/ask-cursor-last-session-<sanitized-model>.txt`. Follow-up calls
can resume the model's own thread with `-r`, which is critical for parallel
panels where each model gets a distinct chat.

### Resume this model's last session

```bash
~/.claude/skills/ask-cursor/scripts/ask.sh -m claude-opus-4-7-thinking-xhigh \
  -r "dig deeper into the migration-safety point you raised"
```

### Resume a specific chat by ID

If you ran `agent ls` and grabbed a chat ID, pass it explicitly:

```bash
~/.claude/skills/ask-cursor/scripts/ask.sh -m claude-opus-4-7-thinking-xhigh \
  --resume <chatId> "follow-up prompt"
```

### `--continue` (globally most-recent) — use with care

`agent --continue` picks the globally most-recent chat regardless of model.
In a parallel panel, "most-recent" would be whichever model finished last.
Prefer `-r` for panels so each model resumes its own thread.

```bash
# Only safe when there's been a single recent call:
~/.claude/skills/ask-cursor/scripts/ask.sh -m gpt-5.4-xhigh \
  --continue "follow-up"
```

### When to resume vs start fresh

- **Resume (`-r`)** when drilling deeper into the same topic, or when the
  context is large and re-sending it would be slow/expensive.
- **Start fresh** when the topic is unrelated, or when the earlier call was
  long enough ago that the chat's context has gone stale.
- **Unsure**: resume is usually the better default when there was a recent
  same-topic call to this model.

## Parallel Panels

When the user asks for multiple takes at once ("a few perspectives", "compare
opus 4.7 and grok", "get codex, gemini, and opus 4.7"), **issue all Bash calls
in the same message as separate tool blocks** — they run in parallel.

### All via ask-cursor

```bash
# One tool-call block, three Bash invocations — sent in parallel.
~/.claude/skills/ask-cursor/scripts/ask.sh -m claude-opus-4-7-thinking-xhigh "..."
~/.claude/skills/ask-cursor/scripts/ask.sh -m gpt-5.4-xhigh "..."
~/.claude/skills/ask-cursor/scripts/ask.sh -m grok-4.3 "..."
```

### Mixed with native ask-codex / ask-gemini

Fire all the Bash calls in one message — each skill's wrapper runs independently:

```bash
# ask-codex (native, goes through Codex CLI)
CODEX_OUT="/tmp/codex-response-${$}-${RANDOM}.txt" && \
  codex exec -s read-only -o "$CODEX_OUT" "<prompt>" && cat "$CODEX_OUT"

# ask-gemini (native, goes through Gemini CLI)
~/.claude/skills/ask-gemini/scripts/ask.sh "<prompt>"

# ask-cursor (Opus 4.7 via Cursor — no native option)
~/.claude/skills/ask-cursor/scripts/ask.sh -m claude-opus-4-7-thinking-xhigh "<prompt>"
```

### Resuming a panel

Because sessions are per-model-per-skill, follow-up parallels work the same
way — just add `-r` (or the native skill's resume flag) to each call:

```bash
~/.claude/skills/ask-cursor/scripts/ask.sh -m claude-opus-4-7-thinking-xhigh -r "<follow-up>"
~/.claude/skills/ask-cursor/scripts/ask.sh -m gpt-5.4-xhigh                  -r "<follow-up>"
~/.claude/skills/ask-cursor/scripts/ask.sh -m grok-4.3             -r "<follow-up>"
```

Don't use `--continue` in a panel — it would route every wrapper call to the
same (most-recent) chat and cross-contaminate responses.

## Crafting the Prompt

For fresh sessions the prompt must be **self-contained** — the agent has no
knowledge of the current Claude Code conversation. For resumed sessions you
can reference prior context without re-sending it. Include:

- **The question or task** — what specifically you want evaluated
- **Relevant context** — code snippets, file paths, architectural decisions,
  constraints (inline from the current conversation if needed)
- **What kind of response you want** — "review this plan", "find flaws",
  "suggest alternatives", "write the implementation"

If the files are in the project directory and you want the agent to read them
directly, pass the project dir as the trailing argument.

### Prompt template (reviews & opinions)

```
You are being consulted for a second opinion on a technical matter.

Context:
<relevant background, code, or plan>

Question:
<what the user wants to know>

Please provide your analysis, highlighting:
- Strengths of the current approach
- Potential issues or risks
- Alternative approaches worth considering
- Your recommendation
```

Adapt this to the situation — a simple factual question doesn't need the full
framework.

## Presenting the Response

After the wrapper returns:

1. Present the reply clearly, attributed **with both model name and "via Cursor"**
   — e.g., **"Opus 4.7 Thinking Extra High (via Cursor):"** or **"Grok 4.3 1M (via Cursor):"**.
   The "via Cursor" distinction matters when the same family is also reachable
   through a native skill.
2. If the user asked for a second opinion, offer your own take — where you
   agree, disagree, or see nuance the model missed.
3. For panels: call out agreements (strong signal) and lay out disagreements
   without forcing a verdict unless asked.

## Auth & Setup

Auth is picked up from the installed Cursor app (`~/.cursor`). No API key is
needed for normal use — the agent uses the user's Cursor subscription. If
`agent` returns an auth error, tell the user to run `agent status` or to log
in via the Cursor app.

For CI contexts, set `CURSOR_API_KEY` in the environment; `agent` picks it up
automatically.

## Timeout

Queries typically take 20–90 seconds; reasoning/thinking variants (`-xhigh`,
`-thinking-*`) can run 2–4 minutes. Use a **300-second (5-minute)
timeout** on the Bash call. If it times out, tell the user and suggest a
faster tier (e.g., `-medium` instead of `-xhigh`) or a shorter prompt.
