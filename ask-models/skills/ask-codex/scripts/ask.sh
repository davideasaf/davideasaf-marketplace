#!/usr/bin/env bash
# ask-codex: orchestrator-friendly wrapper around `codex exec`.
#
# Designed to be driven by a parent Claude Code session as a thinking partner.
# Spawns the child in the background, captures the JSONL event stream
# (`codex exec --json`) for live introspection, writes the clean final
# response to a separate file (`-o final.txt`), and exposes a uniform
# subcommand surface (start/status/tail/events/wait/result/cancel/list/ask)
# matching ask-claude and ask-gemini.
#
# Run state lives at: ~/.cache/ask-runs/codex/<run-id>/
#   prompt.txt    cmd.txt    events.jsonl    stderr.log    final.txt    meta.json

set -euo pipefail

MODEL="gpt-5.5"
REASONING_EFFORT="high"
SANDBOX="read-only"
TOOL="codex"
RUN_ROOT="${ASK_RUN_ROOT:-$HOME/.cache/ask-runs}/$TOOL"
mkdir -p "$RUN_ROOT"

now_iso() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
now_epoch() { date -u +"%s"; }
new_run_id() { printf '%s-%s' "$(date -u +%Y%m%d-%H%M%S)" "$(uuidgen | tr 'A-Z' 'a-z' | cut -c1-6)"; }
run_dir() { printf '%s/%s' "$RUN_ROOT" "$1"; }

resolve_run() {
  local id="$1"
  if [[ "$id" == "latest" ]]; then ls -1t "$RUN_ROOT" 2>/dev/null | head -n1; return; fi
  if [[ -d "$RUN_ROOT/$id" ]]; then printf '%s' "$id"; return; fi
  local match; match=$(ls -1 "$RUN_ROOT" 2>/dev/null | grep -E "^${id}" | head -n1 || true)
  if [[ -n "$match" ]]; then printf '%s' "$match"; return; fi
  echo "Error: no run matching '$id' under $RUN_ROOT" >&2
  return 1
}

write_meta() {
  local dir="$1" key="$2" val="$3"
  local meta="$dir/meta.json"
  [[ -f "$meta" ]] || echo '{}' > "$meta"
  local tmp="$meta.tmp"
  jq --arg k "$key" --arg v "$val" '.[$k]=$v' "$meta" > "$tmp" && mv "$tmp" "$meta"
}
write_meta_num() {
  local dir="$1" key="$2" val="$3"
  local meta="$dir/meta.json"
  [[ -f "$meta" ]] || echo '{}' > "$meta"
  local tmp="$meta.tmp"
  jq --arg k "$key" --argjson v "$val" '.[$k]=$v' "$meta" > "$tmp" && mv "$tmp" "$meta"
}

finalize_run() {
  local dir="$1"
  local events="$dir/events.jsonl"
  local final="$dir/final.txt"
  local exit_code; exit_code=$(cat "$dir/exit_code" 2>/dev/null || echo "")

  # session_id (codex calls it thread_id) — first thread.started event.
  if [[ -f "$events" ]]; then
    local sid
    sid=$(jq -r 'select(.type=="thread.started") | .thread_id' "$events" 2>/dev/null | head -n1 || true)
    [[ -n "$sid" ]] && write_meta "$dir" session_id "$sid"
  fi

  # final.txt — codex writes this for us via -o, but if missing fall back to
  # the last agent_message item.
  if [[ ! -s "$final" && -f "$events" ]]; then
    local txt
    txt=$(jq -r 'select(.type=="item.completed" and .item.type=="agent_message") | .item.text // .item.message // empty' "$events" 2>/dev/null | tail -n1 || true)
    [[ -n "$txt" ]] && printf '%s\n' "$txt" > "$final"
  fi

  # Telemetry from turn.completed.usage
  local is_error="false"
  if [[ -f "$events" ]]; then
    local turn_line
    turn_line=$(jq -c 'select(.type=="turn.completed")' "$events" 2>/dev/null | tail -n1 || true)
    if [[ -n "$turn_line" ]]; then
      local pairs
      pairs=$(printf '%s' "$turn_line" | jq -r '
        {
          input_tokens: .usage.input_tokens,
          cached_input_tokens: .usage.cached_input_tokens,
          output_tokens: .usage.output_tokens,
          reasoning_output_tokens: .usage.reasoning_output_tokens
        }
        | to_entries[] | select(.value != null) | "\(.key)\t\(.value | tostring)"
      ' 2>/dev/null)
      while IFS=$'\t' read -r k v; do
        [[ -z "$k" ]] && continue
        if [[ "$v" =~ ^-?[0-9]+(\.[0-9]+)?$ ]]; then
          write_meta_num "$dir" "$k" "$v"
        else
          write_meta "$dir" "$k" "$v"
        fi
      done <<< "$pairs"
    fi
    # Detect turn.failed or top-level error events
    local err_line
    err_line=$(jq -c 'select(.type=="turn.failed" or .type=="error")' "$events" 2>/dev/null | tail -n1 || true)
    [[ -n "$err_line" ]] && is_error="true"
  fi

  write_meta "$dir" ended_at "$(now_iso)"
  if [[ -n "$exit_code" ]]; then write_meta_num "$dir" exit_code "$exit_code"; fi
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
      local mtime; mtime=$(stat -f %m "$events" 2>/dev/null || stat -c %Y "$events" 2>/dev/null || echo "")
      [[ -n "$mtime" ]] && last_event_age=$(( $(now_epoch) - mtime ))
    fi
  fi

  echo "run_id:      $id"
  echo "tool:        $TOOL"
  echo "status:      $status"
  [[ -n "$pid" ]] && echo "pid:         $pid$(kill -0 "$pid" 2>/dev/null && echo " (alive)" || echo " (gone)")"
  [[ -n "$sid" ]] && echo "thread_id:   $sid"
  echo "events:      $n_events  ($events)"
  [[ -n "$last_event_age" ]] && echo "last_event:  ${last_event_age}s ago"
  echo "started_at:  $started"
  [[ -n "$ended" ]] && echo "ended_at:    $ended"
  if [[ "$status" == "done" || "$status" == "failed" ]]; then
    local in cached out reason
    in=$(jq -r '.input_tokens // empty' "$meta")
    cached=$(jq -r '.cached_input_tokens // empty' "$meta")
    out=$(jq -r '.output_tokens // empty' "$meta")
    reason=$(jq -r '.reasoning_output_tokens // empty' "$meta")
    [[ -n "$in" || -n "$out" ]] && echo "tokens:      in=${in:-0} cached=${cached:-0} out=${out:-0} reasoning=${reason:-0}"
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
      | if $t=="thread.started" then "[thread.started] " + (.thread_id // "")
        elif $t=="turn.started" then "[turn.started]"
        elif $t=="turn.completed" then
          "[turn.completed] in=" + ((.usage.input_tokens // 0) | tostring)
          + " cached=" + ((.usage.cached_input_tokens // 0) | tostring)
          + " out=" + ((.usage.output_tokens // 0) | tostring)
        elif $t=="turn.failed" then "[turn.failed] " + (.error.message // .error // "" | tostring)
        elif $t=="item.started" then "[item.started] " + (.item.type // "?")
        elif $t=="item.completed" then
          (.item.type // "?") as $it
          | if $it=="agent_message" then
              ((.item.text // .item.message // "") | tostring | .[0:120] | gsub("\n"; "\\n")) as $snip
              | "[agent_message] " + $snip
            elif $it=="command_execution" then
              "[command] status=" + (.item.status // "?") + " cmd=" + ((.item.command // "" | tostring) | .[0:80])
            elif $it=="reasoning" then
              ((.item.text // .item.summary // "") | tostring | .[0:120] | gsub("\n"; "\\n")) as $snip
              | "[reasoning] " + $snip
            else "[item.completed] " + $it end
        elif $t=="error" then "[error] " + ((.message // .error // "" ) | tostring)
        else "[" + $t + "]" end
    ' 2>/dev/null || printf '%s\n' "$line"
  done
}

usage() {
  cat <<'EOF'
ask-codex — orchestrator-friendly wrapper around `codex exec`.

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
  ask    [opts] "prompt" [project-dir]      # blocking convenience

Options:
  --resume <thread-id>     Resume an existing codex thread
  --resume-last            Resume the most recent codex thread
  --sandbox <mode>         read-only (default) | workspace-write | danger-full-access
  --model <name>           Override model (default: gpt-5.5)
  --effort <level>         Reasoning effort (default: high)

Legacy positional invocation (no subcommand) is treated as `ask <args>`.
EOF
}

cmd_start() {
  local mode="new" resume_target="" sandbox="$SANDBOX" model="$MODEL" effort="$REASONING_EFFORT"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --resume)      mode="resume"; resume_target="${2:?--resume needs id}"; shift 2;;
      --resume-last) mode="resume-last"; shift;;
      --sandbox)     sandbox="${2:?}"; shift 2;;
      --model)       model="${2:?}"; shift 2;;
      --effort)      effort="${2:?}"; shift 2;;
      --) shift; break;;
      *) break;;
    esac
  done

  if [[ $# -lt 1 ]]; then echo "Error: prompt required" >&2; usage >&2; exit 1; fi
  local prompt_arg="$1"; shift
  local project_dir="${1:-}"

  local prompt
  if [[ "$prompt_arg" == "-" ]]; then prompt="$(cat)"; else prompt="$prompt_arg"; fi
  if [[ -z "${prompt// }" ]]; then echo "Error: prompt is empty" >&2; exit 1; fi

  local run_id; run_id="$(new_run_id)"
  local dir; dir="$(run_dir "$run_id")"
  mkdir -p "$dir"
  printf '%s' "$prompt" > "$dir/prompt.txt"

  # Build the codex command. Resume mode uses `codex exec resume <id>` and
  # does NOT accept -s (inherits sandbox from original session).
  local -a cmd
  case "$mode" in
    resume)
      cmd=(codex exec resume -m "$model" -c "model_reasoning_effort=\"$effort\"" --json -o "$dir/final.txt" "$resume_target" -)
      ;;
    resume-last)
      cmd=(codex exec resume --last -m "$model" -c "model_reasoning_effort=\"$effort\"" --json -o "$dir/final.txt" -)
      ;;
    *)
      cmd=(codex exec -m "$model" -c "model_reasoning_effort=\"$effort\"" -s "$sandbox" --json -o "$dir/final.txt")
      [[ -n "$project_dir" ]] && cmd+=(-C "$project_dir")
      cmd+=(-)  # read prompt from stdin
      ;;
  esac

  printf '%q ' "${cmd[@]}" > "$dir/cmd.txt"; echo >> "$dir/cmd.txt"

  jq -n \
    --arg tool "$TOOL" --arg model "$model" --arg started "$(now_iso)" \
    --arg pdir "$project_dir" --arg mode "$mode" --arg sandbox "$sandbox" --arg effort "$effort" \
    '{tool:$tool, model:$model, status:"running", started_at:$started, project_dir:$pdir, mode:$mode, sandbox:$sandbox, effort:$effort}' \
    > "$dir/meta.json"

  (
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
  echo "TIP: tail with: ask-codex tail $run_id   |   block until done: ask-codex wait $run_id"
}

cmd_status() { local id_in="${1:?}"; local id; id="$(resolve_run "$id_in")" || exit 1; print_status "$id" "$(run_dir "$id")"; }
cmd_tail()   { local id_in="${1:?}"; shift; local n=20; [[ "${1:-}" == "-n" ]] && { n="$2"; shift 2; }; local id; id="$(resolve_run "$id_in")" || exit 1; print_tail "$(run_dir "$id")/events.jsonl" "$n"; }
cmd_events() { local id_in="${1:?}"; local id; id="$(resolve_run "$id_in")" || exit 1; printf '%s\n' "$(run_dir "$id")/events.jsonl"; }

cmd_wait() {
  local id_in="${1:?}"; shift
  local timeout=0; [[ "${1:-}" == "--timeout" ]] && { timeout="$2"; shift 2; }
  local id; id="$(resolve_run "$id_in")" || exit 1
  local dir; dir="$(run_dir "$id")"
  local pid; pid=$(jq -r '.pid // empty' "$dir/meta.json")
  local start_ts; start_ts=$(now_epoch)
  while [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; do
    if [[ "$timeout" -gt 0 && $(($(now_epoch)-start_ts)) -ge "$timeout" ]]; then
      echo "Timeout after ${timeout}s waiting for run $id" >&2; return 124
    fi
    sleep 1
  done
  [[ ! -s "$dir/final.txt" ]] && finalize_run "$dir" || true
  if [[ -s "$dir/final.txt" ]]; then cat "$dir/final.txt"
  else echo "(no final response captured; check $dir/stderr.log)" >&2; return 1; fi
}

cmd_result() {
  local id_in="${1:?}"; local id; id="$(resolve_run "$id_in")" || exit 1
  local dir; dir="$(run_dir "$id")"
  local status; status=$(jq -r '.status // "unknown"' "$dir/meta.json")
  if [[ "$status" == "running" ]]; then echo "Run $id is still running. Use 'wait' or 'status'." >&2; exit 2; fi
  if [[ -s "$dir/final.txt" ]]; then cat "$dir/final.txt"; else echo "(empty)"; fi
}

cmd_cancel() {
  local id_in="${1:?}"; local id; id="$(resolve_run "$id_in")" || exit 1
  local dir; dir="$(run_dir "$id")"
  local pid; pid=$(jq -r '.pid // empty' "$dir/meta.json")
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true; sleep 1; kill -9 "$pid" 2>/dev/null || true
    write_meta "$dir" status "cancelled"; write_meta "$dir" ended_at "$(now_iso)"
    echo "Cancelled $id (pid $pid)"
  else echo "Run $id is not running."; fi
}

cmd_list() {
  local n=10; [[ "${1:-}" == "-n" ]] && { n="$2"; shift 2; }
  ls -1t "$RUN_ROOT" 2>/dev/null | head -n "$n" | while read -r id; do
    local dir="$RUN_ROOT/$id"
    local status started
    status=$(jq -r '.status // "?"' "$dir/meta.json" 2>/dev/null)
    started=$(jq -r '.started_at // "?"' "$dir/meta.json" 2>/dev/null)
    printf '%-32s  %-10s  %s\n' "$id" "$status" "$started"
  done
}

cmd_ask() {
  local out; out="$(cmd_start "$@")"
  echo "$out" >&2
  local rid; rid=$(printf '%s\n' "$out" | awk -F= '/^RUN_ID=/{print $2; exit}')
  cmd_wait "$rid"
}

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
