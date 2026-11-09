#!/usr/bin/env bash
# ask-claude: orchestrator-friendly wrapper around `claude --print`.
#
# Designed to be driven by a parent Claude Code session as a thinking partner:
# the parent can start a child run in the background, watch JSONL events live
# (liveness signal), then collect the final response when ready.
#
# Subcommands:
#   start    Spawn a background run, print RUN_ID and run dir, exit fast.
#   status   Print human-readable liveness summary.
#   tail     Print last N events as readable summaries.
#   events   Print absolute path to the JSONL event stream.
#   wait     Block until the run finishes, then print final response.
#   result   Print final response (errors if run is not done).
#   cancel   Kill the child process for a run.
#   list     List recent runs and their status.
#   ask      Convenience: start + wait + print result. Used by default for
#            positional invocations to preserve the legacy interface.
#
# Run state lives at: ~/.cache/ask-runs/claude/<run-id>/
#   prompt.txt    cmd.txt    events.jsonl    stderr.log    final.txt    meta.json

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIFECYCLE="${ASK_CLAUDE_HELPER:-$SCRIPT_DIR/lifecycle.py}"
MODEL="claude-opus-5-5"
TOOL="claude"
RUN_ROOT="${ASK_RUN_ROOT:-$HOME/.cache/ask-runs}/$TOOL"
mkdir -p "$RUN_ROOT"

# ----------------------------- helpers --------------------------------------

now_iso() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
now_epoch() { date -u +"%s"; }
new_run_id() { printf '%s-%s' "$(date -u +%Y%m%d-%H%M%S)" "$(uuidgen | tr 'A-Z' 'a-z' | cut -c1-6)"; }

normalize_model() {
  local requested lower
  requested="$1"
  lower=$(printf '%s' "$requested" | tr '[:upper:]' '[:lower:]')
  case "$lower" in
    fable|fable-5.2|fable-5-2) printf '%s' "claude-fable-5-2";;
    fable-5.1|fable-5-1) printf '%s' "claude-fable-5-1";;
    opus|opus-5.5|opus-5-5) printf '%s' "claude-opus-5-5";;
    sonnet|sonnet-5.5|sonnet-5-5) printf '%s' "claude-sonnet-5-5";;
    opus-5) printf '%s' "claude-opus-5";;
    *) printf '%s' "$requested";;
  esac
}

run_dir() { printf '%s/%s' "$RUN_ROOT" "$1"; }

# Resolve a possibly-partial run id. Accepts the literal "latest" too.
resolve_run() {
  local id="$1"
  if [[ "$id" == "latest" ]]; then
    ls -1t "$RUN_ROOT" 2>/dev/null | head -n1
    return
  fi
  if [[ -d "$RUN_ROOT/$id" ]]; then
    printf '%s' "$id"
    return
  fi
  local match
  match=$(ls -1 "$RUN_ROOT" 2>/dev/null | grep -E "^${id}" | head -n1 || true)
  if [[ -n "$match" ]]; then
    printf '%s' "$match"
    return
  fi
  echo "Error: no run matching '$id' under $RUN_ROOT" >&2
  return 1
}

write_meta() {
  update_meta "$1" "$2" "$3" string
}

write_meta_num() {
  update_meta "$1" "$2" "$3" number
}

update_meta() {
  # The watcher, wait, and status commands can finalize the same run together.
  # Lock the read/modify/write, not just rename: unique temporary names alone
  # still lose fields when two writers read the same old metadata.
  python3 - "$1" "$2" "$3" "$4" <<'PY'
import fcntl, json, os, pathlib, sys, tempfile
directory, key, value, kind = sys.argv[1:]
path = pathlib.Path(directory) / "meta.json"
with (path.parent / ".metadata.lock").open("a") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    data = json.loads(path.read_text()) if path.exists() else {}
    data[key] = json.loads(value) if kind == "number" else value
    fd, temporary = tempfile.mkstemp(prefix=".metadata-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(data, output, indent=2)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
PY
}

# Mark a run terminal: finalize meta.json with status, exit_code, ended_at,
# and extract the session_id + final response text from events.jsonl.
finalize_run() {
  python3 "$LIFECYCLE" finalize "$1"
}

refresh_run() {
  local dir="$1" pid status
  status=$(jq -r '.status' "$dir/meta.json")
  pid=$(jq -r '.pid // empty' "$dir/meta.json")
  if [[ "$status" == "running" ]] && { [[ -f "$dir/supervisor.done" ]] || { [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; }; }; then
    finalize_run "$dir"
  fi
}

emit_result() {
  local dir="$1" status code
  refresh_run "$dir"
  status=$(jq -r '.status' "$dir/meta.json")
  if [[ "$status" == "running" ]]; then
    echo "Run is still running. Use wait or status." >&2
    return 2
  fi
  [[ ! -s "$dir/final.txt" ]] || cat "$dir/final.txt"
  case "$status" in
    done) return 0;;
    cancelled) return 130;;
    *) code=$(jq -r '.exit_code // 1' "$dir/meta.json")
       [[ "$code" -gt 0 && "$code" -lt 256 ]] || code=1
       echo "Run failed; check $dir/stderr.log and meta.json" >&2
       return "$code";;
  esac
}

print_status() {
  local id="$1" dir="$2"
  local meta="$dir/meta.json" events="$dir/events.jsonl"
  local status pid sid started ended
  refresh_run "$dir"
  status=$(jq -r '.status // "unknown"' "$meta" 2>/dev/null)
  pid=$(jq -r '.pid // empty' "$meta" 2>/dev/null)
  sid=$(jq -r '.session_id // empty' "$meta" 2>/dev/null)
  started=$(jq -r '.started_at // empty' "$meta" 2>/dev/null)
  ended=$(jq -r '.ended_at // empty' "$meta" 2>/dev/null)

  if [[ "$status" == "running" && -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
    finalize_run "$dir"
    status=$(jq -r '.status' "$meta" 2>/dev/null)
    ended=$(jq -r '.ended_at // empty' "$meta" 2>/dev/null)
  fi

  local n_events=0 last_event_age=""
  if [[ -f "$events" ]]; then
    n_events=$(wc -l < "$events" | tr -d ' ')
    if [[ "$n_events" -gt 0 ]]; then
      local mtime
      # GNU form first: on Linux/WSL, `stat -f` means filesystem status and
      # prints multi-line output that breaks the age arithmetic below.
      mtime=$(stat -c %Y "$events" 2>/dev/null || stat -f %m "$events" 2>/dev/null || echo "")
      if [[ -n "$mtime" ]]; then
        last_event_age=$(( $(now_epoch) - mtime ))
      fi
    fi
  fi

  echo "run_id:      $id"
  echo "tool:        $TOOL"
  echo "status:      $status"
  [[ -n "$pid" ]] && echo "pid:         $pid$(kill -0 "$pid" 2>/dev/null && echo " (alive)" || echo " (gone)")"
  [[ -n "$sid" ]] && echo "session_id:  $sid"
  echo "events:      $n_events  ($events)"
  if [[ -n "$last_event_age" ]]; then
    echo "last_event:  ${last_event_age}s ago"
  fi
  echo "started_at:  $started"
  [[ -n "$ended" ]] && echo "ended_at:    $ended"
  if [[ "$status" == "done" || "$status" == "failed" ]]; then
    local cost dur tokens
    cost=$(jq -r '.cost_usd // empty' "$meta" 2>/dev/null)
    dur=$(jq -r '.duration_ms // empty' "$meta" 2>/dev/null)
    tokens=$(jq -r '"in=\(.input_tokens // 0) out=\(.output_tokens // 0)"' "$meta" 2>/dev/null)
    [[ -n "$cost" ]] && echo "cost_usd:    $cost"
    [[ -n "$dur"  ]] && echo "duration_ms: $dur"
    [[ -n "$tokens" ]] && echo "tokens:      $tokens"
  fi
  echo "run_dir:     $dir"
}

print_tail() {
  local events="$1" n="$2"
  if [[ ! -f "$events" ]]; then echo "(no events yet)"; return; fi
  tail -n "$n" "$events" | while IFS= read -r line; do
    printf '%s' "$line" | jq -r '
      . as $e
      | (.type // "?") as $t
      | if $t=="system" then "[system] \(.subtype // "?")"
        elif $t=="stream_event" then
          (.event.type // "?") as $st
          | if $st=="content_block_delta" then
              ((.event.delta.text // .event.delta.partial_json // "") | tostring | .[0:80] | gsub("\n"; "\\n")) as $snip
              | "[delta] " + $snip
            elif $st=="content_block_start" then "[block_start] " + (.event.content_block.type // "?")
            elif $st=="message_start" then "[message_start]"
            elif $st=="message_delta" then "[message_delta] stop=" + (.event.delta.stop_reason // "")
            elif $st=="message_stop" then "[message_stop]"
            else "[" + $st + "]" end
        elif $t=="assistant" then
          ((.message.content // []) | map(.type // "?") | join(",")) as $c
          | "[assistant] content=" + $c
        elif $t=="tool_use" then "[tool_use] " + (.name // "?")
        elif $t=="tool_result" then "[tool_result] id=" + (.tool_use_id // "?")
        elif $t=="result" then "[result] " + (.subtype // "") + " cost=" + ((.cost_usd // 0) | tostring) + " dur=" + ((.duration_ms // 0) | tostring) + "ms"
        else "[" + $t + "]" end
    ' 2>/dev/null || printf '%s\n' "$line"
  done
}

# ----------------------------- subcommands ----------------------------------

usage() {
  cat <<'EOF'
ask-claude — orchestrator-friendly wrapper around `claude --print`.

Subcommands:
  start [opts] "prompt" [project-dir]
  start [opts] - [project-dir]              # prompt from stdin
  status <run-id|latest>
  tail   <run-id|latest> [-n 20]
  events <run-id|latest>                    # prints JSONL path
  wait   <run-id|latest> [--timeout SEC]
  result <run-id|latest>
  cancel <run-id|latest>
  list   [-n 10]
  ask    [opts] "prompt" [project-dir]      # blocking convenience: start + wait

Start/ask options (claude-specific):
  --continue                  Continue the most recent claude conversation in cwd
  --resume <session-id>       Resume a specific claude session
  --session-id <uuid>         Pin to an explicit session UUID
  --fork-session              Branch from --resume into a new session id
  --bare                      Pass --bare to claude (skip hooks/CLAUDE.md/skills) for a clean partner
  --model <name>              Override model (default: claude-opus-5-5)
                              Aliases: sonnet -> claude-sonnet-5-5,
                                       fable -> claude-fable-5-2,
                                       opus  -> claude-opus-5-5

Safe CLI controls (passed as individual arguments):
  --safe-mode --restricted --strict-mcp-config --disable-slash-commands
  --no-session-persistence --no-chrome
  --tools VALUE --allowedTools VALUE --disallowedTools VALUE
  --permission-mode VALUE --permission-prompts VALUE --max-budget-usd VALUE
  --effort VALUE --system-prompt VALUE --setting-sources VALUE --mcp-config VALUE
Permission bypass and unknown options are rejected. Use -- before option-like prompts.

Legacy positional invocation (no subcommand) is treated as `ask <args>`.
EOF
}

cmd_start() {
  local mode="new" resume_target="" session_id="" fork="false" bare="false"
  local model="$MODEL"
  local -a controls=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --continue|-c) mode="continue"; shift;;
      --resume|-r) mode="resume"; resume_target="${2:?--resume needs id}"; shift 2;;
      --session-id) session_id="${2:?--session-id needs uuid}"; shift 2;;
      --fork-session) fork="true"; shift;;
      --bare) bare="true"; shift;;
      --safe-mode|--restricted|--strict-mcp-config|--disable-slash-commands|--no-session-persistence|--no-chrome)
        controls+=("$1"); shift;;
      --tools|--allowedTools|--disallowedTools|--permission-mode|--permission-prompts|--max-budget-usd|--effort|--system-prompt|--setting-sources|--mcp-config)
        [[ $# -ge 2 ]] || { echo "Error: $1 needs a value" >&2; return 2; }
        if [[ "$1" == "--permission-mode" && "$2" == "bypassPermissions" ]]; then
          echo "Error: permission bypass is not supported" >&2; return 2
        fi
        controls+=("$1" "$2"); shift 2;;
      --model) model="${2:?--model needs name}"; shift 2;;
      --) shift; break;;
      --*) echo "Error: unsupported option $1" >&2; return 2;;
      *) break;;
    esac
  done

  model="$(normalize_model "$model")"

  if [[ $# -lt 1 ]]; then echo "Error: prompt required" >&2; usage >&2; exit 1; fi
  local prompt_arg="$1"; shift
  local project_dir="${1:-}"
  [[ $# -le 1 ]] || { echo "Error: unexpected extra arguments" >&2; return 2; }
  [[ -z "$project_dir" || -d "$project_dir" ]] || { echo "Error: project directory does not exist" >&2; return 2; }

  local prompt
  if [[ "$prompt_arg" == "-" ]]; then
    prompt="$(cat)"
  else
    prompt="$prompt_arg"
  fi
  if [[ -z "${prompt// }" ]]; then echo "Error: prompt is empty" >&2; exit 1; fi

  local run_id; run_id="$(new_run_id)"
  local dir; dir="$(run_dir "$run_id")"
  mkdir -p "$dir"
  printf '%s' "$prompt" > "$dir/prompt.txt"

  local -a cmd=(claude --print --model "$model" --output-format stream-json --verbose --include-partial-messages)
  [[ "$bare" == "true" ]] && cmd+=(--bare)
  if [[ ${#controls[@]} -gt 0 ]]; then cmd+=("${controls[@]}"); fi
  case "$mode" in
    continue) cmd+=(--continue);;
    resume)   cmd+=(--resume "$resume_target");;
  esac
  [[ -n "$session_id" ]] && cmd+=(--session-id "$session_id")
  [[ "$fork" == "true" ]] && cmd+=(--fork-session)

  printf '%q ' "${cmd[@]}" > "$dir/cmd.txt"
  echo >> "$dir/cmd.txt"

  jq -n \
    --arg tool "$TOOL" --arg model "$model" --arg started "$(now_iso)" \
    --arg pdir "$project_dir" --arg mode "$mode" --arg bare "$bare" \
    '{tool:$tool, model:$model, status:"running", started_at:$started, project_dir:$pdir, mode:$mode, bare:$bare}' \
    > "$dir/meta.json"

  local cwd_arg=""
  [[ -n "$project_dir" ]] && cwd_arg="$project_dir"

  python3 "$LIFECYCLE" supervise "$dir" "$cwd_arg" "${cmd[@]}" </dev/null >/dev/null 2>"$dir/supervisor.log" &
  local pid=$!
  disown "$pid" 2>/dev/null || true
  # The supervisor publishes its pid before ready. Do not race its metadata.
  local attempt=0
  while [[ ! -f "$dir/ready" && ! -f "$dir/supervisor.done" ]]; do
    if ! kill -0 "$pid" 2>/dev/null || [[ "$attempt" -ge 100 ]]; then
      echo "Error: supervisor did not become ready; inspect $dir" >&2
      return 1
    fi
    sleep 0.05
    attempt=$((attempt + 1))
  done

  echo "RUN_ID=$run_id"
  echo "RUN_DIR=$dir"
  echo "EVENTS=$dir/events.jsonl"
  echo "TIP: tail with: ask-claude tail $run_id   |   block until done: ask-claude wait $run_id"
}

cmd_status() {
  local id_in="${1:?Usage: status <run-id|latest>}"
  local id; id="$(resolve_run "$id_in")" || exit 1
  print_status "$id" "$(run_dir "$id")"
}

cmd_tail() {
  local id_in="${1:?Usage: tail <run-id|latest> [-n N]}"; shift
  local n=20
  if [[ "${1:-}" == "-n" ]]; then n="$2"; shift 2; fi
  local id; id="$(resolve_run "$id_in")" || exit 1
  print_tail "$(run_dir "$id")/events.jsonl" "$n"
}

cmd_events() {
  local id_in="${1:?Usage: events <run-id|latest>}"
  local id; id="$(resolve_run "$id_in")" || exit 1
  printf '%s\n' "$(run_dir "$id")/events.jsonl"
}

cmd_wait() {
  local id_in="${1:?Usage: wait <run-id|latest> [--timeout SEC]}"; shift
  local timeout=0
  if [[ "${1:-}" == "--timeout" ]]; then timeout="$2"; shift 2; fi
  local id; id="$(resolve_run "$id_in")" || exit 1
  local dir; dir="$(run_dir "$id")"
  local pid; pid=$(jq -r '.pid // empty' "$dir/meta.json")
  local start_ts; start_ts=$(now_epoch)

  [[ "$timeout" =~ ^[0-9]+$ ]] || { echo "Error: timeout must be nonnegative seconds" >&2; return 2; }
  while true; do
    refresh_run "$dir"
    [[ "$(jq -r '.status' "$dir/meta.json")" == "running" ]] || break
    if [[ "$timeout" -gt 0 && $(($(now_epoch)-start_ts)) -ge "$timeout" ]]; then
      echo "Timeout after ${timeout}s waiting for run $id" >&2
      return 124
    fi
    sleep 0.1
  done
  emit_result "$dir"
}

cmd_result() {
  local id_in="${1:?Usage: result <run-id|latest>}"
  local id; id="$(resolve_run "$id_in")" || exit 1
  local dir; dir="$(run_dir "$id")"
  emit_result "$dir"
}

cmd_cancel() {
  local id_in="${1:?Usage: cancel <run-id|latest>}"
  local id; id="$(resolve_run "$id_in")" || exit 1
  local dir; dir="$(run_dir "$id")"
  refresh_run "$dir"
  if [[ "$(jq -r '.status' "$dir/meta.json")" != "running" ]]; then
    echo "Run $id is not running."
    return 0
  fi
  # A request to the run's supervisor avoids signalling a stale/reused pid.
  touch "$dir/cancel.request"
  local attempt=0
  while [[ ! -f "$dir/supervisor.done" && "$attempt" -lt 100 ]]; do
    sleep 0.05
    attempt=$((attempt + 1))
  done
  if [[ ! -f "$dir/supervisor.done" ]]; then
    echo "Cancellation requested but not confirmed for $id" >&2
    return 1
  fi
  finalize_run "$dir"
  echo "Cancelled $id"

}

cmd_list() {
  local n=10
  if [[ "${1:-}" == "-n" ]]; then n="$2"; shift 2; fi
  ls -1t "$RUN_ROOT" 2>/dev/null | head -n "$n" | while read -r id; do
    local dir="$RUN_ROOT/$id"
    local status started
    status=$(jq -r '.status // "?"' "$dir/meta.json" 2>/dev/null)
    started=$(jq -r '.started_at // "?"' "$dir/meta.json" 2>/dev/null)
    printf '%-32s  %-10s  %s\n' "$id" "$status" "$started"
  done
}

cmd_ask() {
  local out
  out="$(cmd_start "$@")"
  echo "$out" >&2
  local rid
  rid=$(printf '%s\n' "$out" | awk -F= '/^RUN_ID=/{print $2; exit}')
  cmd_wait "$rid"
}

# ----------------------------- dispatch -------------------------------------

if [[ $# -eq 0 ]]; then usage; exit 0; fi

case "$1" in
  start)   shift; cmd_start "$@";;
  status)  shift; cmd_status "$@";;
  tail)    shift; cmd_tail "$@";;
  events)  shift; cmd_events "$@";;
  wait)    shift; cmd_wait "$@";;
  result)  shift; cmd_result "$@";;
  cancel)  shift; cmd_cancel "$@";;
  list)    shift; cmd_list "$@";;
  ask)     shift; cmd_ask "$@";;
  -h|--help|help) usage;;
  *)       cmd_ask "$@";;
esac
