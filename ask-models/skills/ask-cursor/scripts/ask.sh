#!/usr/bin/env bash
# ask.sh — Wrapper for Cursor's `agent` CLI that enforces headless defaults
# and captures per-model session IDs so follow-ups can resume reliably even
# in parallel-panel scenarios (where several models are running at once).
#
# Usage:
#   ask.sh -m <model> "prompt"                        # Query, saves session id
#   ask.sh -m <model> "prompt" /path/to/project       # With codebase access
#   cat p.txt | ask.sh -m <model> - /path/to/project  # Pipe long prompt
#   ask.sh -m <model> -r "follow-up"                  # Resume THIS model's last session
#   ask.sh -m <model> --resume <chatId> "follow-up"   # Resume a specific chat id
#   ask.sh -m <model> --continue "follow-up"          # Resume most-recent (global)
#
# Why -r exists:
#   `--continue` picks the globally most-recent chat, which is wrong when
#   several models ran in parallel (e.g., opus+grok+gemini). -r reads the
#   session ID we captured for the specific model in the previous call and
#   passes it via `--resume <id>`, so each model's thread stays intact.
#
# Notes:
#   - `-m <model>` is required. Use IDs from `agent models`.
#   - Auth is picked up from the installed Cursor app (~/.cursor). Set
#     CURSOR_API_KEY for CI.
#   - Output is the model's text reply. Session ID is written to a per-model
#     file under /tmp (see SESSION_FILE) — read back by the next -r call.

set -euo pipefail

MODEL=""
RESUME_SAVED=""     # -r: resume the session we previously saved for this model
RESUME_ID=""        # --resume <id>: explicit chat id
CONTINUE_GLOBAL=""  # --continue: globally most-recent (pass-through)

while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--model)
      MODEL="${2:?missing model id after -m}"
      shift 2
      ;;
    -r|--resume-saved)
      RESUME_SAVED="1"
      shift
      ;;
    --resume)
      RESUME_ID="${2:?missing chat id after --resume}"
      shift 2
      ;;
    --continue)
      CONTINUE_GLOBAL="1"
      shift
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

if [[ -z "$MODEL" ]]; then
  echo "ask.sh: -m <model> is required. Run 'agent models' to list options." >&2
  exit 2
fi

PROMPT="${1:?Usage: ask.sh -m <model> [-r|--resume <id>|--continue] <prompt|-> [project-dir]}"
PROJECT_DIR="${2:-}"

# Per-model session file. Sanitize the model id (dots, slashes) for a safe
# filename. All current IDs are already safe, but be defensive.
SAFE_MODEL="${MODEL//\//-}"
SAFE_MODEL="${SAFE_MODEL//./-}"
SESSION_FILE="/tmp/ask-cursor-last-session-${SAFE_MODEL}.txt"

# Run in JSON output mode so we get both the text reply AND the session_id.
# --yolo auto-approves tool calls (web search, shell, file ops) — without it
# the agent can't hit the web or run curl, and silently falls back to
# training-data answers. --approve-mcps covers any configured MCP servers.
# --trust skips the workspace-trust prompt.
AGENT_ARGS=(-p --model "$MODEL" --output-format json --trust --yolo --approve-mcps)

if [[ -n "$PROJECT_DIR" ]]; then
  AGENT_ARGS+=(--workspace "$PROJECT_DIR")
fi

# Session continuation: resolve in priority order.
if [[ -n "$RESUME_SAVED" ]]; then
  if [[ ! -s "$SESSION_FILE" ]]; then
    echo "ask.sh: no saved session for model '$MODEL' at $SESSION_FILE" >&2
    echo "        run a fresh call first (without -r) so the session id can be captured." >&2
    exit 3
  fi
  AGENT_ARGS+=(--resume "$(cat "$SESSION_FILE")")
elif [[ -n "$RESUME_ID" ]]; then
  AGENT_ARGS+=(--resume "$RESUME_ID")
elif [[ -n "$CONTINUE_GLOBAL" ]]; then
  AGENT_ARGS+=(--continue)
fi

# Read prompt from stdin if "-", otherwise use the positional arg.
if [[ "$PROMPT" == "-" ]]; then
  PROMPT="$(cat)"
fi

# Capture JSON response to a unique temp file. $$ + $RANDOM for uniqueness —
# never mktemp XXXXXX, prior runs can leave literal XXXXXX files behind.
JSON_OUT="/tmp/ask-cursor-json-${$}-${RANDOM}.txt"
trap 'rm -f "$JSON_OUT"' EXIT

agent "${AGENT_ARGS[@]}" "$PROMPT" > "$JSON_OUT"

# Extract result + session_id. Fall through to raw output on parse failure
# (e.g., if the CLI printed an auth error instead of JSON).
python3 - "$JSON_OUT" "$SESSION_FILE" <<'PY' || { cat "$JSON_OUT"; exit 1; }
import json, sys
path, session_path = sys.argv[1], sys.argv[2]
with open(path) as f:
    raw = f.read().strip()
# The CLI emits a single JSON object on stdout; if it streamed multiple,
# take the last complete one.
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    # Try to grab the last line as JSON (defensive).
    last = raw.splitlines()[-1] if raw else ""
    data = json.loads(last)
print(data.get("result", "").lstrip("\n").rstrip())
sid = data.get("session_id")
if sid:
    with open(session_path, "w") as f:
        f.write(sid)
PY
