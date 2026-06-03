#!/usr/bin/env bash
# ask-antigravity: orchestrator-friendly wrapper around `agy -p` (Antigravity CLI).
#
# Designed to be driven by a parent Claude Code session as a thinking partner.
# Spawns the child in the background, captures plain-text stdout (agy has no
# JSON/event stream), exposes the same subcommand surface as ask-claude,
# ask-codex, and ask-gemini.
#
# Liveness note: agy -p emits no structured events — just plain text on stdout
# when the answer is ready (or token-by-token, depending on version). Live
# introspection therefore relies on:
#   - process liveness (pid alive)
#   - output.txt size + mtime (growing → healthy)
#   - stderr.log mtime
#
# Model selection: agy currently has NO --model CLI flag. The wrapper inherits
# whatever model the user pinned via agy's interactive Switch Model menu.
# Recommended default: Gemini 3.5 Flash (High).
#
# Run state lives at: ~/.cache/ask-runs/antigravity/<run-id>/
#   prompt.txt   cmd.txt   output.txt   stderr.log   final.txt   meta.json

set -euo pipefail

TOOL="antigravity"
BIN="${AGY_BIN:-agy}"
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
  [[ -n "$match" ]] && { printf '%s' "$match"; return; }
  echo "Error: no run matching '$id' under $RUN_ROOT" >&2; return 1
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
  local out="$dir/output.txt"
  local final="$dir/final.txt"
  local exit_code; exit_code=$(cat "$dir/exit_code" 2>/dev/null || echo "")
  local started_epoch; started_epoch=$(jq -r '.started_epoch // empty' "$dir/meta.json" 2>/dev/null)

  if [[ ! -s "$final" && -s "$out" ]]; then
    cp "$out" "$final"
  fi

  write_meta "$dir" ended_at "$(now_iso)"
  if [[ -n "$started_epoch" ]]; then
    local dur_ms=$(( ( $(now_epoch) - started_epoch ) * 1000 ))
    write_meta_num "$dir" duration_ms "$dur_ms"
  fi
  if [[ -n "$exit_code" ]]; then write_meta_num "$dir" exit_code "$exit_code"; fi
  if [[ -n "$exit_code" && "$exit_code" != "0" ]]; then
    write_meta "$dir" status "failed"
  else
    write_meta "$dir" status "done"
  fi
}

print_status() {
  local id="$1" dir="$2"
  local meta="$dir/meta.json" out="$dir/output.txt"
  local status pid started ended
  status=$(jq -r '.status // "unknown"' "$meta" 2>/dev/null)
  pid=$(jq -r '.pid // empty' "$meta" 2>/dev/null)
  started=$(jq -r '.started_at // empty' "$meta" 2>/dev/null)
  ended=$(jq -r '.ended_at // empty' "$meta" 2>/dev/null)

  if [[ "$status" == "running" && -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
    finalize_run "$dir"
    status=$(jq -r '.status' "$meta" 2>/dev/null)
    ended=$(jq -r '.ended_at // empty' "$meta" 2>/dev/null)
  fi

  local bytes=0 last_write_age=""
  if [[ -f "$out" ]]; then
    bytes=$(wc -c < "$out" | tr -d ' ')
    if [[ "$bytes" -gt 0 ]]; then
      local mtime; mtime=$(stat -f %m "$out" 2>/dev/null || stat -c %Y "$out" 2>/dev/null || echo "")
      [[ -n "$mtime" ]] && last_write_age=$(( $(now_epoch) - mtime ))
    fi
  fi

  echo "run_id:       $id"
  echo "tool:         $TOOL"
  echo "status:       $status"
  [[ -n "$pid" ]] && echo "pid:          $pid$(kill -0 "$pid" 2>/dev/null && echo " (alive)" || echo " (gone)")"
  echo "output_bytes: $bytes  ($out)"
  [[ -n "$last_write_age" ]] && echo "last_write:   ${last_write_age}s ago"
  echo "started_at:   $started"
  [[ -n "$ended" ]] && echo "ended_at:     $ended"
  if [[ "$status" == "done" || "$status" == "failed" ]]; then
    local dur; dur=$(jq -r '.duration_ms // empty' "$meta")
    [[ -n "$dur" ]] && echo "duration_ms:  $dur"
  fi
  echo "run_dir:      $dir"

  # Liveness hints while running
  if [[ "$status" == "running" ]]; then
    if [[ "$bytes" -eq 0 ]]; then
      local age_started; age_started=$(( $(now_epoch) - $(jq -r '.started_epoch // 0' "$meta") ))
      if [[ "$age_started" -gt 60 ]]; then
        echo "hint:         no output after ${age_started}s — check stderr.log for auth/network issues"
      fi
    elif [[ -n "$last_write_age" && "$last_write_age" -gt 120 ]]; then
      echo "hint:         output stalled for ${last_write_age}s — child may be hung; consider 'cancel'"
    fi
  fi
}

usage() {
  cat <<'EOF'
ask-antigravity — orchestrator-friendly wrapper around `agy -p`.

Subcommands:
  start [opts] "prompt" [project-dir]
  start [opts] - [project-dir]              # prompt from stdin
  status <run-id|latest>
  tail   <run-id|latest> [-n 40]
  output <run-id|latest>                    # prints output.txt path
  wait   <run-id|latest> [--timeout SEC]
  result <run-id|latest>
  cancel <run-id|latest>
  list   [-n 10]
  ask    [opts] "prompt" [project-dir]      # blocking convenience

Options (pass-through to agy):
  --continue, -c           Continue the most recent agy conversation
  --conversation <id>      Resume a specific agy conversation by ID
  --print-timeout <dur>    Override agy's print-mode timeout (default 5m)
  --add-dir <path>         Add a directory to the workspace (repeatable)
  --sandbox                Run in agy's sandbox
  --yolo                   Set --dangerously-skip-permissions
                             (auto-enabled when project-dir is supplied)

Model selection:
  agy currently has NO --model CLI flag. Pin your preferred model once via
  `agy` interactive → Switch Model. The wrapper inherits that choice.
  Recommended default: Gemini 3.5 Flash (High).

Legacy positional invocation (no subcommand) is treated as `ask <args>`.
EOF
}

cmd_start() {
  local -a passthrough=()
  local yolo="" project_yolo_auto=1

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -c|--continue) passthrough+=(--continue); shift;;
      --conversation) passthrough+=(--conversation "${2:?}"); shift 2;;
      --print-timeout) passthrough+=(--print-timeout "${2:?}"); shift 2;;
      --add-dir) passthrough+=(--add-dir "${2:?}"); shift 2;;
      --sandbox) passthrough+=(--sandbox); shift;;
      --yolo) yolo=1; shift;;
      --no-auto-yolo) project_yolo_auto=0; shift;;
      --) shift; break;;
      -) break;;  # bare '-' is the stdin prompt sentinel, not an option
      -*) echo "Unknown option: $1" >&2; usage >&2; exit 1;;
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

  local -a cmd=("$BIN" "${passthrough[@]}")
  if [[ -n "$yolo" || ( -n "$project_dir" && "$project_yolo_auto" == "1" ) ]]; then
    cmd+=(--dangerously-skip-permissions)
  fi
  cmd+=(-p "$prompt")

  printf '%q ' "${cmd[@]}" > "$dir/cmd.txt"; echo >> "$dir/cmd.txt"

  jq -n \
    --arg tool "$TOOL" --arg started "$(now_iso)" --argjson started_epoch "$(now_epoch)" \
    --arg pdir "$project_dir" \
    '{tool:$tool, status:"running", started_at:$started, started_epoch:$started_epoch, project_dir:$pdir}' \
    > "$dir/meta.json"

  local cwd_arg=""; [[ -n "$project_dir" ]] && cwd_arg="$project_dir"

  (
    if [[ -n "$cwd_arg" ]]; then cd "$cwd_arg"; fi
    "${cmd[@]}" > "$dir/output.txt" 2> "$dir/stderr.log"
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
  echo "OUTPUT=$dir/output.txt"
  echo "TIP: tail with: ask-antigravity tail $run_id   |   block until done: ask-antigravity wait $run_id"
}

cmd_status() { local id_in="${1:?}"; local id; id="$(resolve_run "$id_in")" || exit 1; print_status "$id" "$(run_dir "$id")"; }
cmd_tail()   {
  local id_in="${1:?}"; shift
  local n=40; [[ "${1:-}" == "-n" ]] && { n="$2"; shift 2; }
  local id; id="$(resolve_run "$id_in")" || exit 1
  local out="$(run_dir "$id")/output.txt"
  if [[ ! -f "$out" ]]; then echo "(no output yet)"; return; fi
  tail -n "$n" "$out"
}
cmd_output() { local id_in="${1:?}"; local id; id="$(resolve_run "$id_in")" || exit 1; printf '%s\n' "$(run_dir "$id")/output.txt"; }

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
  else echo "(no output captured; check $dir/stderr.log)" >&2; return 1; fi
}

cmd_result() {
  local id_in="${1:?}"; local id; id="$(resolve_run "$id_in")" || exit 1
  local dir; dir="$(run_dir "$id")"
  local status; status=$(jq -r '.status // "unknown"' "$dir/meta.json")
  if [[ "$status" == "running" ]]; then echo "Run $id is still running. Use 'wait' or 'status'." >&2; exit 2; fi
  if [[ -s "$dir/final.txt" ]]; then cat "$dir/final.txt"
  elif [[ -s "$dir/output.txt" ]]; then cat "$dir/output.txt"
  else echo "(empty)"; fi
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
  output|events) shift; cmd_output "$@";;
  wait)    shift; cmd_wait "$@";;
  result)  shift; cmd_result "$@";;
  cancel)  shift; cmd_cancel "$@";;
  list)    shift; cmd_list "$@";;
  ask)     shift; cmd_ask "$@";;
  -h|--help|help) usage;;
  *)       cmd_ask "$@";;
esac
