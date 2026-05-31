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

MODEL="claude-opus-4-8"
TOOL="claude"
RUN_ROOT="${ASK_RUN_ROOT:-$HOME/.cache/ask-runs}/$TOOL"
mkdir -p "$RUN_ROOT"

# ----------------------------- helpers --------------------------------------

now_iso() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
now_epoch() { date -u +"%s"; }
new_run_id() { printf '%s-%s' "$(date -u +%Y%m%d-%H%M%S)" "$(uuidgen | tr 'A-Z' 'a-z' | cut -c1-6)"; }

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
  local dir="$1" key="$2" val="$3"
  local meta="$dir/meta.json"
  if [[ ! -f "$meta" ]]; then echo '{}' > "$meta"; fi
  local tmp="$meta.tmp"
  jq --arg k "$key" --arg v "$val" '.[$k]=$v' "$meta" > "$tmp" && mv "$tmp" "$meta"
}

write_meta_num() {
  local dir="$1" key="$2" val="$3"
  local meta="$dir/meta.json"
  if [[ ! -f "$meta" ]]; then echo '{}' > "$meta"; fi
  local tmp="$meta.tmp"
  jq --arg k "$key" --argjson v "$val" '.[$k]=$v' "$meta" > "$tmp" && mv "$tmp" "$meta"
}

# Mark a run terminal: finalize meta.json with status, exit_code, ended_at,
# and extract the session_id + final response text from events.jsonl.
finalize_run() {
  local dir="$1"
  local events="$dir/events.jsonl"
  local final="$dir/final.txt"
  local exit_code
  exit_code=$(cat "$dir/exit_code" 2>/dev/null || echo "")

  local sid=""
  if [[ -f "$events" ]]; then
    sid=$(jq -r 'select(.session_id) | .session_id' "$events" 2>/dev/null | head -n1 || true)
  fi
  [[ -n "$sid" ]] && write_meta "$dir" session_id "$sid"

  if [[ -f "$events" && ! -s "$final" ]]; then
    local res
    res=$(jq -r 'select(.type=="result") | .result // empty' "$events" 2>/dev/null | tail -n1 || true)
    if [[ -n "$res" ]]; then
      printf '%s\n' "$res" > "$final"
    else
      jq -r 'select(.type=="stream_event" and .event.type=="content_block_delta" and .event.delta.type=="text_delta") | .event.delta.text' "$events" 2>/dev/null \
        | tr -d '\000' > "$final" || true
    fi
  fi

  local is_error="false"
  if [[ -f "$events" ]]; then
    local result_line
    result_line=$(jq -c 'select(.type=="result")' "$events" 2>/dev/null | tail -n1 || true)
    if [[ -n "$result_line" ]]; then
      # Flatten to a uniform set of fields. Claude uses total_cost_usd and
      # nests tokens under .usage.{input,output}_tokens; we surface both.
      local pairs
      pairs=$(printf '%s' "$result_line" | jq -r '
        {
          subtype: .subtype,
          duration_ms: .duration_ms,
          duration_api_ms: .duration_api_ms,
          num_turns: .num_turns,
          stop_reason: .stop_reason,
          cost_usd: (.cost_usd // .total_cost_usd),
          input_tokens: (.input_tokens // .usage.input_tokens),
          output_tokens: (.output_tokens // .usage.output_tokens),
          cache_read_input_tokens: .usage.cache_read_input_tokens,
          cache_creation_input_tokens: .usage.cache_creation_input_tokens,
          terminal_reason: .terminal_reason
        }
        | to_entries[]
        | select(.value != null and .value != "")
        | "\(.key)\t\(.value | tostring)"
      ' 2>/dev/null)
      while IFS=$'\t' read -r k v; do
        [[ -z "$k" ]] && continue
        if [[ "$v" =~ ^-?[0-9]+(\.[0-9]+)?$ ]]; then
          write_meta_num "$dir" "$k" "$v"
        else
          write_meta "$dir" "$k" "$v"
        fi
      done <<< "$pairs"
      # is_error means the model returned an error result (auth, max-turns, budget, etc.)
      is_error=$(printf '%s' "$result_line" | jq -r '(.is_error // false) | tostring' 2>/dev/null)
    fi
  fi

  write_meta "$dir" ended_at "$(now_iso)"
  if [[ -n "$exit_code" ]]; then
    write_meta_num "$dir" exit_code "$exit_code"
  fi
  if [[ "$is_error" == "true" || ( -n "$exit_code" && "$exit_code" != "0" ) ]]; then
    write_meta "$dir" status "failed"
  else
    write_meta "$dir" status "done"
  fi
}

print_status() {
  local id="$1" dir="$2"
  local meta="$dir/meta.json" events="$dir/events.jsonl"
  local status pid sid started ended
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
      mtime=$(stat -f %m "$events" 2>/dev/null || stat -c %Y "$events" 2>/dev/null || echo "")
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
  --model <name>              Override model (default: claude-opus-4-8)

Legacy positional invocation (no subcommand) is treated as `ask <args>`.
EOF
}

cmd_start() {
  local mode="new" resume_target="" session_id="" fork="false" bare="false"
  local model="$MODEL"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --continue|-c) mode="continue"; shift;;
      --resume|-r) mode="resume"; resume_target="${2:?--resume needs id}"; shift 2;;
      --session-id) session_id="${2:?--session-id needs uuid}"; shift 2;;
      --fork-session) fork="true"; shift;;
      --bare) bare="true"; shift;;
      --model) model="${2:?--model needs name}"; shift 2;;
      --) shift; break;;
      *) break;;
    esac
  done

  if [[ $# -lt 1 ]]; then echo "Error: prompt required" >&2; usage >&2; exit 1; fi
  local prompt_arg="$1"; shift
  local project_dir="${1:-}"

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

  (
    if [[ -n "$cwd_arg" ]]; then cd "$cwd_arg"; fi
    "${cmd[@]}" < "$dir/prompt.txt" > "$dir/events.jsonl" 2> "$dir/stderr.log"
    echo $? > "$dir/exit_code"
  ) &
  local pid=$!
  disown $pid 2>/dev/null || true
  write_meta_num "$dir" pid "$pid"

  (
    while kill -0 "$pid" 2>/dev/null; do sleep 1; done
    finalize_run "$dir"
  ) >/dev/null 2>&1 &
  disown $! 2>/dev/null || true

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

  while [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; do
    if [[ "$timeout" -gt 0 && $(($(now_epoch)-start_ts)) -ge "$timeout" ]]; then
      echo "Timeout after ${timeout}s waiting for run $id" >&2
      return 124
    fi
    sleep 1
  done
  [[ ! -s "$dir/final.txt" ]] && finalize_run "$dir" || true
  if [[ -s "$dir/final.txt" ]]; then
    cat "$dir/final.txt"
  else
    echo "(no final response captured; check $dir/stderr.log)" >&2
    return 1
  fi
}

cmd_result() {
  local id_in="${1:?Usage: result <run-id|latest>}"
  local id; id="$(resolve_run "$id_in")" || exit 1
  local dir; dir="$(run_dir "$id")"
  local status; status=$(jq -r '.status // "unknown"' "$dir/meta.json")
  if [[ "$status" == "running" ]]; then
    echo "Run $id is still running. Use 'wait' or 'status'." >&2
    exit 2
  fi
  if [[ -s "$dir/final.txt" ]]; then cat "$dir/final.txt"; else echo "(empty)"; fi
}

cmd_cancel() {
  local id_in="${1:?Usage: cancel <run-id|latest>}"
  local id; id="$(resolve_run "$id_in")" || exit 1
  local dir; dir="$(run_dir "$id")"
  local pid; pid=$(jq -r '.pid // empty' "$dir/meta.json")
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    kill -9 "$pid" 2>/dev/null || true
    write_meta "$dir" status "cancelled"
    write_meta "$dir" ended_at "$(now_iso)"
    echo "Cancelled $id (pid $pid)"
  else
    echo "Run $id is not running."
  fi
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
