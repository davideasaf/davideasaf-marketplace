#!/usr/bin/env bash
# ask-codex: orchestrator-friendly wrapper around `codex exec`.
#
# Designed to be driven by a host agent as a thinking partner. The host may
# keep the foreground child in a managed background session. Captures the JSONL event stream
# (`codex exec --json`) for live introspection, writes the clean final
# response to a separate file (`-o final.txt`), and exposes a uniform
# subcommand surface (run/start/status/tail/events/wait/result/cancel/list/ask)
# matching ask-claude and ask-gemini.
#
# Run state lives at: ~/.cache/ask-runs/codex/<run-id>/
#   prompt.txt    cmd.txt    events.jsonl    stderr.log    final.txt    meta.json

set -euo pipefail

MODEL="gpt-6.1-sol"
REASONING_EFFORT="xhigh"
SANDBOX="read-only"
CU_MODEL="gpt-6.1-terra"
CU_EFFORT="max"
CODEX_BIN="${ASK_CODEX_BIN:-codex}"
CODEX_CONFIG="${CODEX_CONFIG:-${CODEX_HOME:-$HOME/.codex}/config.toml}"
TOOL="codex"

# codex exec refuses a working dir that is neither inside a git repo nor
# listed as trusted in config.toml. An isolated Fable run carries no user
# config, so only git counts there.
needs_skip_git_check() {
  local d="$1"
  git -C "$d" rev-parse --show-toplevel >/dev/null 2>&1 && return 1
  if [[ -z "${FABLE_ORCHESTRATOR_ISOLATION_JSON:-}" ]] && grep -qF "[projects.\"$d\"]" "$CODEX_CONFIG" 2>/dev/null; then
    return 1
  fi
  return 0
}

# Short aliases for the current Codex catalog (see ~/.codex/models_cache.json).
resolve_model() {
  local lower; lower=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')
  case "$lower" in
    astra) echo "gpt-6-astra";;
    sol)   echo "gpt-6.1-sol";;
    terra) echo "gpt-6.1-terra";;
    luna)  echo "gpt-6-luna";;
    *)     echo "$1";;
  esac
}
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CU_PREAMBLE="$SKILL_DIR/references/computer-use-mission.md"
SUPERVISOR="$SKILL_DIR/scripts/supervisor.py"
RUN_ROOT="${ASK_RUN_ROOT:-$HOME/.cache/ask-runs}/$TOOL"
umask 077
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
  update_meta "$1" "$2" "$3" string
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

write_meta_num() {
  update_meta "$1" "$2" "$3" number
}

has_nonblank_text() { [[ -f "$1" ]] && LC_ALL=C grep -q '[^[:space:]]' "$1"; }

resolve_run() {
  local id="$1"
  if [[ "$id" == "latest" ]]; then ls -1t "$RUN_ROOT" 2>/dev/null | head -n1; return; fi
  if [[ -d "$RUN_ROOT/$id" ]]; then printf '%s' "$id"; return; fi
  local match; match=$(ls -1 "$RUN_ROOT" 2>/dev/null | grep -E "^${id}" | head -n1 || true)
  if [[ -n "$match" ]]; then printf '%s' "$match"; return; fi
  echo "Error: no run matching '$id' under $RUN_ROOT" >&2
  return 1
}

write_terminal_status() {
  python3 - "$1" "$2" "$3" "$4" "$(now_iso)" <<'PY_STATUS'
import fcntl, json, os, pathlib, sys, tempfile
directory, status, reason, code, ended = sys.argv[1:]
path = pathlib.Path(directory) / 'meta.json'
with path.with_name('.metadata.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    data = json.loads(path.read_text())
    if data.get('status') != 'cancelled':
        data.update(status=status, ended_at=ended)
        if reason:
            data['failure_reason'] = reason
        else:
            data.pop('failure_reason', None)
        if code:
            data['exit_code'] = int(code)
        else:
            data.pop('exit_code', None)
        fd, temporary = tempfile.mkstemp(prefix='.metadata-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as output:
                json.dump(data, output, indent=2)
                output.write('\n')
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
PY_STATUS
}

finalize_run() {
  local dir="$1"
  local lock="$dir/finalize.lock"
  if ! mkdir "$lock" 2>/dev/null; then
    for _ in {1..40}; do
      [[ ! -d "$lock" ]] && return 0
      sleep 0.05
    done
    return 1
  fi
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

  if [[ -f "$dir/cancelled" || "$(jq -r '.status // empty' "$dir/meta.json")" == "cancelled" ]]; then
    write_terminal_status "$dir" "cancelled" "cancelled" "$exit_code"
  elif [[ -z "$exit_code" ]]; then
    write_terminal_status "$dir" "failed" "missing_exit_code" ""
  elif [[ "$is_error" == "true" ]]; then
    write_terminal_status "$dir" "failed" "event_error" "$exit_code"
  elif [[ "$exit_code" != "0" ]]; then
    write_terminal_status "$dir" "failed" "nonzero_exit" "$exit_code"
  elif ! has_nonblank_text "$final"; then
    write_terminal_status "$dir" "empty-output" "empty_output" "$exit_code"
  else
    write_terminal_status "$dir" "done" "" "$exit_code"
    # Computer-use missions end with a protocol line (see
    # references/computer-use-mission.md); surface it as meta.outcome.
    local first outcome
    first=$(LC_ALL=C grep -m1 '[^[:space:]]' "$final" || true)
    local re='^[*_` ]*(DONE|NEEDS_CONFIRMATION|WAITING_FOR_HUMAN|BLOCKED)([^A-Z_]|$)'
    if [[ "$first" =~ $re ]]; then outcome="${BASH_REMATCH[1]}"; write_meta "$dir" outcome "$outcome"; fi
  fi
  rmdir "$lock" 2>/dev/null || true
}

refresh_pid_from_runner_file() {
  local dir="$1"
  local meta="$dir/meta.json"
  local pid
  pid=$(jq -r '.pid // empty' "$meta" 2>/dev/null || true)
  if [[ -z "$pid" && -s "$dir/runner_pid" ]]; then
    pid=$(cat "$dir/runner_pid" 2>/dev/null || true)
    [[ -n "$pid" ]] && write_meta_num "$dir" pid "$pid"
  fi
  printf '%s' "$pid"
}

remove_isolated_auth() {
  local dir="$1"
  local expected_runtime="$dir/runtime-home"
  local recorded_runtime auth_copy marker
  recorded_runtime=$(jq -r '.runtime_home // empty' "$dir/meta.json" 2>/dev/null || true)
  [[ -z "$recorded_runtime" ]] && return 0
  if [[ "$recorded_runtime" != "$expected_runtime" ]]; then
    echo "Error: refusing credential cleanup outside the canonical run runtime home" >&2
    return 1
  fi
  auth_copy="$expected_runtime/.codex/auth.json"
  marker="$dir/auth-removed"
  if [[ -L "$auth_copy" ]]; then
    echo "Error: refusing to follow a symlinked isolated Codex auth file" >&2
    return 1
  fi
  if [[ -f "$auth_copy" ]]; then
    unlink "$auth_copy"
  fi
  if [[ ! -e "$auth_copy" && ! -L "$auth_copy" ]]; then
    printf 'removed\n' > "$marker"
    chmod 600 "$marker"
  fi
}

write_runner_script() {
  local run_id="$1" dir="$2" cwd_arg="$3" detached="$4"; shift 4
  local runner="$dir/runner.sh"
  local label="com.ask-${TOOL}.${run_id//[^A-Za-z0-9]/-}"
  {
    echo '#!/bin/bash'
    echo 'set +e'
    echo 'umask 077'
    printf 'export PATH=%q\n' "$PATH"
    printf 'export HOME=%q\n' "$HOME"
    printf 'export ASK_RUN_ROOT=%q\n' "${RUN_ROOT%/$TOOL}"
    if [[ -n "${CODEX_HOME:-}" ]]; then
      printf 'export CODEX_HOME=%q\n' "$CODEX_HOME"
    fi
    if [[ -n "${CODEX_SQLITE_HOME:-}" ]]; then
      printf 'export CODEX_SQLITE_HOME=%q\n' "$CODEX_SQLITE_HOME"
    fi
    for name in \
      FABLE_ORCHESTRATOR_ASK_CODEX \
      FABLE_ORCHESTRATOR_CODEX_SHIM_DIR \
      FABLE_ORCHESTRATOR_ISOLATION_JSON \
      FABLE_ORCHESTRATOR_REAL_CODEX \
      FABLE_ORCHESTRATOR_WATCHDOG \
      FABLE_ORCHESTRATOR_WATCHDOG_GRACE_S \
      FABLE_ORCHESTRATOR_WATCHDOG_TIMEOUT_S; do
      if [[ -n "${!name:-}" ]]; then
        printf 'export %s=%q\n' "$name" "${!name}"
      fi
    done
    printf 'echo $$ > %q\n' "$dir/runner_pid"
    if [[ -n "$cwd_arg" ]]; then
      printf 'cd %q || exit 127\n' "$cwd_arg"
    fi
    printf 'cmd=('
    printf '%q ' "$@"
    echo ')'
    printf 'python3 %q supervise %q %q "${cmd[@]}"\n' "$SUPERVISOR" "$dir" "$cwd_arg"
    if [[ "$detached" == "true" ]]; then
      printf 'command -v launchctl >/dev/null 2>&1 && launchctl remove %q >/dev/null 2>&1 || true\n' "$label"
    fi
  } > "$runner"
  chmod +x "$runner"
  printf '%s' "$runner"
}

spawn_runner() {
  local run_id="$1" dir="$2" runner="$3"
  local pid="" label=""

  if [[ "$(uname -s 2>/dev/null || true)" == "Darwin" ]] && command -v launchctl >/dev/null 2>&1; then
    label="com.ask-${TOOL}.${run_id//[^A-Za-z0-9]/-}"
    write_meta "$dir" launch_label "$label"
    if ! launchctl submit -l "$label" -- "$runner"; then
      echo "Error: launchctl could not submit durable runner $label" >&2
      return 1
    fi
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
      if [[ -s "$dir/runner_pid" ]]; then
        pid=$(cat "$dir/runner_pid" 2>/dev/null || true)
        break
      fi
      sleep 0.1
    done
    if [[ -z "$pid" ]]; then
      launchctl remove "$label" >/dev/null 2>&1 || true
      echo "Error: durable runner $label published no PID" >&2
      return 1
    fi
    write_meta_num "$dir" pid "$pid"
    return 0
  fi

  "$runner" &
  pid=$!
  disown "$pid" 2>/dev/null || true
  write_meta_num "$dir" pid "$pid"
}

print_status() {
  local id="$1" dir="$2"
  local meta="$dir/meta.json" events="$dir/events.jsonl"
  local status pid sid started ended
  status=$(jq -r '.status // "unknown"' "$meta" 2>/dev/null)
  pid=$(refresh_pid_from_runner_file "$dir")
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

screen_locked() {
  if [[ -n "${ASK_CODEX_SCREEN_LOCKED:-}" ]]; then [[ "$ASK_CODEX_SCREEN_LOCKED" == "1" ]]; return; fi
  # Capture first: under pipefail, `ioreg | grep -q` can SIGPIPE ioreg (141) and read as unlocked.
  local root; root="$(ioreg -n Root -d1 2>/dev/null || true)"
  [[ "$root" == *'"CGSSessionScreenIsLocked"=Yes'* ]]
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
  run   [opts] "prompt" [project-dir]       # foreground; host may background
  run   [opts] - [project-dir]              # prompt from stdin
  start [opts] "prompt" [project-dir]       # legacy; ASK_ALLOW_LAUNCHCTL=1
  start [opts] - [project-dir]
  status <run-id|latest>
  tail   <run-id|latest> [-n 20]
  events <run-id|latest>                    # prints JSONL path
  wait   <run-id|latest> [--timeout SEC]
  result <run-id|latest>
  cancel <run-id|latest>
  list   [-n 10]
  reply <run-id> [--wait] "message"  # managed continuation
  preflight [project-dir]          # read-only readiness checks
  ask    [opts] "prompt" [project-dir]      # blocking convenience

Options:
  --resume <thread-id>     Resume an existing codex thread
  --resume-last            Resume the most recent codex thread
  --sandbox <mode>         read-only (default) | workspace-write | danger-full-access
  --model <name>           Override model (default: gpt-6.1-sol)
                           Aliases: astra=gpt-6-astra  sol=gpt-6.1-sol  terra=gpt-6.1-terra  luna=gpt-6-luna
  --effort <level>         Reasoning effort (default: xhigh; computer-use: max)
  --computer-use           GUI mission with explicit full-access sandbox
  --image <file>           Attach an image (repeatable)
  --config <key=value>     Codex configuration override (repeatable)

Legacy positional invocation (no subcommand) is treated as `ask <args>`.
EOF
}

cmd_start() {
  local execution="detached"
  if [[ "${1:-}" == "--managed" ]]; then
    execution="managed"
    shift
  fi
  if [[ "$execution" == "detached" && "${ASK_ALLOW_LAUNCHCTL:-}" != "1" ]]; then
    echo "Error: 'start' self-detachment is disabled because it registers a launchd job." >&2
    echo "Use 'run' in the host agent's managed background session." >&2
    echo "Security-approved compatibility only: ASK_ALLOW_LAUNCHCTL=1 ask.sh start ..." >&2
    return 64
  fi

  local mode="new" resume_target="" sandbox="$SANDBOX" model="$MODEL" effort="$REASONING_EFFORT"
  local computer_use=false effort_set=false model_set=false
  local -a extra_configs=() images=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --resume)      mode="resume"; resume_target="${2:?--resume needs id}"; shift 2;;
      --resume-last) mode="resume-last"; shift;;
      --sandbox)     sandbox="${2:?}"; shift 2;;
      --model)       model="$(resolve_model "${2:?}")"; model_set=true; shift 2;;
      --effort)      effort="${2:?}"; effort_set=true; shift 2;;
      --computer-use) computer_use=true; shift;;
      --image)       images+=("${2:?--image needs a file}"); shift 2;;
      --config)      extra_configs+=("${2:?--config needs key=value}"); shift 2;;
      --) shift; break;;
      --*) echo "Error: unsupported option $1" >&2; return 2;;
      *) break;;
    esac
  done

  if [[ $# -lt 1 ]]; then echo "Error: prompt required" >&2; usage >&2; exit 1; fi
  local prompt_arg="$1"; shift
  local project_dir="${1:-}"
  [[ $# -le 1 ]] || { echo "Error: unexpected extra arguments" >&2; return 2; }
  [[ -z "$project_dir" || -d "$project_dir" ]] || { echo "Error: project directory does not exist" >&2; return 2; }
  if [[ -n "$project_dir" ]]; then project_dir="$(cd -- "$project_dir" && pwd -P)"; fi

  local prompt
  if [[ "$prompt_arg" == "-" ]]; then prompt="$(cat)"; else prompt="$prompt_arg"; fi
  if [[ -z "${prompt// }" ]]; then echo "Error: prompt is empty" >&2; exit 1; fi

  local locked=false
  if [[ "$computer_use" == true ]]; then
    sandbox="danger-full-access"
    [[ "$model_set" == true ]] || model="$CU_MODEL"
    [[ "$effort_set" == true ]] || effort="$CU_EFFORT"
    if [[ "$mode" == "new" ]]; then
      [[ -s "$CU_PREAMBLE" ]] || { echo "Error: missing computer-use-mission.md reference: $CU_PREAMBLE" >&2; return 2; }
      prompt="$(cat "$CU_PREAMBLE")"$'\n\n## Mission\n\n'"$prompt"
    fi
    if screen_locked; then
      locked=true
      echo "WARNING: screen appears locked; verify the requested UI surface is available." >&2
    fi
  fi

  local run_id; run_id="$(new_run_id)"
  local dir; dir="$(run_dir "$run_id")"
  mkdir -p "$dir"
  printf '%s' "$prompt" > "$dir/prompt.txt"
  if [[ -n "${FABLE_ORCHESTRATOR_ISOLATION_JSON:-}" ]]; then
    local source_codex_home auth_source runtime_home isolated_codex_home
    source_codex_home="${CODEX_HOME:-$HOME/.codex}"
    auth_source="${FABLE_ORCHESTRATOR_AUTH_SOURCE:-$source_codex_home/auth.json}"
    if [[ ! -f "$auth_source" || -L "$auth_source" ]]; then
      echo "Error: isolated Fable worker requires a regular Codex auth file" >&2
      exit 1
    fi
    runtime_home="$dir/runtime-home"
    isolated_codex_home="$runtime_home/.codex"
    mkdir -m 700 "$runtime_home" "$isolated_codex_home"
    cp "$auth_source" "$isolated_codex_home/auth.json"
    chmod 600 "$isolated_codex_home/auth.json"
    export HOME="$runtime_home"
    export CODEX_HOME="$isolated_codex_home"
    export CODEX_SQLITE_HOME="$isolated_codex_home"
  fi

  # Build the codex command. Resume mode uses `codex exec resume <id>` and
  # does NOT accept -s (inherits sandbox from original session).
  local -a cmd passthrough=()
  local extra
  for extra in "${extra_configs[@]+"${extra_configs[@]}"}"; do passthrough+=(-c "$extra"); done
  for extra in "${images[@]+"${images[@]}"}"; do passthrough+=("--image=$extra"); done
  local skip_git=false
  if needs_skip_git_check "${project_dir:-$(pwd -P)}"; then skip_git=true; passthrough+=(--skip-git-repo-check); fi
  case "$mode" in
    resume)
      cmd=("$CODEX_BIN" exec resume -m "$model" -c "model_reasoning_effort=\"$effort\"" --json -o "$dir/final.txt" "${passthrough[@]+"${passthrough[@]}"}" "$resume_target" -)
      ;;
    resume-last)
      cmd=("$CODEX_BIN" exec resume --last -m "$model" -c "model_reasoning_effort=\"$effort\"" --json -o "$dir/final.txt" "${passthrough[@]+"${passthrough[@]}"}" -)
      ;;
    *)
      cmd=("$CODEX_BIN" exec -m "$model" -c "model_reasoning_effort=\"$effort\"" -s "$sandbox" --json -o "$dir/final.txt" "${passthrough[@]+"${passthrough[@]}"}")
      [[ -n "$project_dir" ]] && cmd+=(-C "$project_dir")
      cmd+=(-)  # read prompt from stdin
      ;;
  esac

  printf '%q ' "${cmd[@]}" > "$dir/cmd.txt"; echo >> "$dir/cmd.txt"

  jq -n \
    --arg tool "$TOOL" --arg model "$model" --arg started "$(now_iso)" \
    --arg pdir "$project_dir" --arg mode "$mode" --arg sandbox "$sandbox" --arg effort "$effort" \
    --argjson cu "$computer_use" --argjson locked "$locked" --argjson skipgit "$skip_git" \
    '{tool:$tool, model:$model, status:"running", started_at:$started, project_dir:$pdir, mode:$mode, sandbox:$sandbox, effort:$effort}
     + (if $cu then {computer_use:true, screen_locked:$locked} else {} end)
     + (if $skipgit then {skip_git_repo_check:true} else {} end)'  \
    > "$dir/meta.json"
  if [[ -n "${FABLE_ORCHESTRATOR_ISOLATION_JSON:-}" ]]; then
    write_meta "$dir" runtime_home "$runtime_home"
    write_meta "$dir" codex_home "$isolated_codex_home"
  fi

  local detached="false"
  [[ "$execution" == "detached" ]] && detached="true"
  local runner
  runner=$(write_runner_script "$run_id" "$dir" "$project_dir" "$detached" "${cmd[@]}")
  echo "RUN_ID=$run_id"
  echo "RUN_DIR=$dir"
  echo "EVENTS=$dir/events.jsonl"
  echo "TIP: tail with: ask-codex tail $run_id   |   block until done: ask-codex wait $run_id"

  if [[ "$execution" == "managed" ]]; then
    "$runner"
    local recorded_code status
    recorded_code=$(cat "$dir/exit_code" 2>/dev/null || echo "")
    status=$(jq -r '.status // "failed"' "$dir/meta.json" 2>/dev/null || echo "failed")
    if [[ "$status" != "done" ]]; then
      [[ "$recorded_code" =~ ^[0-9]+$ && "$recorded_code" != "0" ]] && return "$recorded_code"
      return 1
    fi
    return 0
  fi

  spawn_runner "$run_id" "$dir" "$runner"
}

cmd_run() { cmd_start --managed "$@"; }

cmd_status() { local id_in="${1:?}"; local id; id="$(resolve_run "$id_in")" || exit 1; print_status "$id" "$(run_dir "$id")"; }
cmd_tail()   { local id_in="${1:?}"; shift; local n=20; [[ "${1:-}" == "-n" ]] && { n="$2"; shift 2; }; local id; id="$(resolve_run "$id_in")" || exit 1; print_tail "$(run_dir "$id")/events.jsonl" "$n"; }
cmd_events() { local id_in="${1:?}"; local id; id="$(resolve_run "$id_in")" || exit 1; printf '%s\n' "$(run_dir "$id")/events.jsonl"; }

cmd_wait() {
  local id_in="${1:?}"; shift
  local timeout=0; [[ "${1:-}" == "--timeout" ]] && { timeout="$2"; shift 2; }
  local id; id="$(resolve_run "$id_in")" || exit 1
  local dir; dir="$(run_dir "$id")"
  local pid; pid=$(refresh_pid_from_runner_file "$dir")
  local start_ts; start_ts=$(now_epoch)
  while [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; do
    if [[ "$timeout" -gt 0 && $(($(now_epoch)-start_ts)) -ge "$timeout" ]]; then
      echo "Timeout after ${timeout}s waiting for run $id" >&2; return 124
    fi
    sleep 1
  done
  finalize_run "$dir"
  local status reason
  status=$(jq -r '.status // "unknown"' "$dir/meta.json")
  reason=$(jq -r '.failure_reason // empty' "$dir/meta.json")
  if [[ "$status" == "done" ]] && has_nonblank_text "$dir/final.txt"; then
    cat "$dir/final.txt"
  else
    echo "Run $id ended with status '$status'${reason:+ ($reason)}; check $dir/stderr.log and $dir/events.jsonl" >&2
    return 1
  fi
}

cmd_result() {
  local id_in="${1:?}"; local id; id="$(resolve_run "$id_in")" || exit 1
  local dir; dir="$(run_dir "$id")"
  local status; status=$(jq -r '.status // "unknown"' "$dir/meta.json")
  if [[ "$status" == "running" ]]; then
    local pid; pid=$(refresh_pid_from_runner_file "$dir")
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "Run $id is still running. Use 'wait' or 'status'." >&2
      exit 2
    fi
    finalize_run "$dir"
    status=$(jq -r '.status // "unknown"' "$dir/meta.json")
  fi
  if [[ "$status" == "done" ]] && ! has_nonblank_text "$dir/final.txt"; then
    finalize_run "$dir"
    status=$(jq -r '.status // "unknown"' "$dir/meta.json")
  fi
  if [[ "$status" == "done" ]] && has_nonblank_text "$dir/final.txt"; then
    cat "$dir/final.txt"
  else
    local reason; reason=$(jq -r '.failure_reason // empty' "$dir/meta.json")
    echo "Run $id ended with status '$status'${reason:+ ($reason)}; check $dir/stderr.log and $dir/events.jsonl" >&2
    return 1
  fi
}

cmd_cancel() {
  local id_in="${1:?}"; local id; id="$(resolve_run "$id_in")" || exit 1
  local dir; dir="$(run_dir "$id")"
  local pid status label
  pid=$(refresh_pid_from_runner_file "$dir")
  status=$(jq -r '.status // "unknown"' "$dir/meta.json" 2>/dev/null)
  label=$(jq -r '.launch_label // empty' "$dir/meta.json" 2>/dev/null)
  if [[ "$status" == "running" ]]; then
    : > "$dir/cancelled"
    : > "$dir/cancel.request"
    chmod 600 "$dir/cancelled" "$dir/cancel.request"
    if [[ -n "$(jq -r '.child_pid // empty' "$dir/meta.json")" ]]; then
      local attempt=0
      while [[ ! -f "$dir/supervisor.done" && "$attempt" -lt 100 ]]; do
        sleep 0.05
        attempt=$((attempt + 1))
      done
      if [[ ! -f "$dir/supervisor.done" ]]; then
        echo "Cancellation requested but not confirmed for $id" >&2
        return 1
      fi
      local terminal; terminal=$(jq -r '.status' "$dir/meta.json")
      if [[ "$terminal" == "cancelled" ]]; then
        echo "Cancelled $id"
      elif [[ "$terminal" == "done" ]]; then
        echo "Run $id completed before cancellation."
      else
        echo "Run $id ended with status $terminal; cancellation was not confirmed" >&2
        return 1
      fi
    else
      echo "Cancellation requested for legacy run $id; provider termination is unconfirmed" >&2
      return 1
    fi
  else echo "Run $id is not running."; fi
}

cmd_reply() {
  local id_in="${1:?run-id required}"; shift
  local block=false; [[ "${1:-}" == "--wait" ]] && { block=true; shift; }
  local msg="${1:?reply message required}"
  local id; id="$(resolve_run "$id_in")" || exit 1
  local meta; meta="$(run_dir "$id")/meta.json"
  local tid pdir model effort
  tid=$(jq -r '.session_id // empty' "$meta"); pdir=$(jq -r '.project_dir // empty' "$meta")
  model=$(jq -r '.model // empty' "$meta"); effort=$(jq -r '.effort // empty' "$meta")
  [[ -n "$tid" ]] || { echo "Error: run $id has no thread id (did it start?)" >&2; exit 1; }
  local -a args=(--resume "$tid" --model "${model:-$MODEL}" --effort "${effort:-$REASONING_EFFORT}")
  [[ "$(jq -r '.computer_use // false' "$meta")" == true ]] && args+=(--computer-use)
  if [[ "$block" == true ]]; then cmd_ask "${args[@]}" "$msg" ${pdir:+"$pdir"}
  else cmd_run "${args[@]}" "$msg" ${pdir:+"$pdir"}; fi
}

cmd_preflight() {
  local pdir="${1:-$PWD}" ok=true
  [[ -d "$pdir" ]] && pdir="$(cd -- "$pdir" && pwd -P)"
  local ver; ver=$("$CODEX_BIN" --version 2>/dev/null || true)
  if [[ -n "$ver" ]]; then echo "codex:         $ver ($(command -v "$CODEX_BIN"))"
  else echo "codex:         MISSING ($CODEX_BIN)"; ok=false; fi
  local p state
  for p in unified-computer-use@openai-bundled computer-use@openai-bundled chrome@openai-bundled browser@openai-bundled; do
    state=$(grep -A1 -F "[plugins.\"$p\"]" "$CODEX_CONFIG" 2>/dev/null | grep -Eo 'enabled = (true|false)' | awk '{print $3}' || true)
    printf 'plugin:        %-38s %s\n' "$p" "${state:-not configured}"
    [[ "$p" == unified-computer-use@openai-bundled && "$state" != true ]] && ok=false
  done
  if [[ -d "${CODEX_HOME:-$HOME/.codex}/computer-use/Codex Computer Use.app" ]]; then echo "cua app:       installed"
  else echo "cua app:       MISSING (install Computer Use from the Codex desktop app)"; ok=false; fi
  if screen_locked; then echo "screen:        LOCKED — native apps unavailable; verify browser support separately"
  else echo "screen:        unlocked"; fi
  local root; root=$(git -C "$pdir" rev-parse --show-toplevel 2>/dev/null || true)
  if [[ -z "$root" ]]; then
    if needs_skip_git_check "$pdir"; then echo "project-dir:   $pdir (not git, not trusted — wrapper adds --skip-git-repo-check)"
    else echo "project-dir:   $pdir (not git, trusted)"; fi
  elif grep -qF "[projects.\"$root\"]" "$CODEX_CONFIG" 2>/dev/null; then echo "project-dir:   $root (git, trusted)"
  else echo "project-dir:   $root (git, not listed as trusted in config.toml)"; fi
  if [[ "$ok" == true ]]; then echo "READY"; else echo "NOT READY"; return 1; fi
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
  local out; out="$(cmd_run "$@")"
  echo "$out" >&2
  local rid; rid=$(printf '%s\n' "$out" | awk -F= '/^RUN_ID=/{print $2; exit}')
  cmd_wait "$rid"
}

if [[ $# -eq 0 ]]; then usage; exit 0; fi
case "$1" in
  __remove-auth) shift; id="$(resolve_run "${1:?}")" || exit 1; remove_isolated_auth "$(run_dir "$id")";;
  __finalize) shift; id="$(resolve_run "${1:?}")" || exit 1; finalize_run "$(run_dir "$id")";;
  run)     shift; cmd_run "$@";;
  start)   shift; cmd_start "$@";;
  status)  shift; cmd_status "$@";;
  tail)    shift; cmd_tail "$@";;
  events)  shift; cmd_events "$@";;
  wait)    shift; cmd_wait "$@";;
  result)  shift; cmd_result "$@";;
  cancel)  shift; cmd_cancel "$@";;
  list)    shift; cmd_list "$@";;
  ask)     shift; cmd_ask "$@";;
  reply)   shift; cmd_reply "$@";;
  preflight) shift; cmd_preflight "$@";;
  -h|--help|help) usage;;
  *)       cmd_ask "$@";;
esac
