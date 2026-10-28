#!/usr/bin/env bash

set -euo pipefail

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)/ask.sh"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ask-codex-tests.XXXXXX")"
TEST_COUNT=0
trap 'rm -rf "$TEST_ROOT"' EXIT

fail() { printf 'not ok - %s\n' "$1" >&2; exit 1; }
pass() { TEST_COUNT=$((TEST_COUNT + 1)); printf 'ok %d - %s\n' "$TEST_COUNT" "$1"; }

setup_fixture() {
  local name="$1"
  FIXTURE="$TEST_ROOT/$name"
  BIN_DIR="$FIXTURE/bin"
  HOME_DIR="$FIXTURE/home"
  RUN_ROOT="$FIXTURE/runs"
  PROJECT_DIR="$FIXTURE/project"
  LAUNCHCTL_LOG="$FIXTURE/launchctl.log"
  mkdir -p "$BIN_DIR" "$HOME_DIR" "$RUN_ROOT" "$PROJECT_DIR"
  : > "$LAUNCHCTL_LOG"

  cat > "$BIN_DIR/codex" <<'FAKE_CODEX'
#!/usr/bin/env bash
final=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) final="$2"; shift 2;;
    *) shift;;
  esac
done
cat >/dev/null
[[ -n "$final" ]] && printf '%s\n' 'fake codex answer' > "$final"
printf '%s\n' '{"type":"thread.started","thread_id":"test-thread"}'
printf '%s\n' '{"type":"turn.completed","usage":{"input_tokens":1,"cached_input_tokens":0,"output_tokens":2,"reasoning_output_tokens":0}}'
FAKE_CODEX
  chmod +x "$BIN_DIR/codex"

  cat > "$BIN_DIR/launchctl" <<'FAKE_LAUNCHCTL'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$LAUNCHCTL_LOG"
case "${1:-}" in
  submit)
    shift
    while [[ $# -gt 0 && "$1" != "--" ]]; do shift; done
    [[ "${1:-}" == "--" ]] && shift
    "$@" &
    ;;
  remove)
    ;;
esac
FAKE_LAUNCHCTL
  chmod +x "$BIN_DIR/launchctl"
  export FIXTURE BIN_DIR HOME_DIR RUN_ROOT PROJECT_DIR LAUNCHCTL_LOG
}

run_wrapper() {
  env HOME="$HOME_DIR" ASK_RUN_ROOT="$RUN_ROOT" LAUNCHCTL_LOG="$LAUNCHCTL_LOG" \
    PATH="$BIN_DIR:/usr/bin:/bin:/usr/sbin:/sbin" "$SCRIPT" "$@"
}

only_run_dir() { find "$RUN_ROOT/codex" -mindepth 1 -maxdepth 1 -type d -print | head -n1; }

test_blocking_ask_avoids_launchctl() {
  setup_fixture blocking-ask
  run_wrapper ask "review this" "$PROJECT_DIR" >"$FIXTURE/stdout" 2>"$FIXTURE/stderr" || fail "blocking ask should succeed"
  [[ "$(cat "$FIXTURE/stdout")" == "fake codex answer" ]] || fail "blocking ask should print final answer"
  [[ ! -s "$LAUNCHCTL_LOG" ]] || fail "blocking ask must not invoke launchctl"
  local dir="$(only_run_dir)"
  [[ "$(jq -r .status "$dir/meta.json")" == "done" && "$(cat "$dir/exit_code")" == "0" ]] || fail "blocking ask should finalize successfully"
  [[ "$(jq -r .model "$dir/meta.json")" == "gpt-6.1-sol" ]] || fail "default model should be GPT-6.1-Sol"
  [[ "$(jq -r .effort "$dir/meta.json")" == "xhigh" ]] || fail "default reasoning effort should be xhigh"
  pass "blocking ask completes without launchctl"
}

test_managed_run_avoids_launchctl() {
  setup_fixture managed-run
  run_wrapper run "review this" "$PROJECT_DIR" >"$FIXTURE/stdout" 2>"$FIXTURE/stderr" || fail "managed run should succeed"
  local run_id="$(awk -F= '/^RUN_ID=/{print $2; exit}' "$FIXTURE/stdout")"
  [[ -n "$run_id" ]] || fail "managed run should print RUN_ID"
  [[ ! -s "$LAUNCHCTL_LOG" ]] || fail "managed run must not invoke launchctl"
  [[ "$(jq -r .status "$RUN_ROOT/codex/$run_id/meta.json")" == "done" ]] || fail "managed run should finalize"
  pass "managed run completes without launchctl"
}

test_start_requires_opt_in() {
  setup_fixture start-gated
  if run_wrapper start "review this" "$PROJECT_DIR" >"$FIXTURE/stdout" 2>"$FIXTURE/stderr"; then fail "start should fail without opt-in"; fi
  rg -q 'ASK_ALLOW_LAUNCHCTL=1' "$FIXTURE/stderr" || fail "start should explain opt-in"
  [[ ! -s "$LAUNCHCTL_LOG" ]] || fail "gated start must not invoke launchctl"
  [[ "$(find "$RUN_ROOT/codex" -mindepth 1 -maxdepth 1 -type d -print | wc -l | tr -d ' ')" == "0" ]] || fail "gated start should create no run"
  pass "start fails closed without launchctl opt-in"
}

test_opted_in_start() {
  setup_fixture start-opted-in
  ASK_ALLOW_LAUNCHCTL=1 run_wrapper start "review this" "$PROJECT_DIR" >"$FIXTURE/stdout" 2>"$FIXTURE/stderr" || fail "opted-in start should submit"
  local run_id="$(awk -F= '/^RUN_ID=/{print $2; exit}' "$FIXTURE/stdout")"
  ASK_ALLOW_LAUNCHCTL=1 run_wrapper wait "$run_id" --timeout 10 >"$FIXTURE/result" 2>>"$FIXTURE/stderr" || fail "opted-in run should finish"
  rg -q '^submit -l com\.ask-codex\.' "$LAUNCHCTL_LOG" || fail "opted-in start should submit"
  rg -q '^remove com\.ask-codex\.' "$LAUNCHCTL_LOG" || fail "opted-in runner should remove job"
  [[ "$(cat "$FIXTURE/result")" == "fake codex answer" ]] || fail "opted-in result should be preserved"
  pass "explicit opt-in retains launchctl compatibility"
}

test_computer_use_defaults_to_terra() {
  setup_fixture computer-use
  run_wrapper ask --computer-use "open a page" "$PROJECT_DIR" >"$FIXTURE/stdout" 2>"$FIXTURE/stderr" || fail "computer-use ask should succeed"
  local dir="$(only_run_dir)"
  [[ "$(jq -r .model "$dir/meta.json")" == "gpt-6.1-terra" ]] || fail "computer use should default to GPT-6.1-Terra"
  [[ "$(jq -r .effort "$dir/meta.json")" == "max" ]] || fail "computer use should default to max effort"
  setup_fixture computer-use-explicit
  run_wrapper ask --model SOL --computer-use --effort low "open a page" "$PROJECT_DIR" >"$FIXTURE/stdout" 2>"$FIXTURE/stderr" || fail "explicit computer-use ask should succeed"
  dir="$(only_run_dir)"
  [[ "$(jq -r .model "$dir/meta.json")" == "gpt-6.1-sol" ]] || fail "explicit model should win over the computer-use default"
  [[ "$(jq -r .effort "$dir/meta.json")" == "low" ]] || fail "explicit effort should win over the computer-use default"
  pass "computer use defaults to Terra max and keeps explicit choices"
}

test_skip_git_check_only_outside_git_or_trust() {
  setup_fixture skip-git-untrusted
  local config="$FIXTURE/config.toml" real
  : > "$config"
  CODEX_CONFIG="$config" run_wrapper ask "review this" "$PROJECT_DIR" >"$FIXTURE/stdout" 2>"$FIXTURE/stderr" || fail "untrusted non-git ask should succeed"
  local dir="$(only_run_dir)"
  rg -q -- '--skip-git-repo-check' "$dir/cmd.txt" || fail "untrusted non-git dir should get --skip-git-repo-check"
  [[ "$(jq -r .skip_git_repo_check "$dir/meta.json")" == "true" ]] || fail "meta should record the skip"
  setup_fixture skip-git-repo
  config="$FIXTURE/config.toml"; : > "$config"
  git -C "$PROJECT_DIR" init -q || fail "git init should succeed"
  CODEX_CONFIG="$config" run_wrapper ask "review this" "$PROJECT_DIR" >"$FIXTURE/stdout" 2>"$FIXTURE/stderr" || fail "git ask should succeed"
  dir="$(only_run_dir)"
  ! rg -q -- '--skip-git-repo-check' "$dir/cmd.txt" || fail "git dir should not get --skip-git-repo-check"
  [[ "$(jq -r '.skip_git_repo_check // false' "$dir/meta.json")" == "false" ]] || fail "meta should omit the skip for a git dir"
  setup_fixture skip-git-trusted
  config="$FIXTURE/config.toml"; real="$(cd "$PROJECT_DIR" && pwd -P)"
  printf '[projects."%s"]\ntrust_level = "trusted"\n' "$real" > "$config"
  CODEX_CONFIG="$config" run_wrapper ask "review this" "$PROJECT_DIR" >"$FIXTURE/stdout" 2>"$FIXTURE/stderr" || fail "trusted ask should succeed"
  dir="$(only_run_dir)"
  ! rg -q -- '--skip-git-repo-check' "$dir/cmd.txt" || fail "trusted dir should not get --skip-git-repo-check"
  pass "skip-git-repo-check added only for untrusted non-git dirs"
}

printf '1..6\n'
FILTER="${1:-}"
[[ -z "$FILTER" || "$FILTER" == blocking-ask ]] && test_blocking_ask_avoids_launchctl
[[ -z "$FILTER" || "$FILTER" == managed-run ]] && test_managed_run_avoids_launchctl
[[ -z "$FILTER" || "$FILTER" == start-gated ]] && test_start_requires_opt_in
[[ -z "$FILTER" || "$FILTER" == start-opted-in ]] && test_opted_in_start
[[ -z "$FILTER" || "$FILTER" == computer-use ]] && test_computer_use_defaults_to_terra
[[ -z "$FILTER" || "$FILTER" == skip-git ]] && test_skip_git_check_only_outside_git_or_trust
exit 0
