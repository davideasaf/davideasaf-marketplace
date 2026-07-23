#!/bin/sh
set -eu
umask 077
wrapper="${FABLE_ORCHESTRATOR_ASK_CODEX:-$HOME/.agents/skills/ask-codex/scripts/ask.sh}"
if [ "${1:-}" = "cancel" ]; then
  [ "$#" -eq 2 ] || {
    echo "cancel requires exactly one run ID" >&2
    exit 2
  }
  run_id="$2"
  case "$run_id" in
    [A-Za-z0-9]*) ;;
    *)
      echo "unsafe Ask run ID" >&2
      exit 2
      ;;
  esac
  case "$run_id" in
    *[!A-Za-z0-9._-]*)
      echo "unsafe Ask run ID" >&2
      exit 2
      ;;
  esac
  [ "${#run_id}" -le 128 ] || {
    echo "unsafe Ask run ID" >&2
    exit 2
  }
  run_root="${ASK_RUN_ROOT:?program-scoped ASK_RUN_ROOT is required for cancel}"
  codex_root="$run_root/codex"
  run_dir="$codex_root/$run_id"
  watchdog="${FABLE_ORCHESTRATOR_WATCHDOG:?controller watchdog is required for cancel}"
  supervision="$run_dir/supervision.json"
  if [ ! -d "$run_root" ] || [ -L "$run_root" ] ||
    [ ! -d "$codex_root" ] || [ -L "$codex_root" ] ||
    [ ! -d "$run_dir" ] || [ -L "$run_dir" ] ||
    ! grep -q '"watchdog_started": true' "$supervision" 2>/dev/null; then
    "$wrapper" cancel "$run_id" >/dev/null 2>&1 || true
    echo "cannot verify canonical Ask run supervision for cancel" >&2
    exit 2
  fi
  test -x "$watchdog"
  output_file="$(mktemp "${TMPDIR:-/tmp}/fable-private-cancel.XXXXXX")"
  trap 'rm -f "$output_file"' EXIT HUP INT TERM
  set +e
  "$wrapper" cancel "$run_id" >"$output_file"
  wrapper_status=$?
  "$watchdog" \
    --wrapper "$wrapper" \
    --run-id "$run_id" \
    --run-dir "$run_dir" \
    --supervision "$supervision" \
    --mode terminate \
    --trigger explicit_cancel \
    --cancel-exit-code "$wrapper_status"
  verification_status=$?
  set -e
  cat "$output_file"
  if [ "$wrapper_status" -ne 0 ]; then
    echo "installed Ask wrapper cancel failed for $run_id" >&2
    exit "$wrapper_status"
  fi
  if [ "$verification_status" -ne 0 ] || [ ! -s "$run_dir/watchdog.json" ]; then
    echo "Ask worker process-group termination was not verified" >&2
    exit 2
  fi
  exit 0
fi
if [ "${1:-}" != "start" ]; then
  exec "$wrapper" "$@"
fi
shim_dir="${FABLE_ORCHESTRATOR_CODEX_SHIM_DIR:?controller Codex shim directory is required}"
watchdog="${FABLE_ORCHESTRATOR_WATCHDOG:?controller watchdog is required}"
timeout_s="${FABLE_ORCHESTRATOR_WATCHDOG_TIMEOUT_S:?watchdog timeout is required}"
test -x "$shim_dir/codex"
test -x "$watchdog"
PATH="$shim_dir:$PATH"
export PATH
output_file="$(mktemp "${TMPDIR:-/tmp}/fable-private-ask.XXXXXX")"
trap 'rm -f "$output_file"' EXIT HUP INT TERM
set +e
"$wrapper" "$@" >"$output_file"
status=$?
set -e
cat "$output_file"
if [ "$status" -ne 0 ]; then
  exit "$status"
fi
run_id="$(sed -n 's/^RUN_ID=//p' "$output_file" | tail -1)"
run_dir="$(sed -n 's/^RUN_DIR=//p' "$output_file" | tail -1)"
if [ -z "$run_id" ] || [ -z "$run_dir" ]; then
  echo "private Ask wrapper returned no RUN_ID/RUN_DIR" >&2
  exit 2
fi
supervision="$run_dir/supervision.json"
identity_waits=0
while ! grep -q '"watchdog_started": true' "$supervision" 2>/dev/null &&
  [ "$identity_waits" -lt 40 ]; do
  sleep 0.05
  identity_waits=$((identity_waits + 1))
done
if ! grep -q '"watchdog_started": true' "$supervision" 2>/dev/null; then
  echo "private Ask launch returned without durable supervision identity" >&2
  "$wrapper" cancel "$run_id" >/dev/null 2>&1 || true
  exit 2
fi
