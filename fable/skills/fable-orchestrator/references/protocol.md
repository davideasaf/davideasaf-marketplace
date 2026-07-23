# Fable Orchestrator Protocol v1

## Charter

Every field is required. Booleans are exact JSON booleans, not strings or numbers.

```json
{
  "workspace": "/absolute/active/worktree",
  "maximum_sandbox": "read-only",
  "max_workers_per_wave": 3,
  "mcps_allowed": false,
  "trusted_mcp_servers": [],
  "mcp_blanket_approval_acknowledged": false,
  "external_mutations_allowed": false,
  "max_worker_timeout_s": 600,
  "max_fable_cycles": 20,
  "max_worker_runs": 30,
  "max_total_worker_seconds": 14400,
  "max_total_input_tokens": 1000000,
  "max_total_output_tokens": 300000,
  "budget_warning_ratio": 0.8
}
```

If `mcps_allowed` is true, `trusted_mcp_servers` must be an exact nonempty list and
`mcp_blanket_approval_acknowledged` must be true. Each MCP-enabled cycle runs
`agent mcp list`; configured servers must be a subset. The installed advisor maps
MCP use to blanket Cursor `--approve-mcps`, so this policy is a fail-closed trust
boundary, not per-tool read-only enforcement. MCP-on therefore also requires
`external_mutations_allowed: true`: the user is authorizing the full mutating
capability of every configured trusted server.

## Private Layout and Integrity

The canonical state root is outside worker authority. Directories are `0700`;
files are `0600`; authority files must not be symlinks.

```text
<program>/
  .controller.lock
  charter.md
  plan.md
  decisions.md
  plans/revision-N.md
  budgets/revision-N.json
  state.json
  ledger.jsonl
  fable-session-id
  cycles/<cycle_id>/{pending-*.txt,attempt-N/*,raw-response.txt,manifest.json}
  ask-runs/codex/<run_id>/{prompt.txt,meta.json,cmd.txt,isolation.json,supervision.json,watchdog.json,final.txt,...}
```

The initialization event anchors SHA-256 hashes of `charter.md`, `plan.md`, and
`decisions.md`. A plan approval creates a new immutable revision file and anchors
its hash in `plan_revision_approved`; it never overwrites `plan.md`.
An approved limit expansion creates `budgets/revision-N.json` and anchors it in
`budget_revision_approved`; the original charter remains immutable.
The random program nonce is stored only in private state and prefixes each worker
prompt together with its dispatch ID and attempt number.

Every mutation holds `.controller.lock`. Ledger sequence is strictly monotonic.
A torn final JSONL record is ignored during replay and truncated under lock before
the next append. Ledger and snapshot writes fsync their file and containing directory.

## Manifest

Fable returns exactly one bare JSON object with no fences or prose:

```json
{
  "protocol_version": "1",
  "cycle_id": 1,
  "program_status": "ready_for_dispatch",
  "summary": "One bounded inspection is ready.",
  "plan_revision": 1,
  "gate": {"kind": "none", "reason": ""},
  "dispatches": [{
    "dispatch_id": "c1.1",
    "objective": "Inspect current implementation.",
    "worker_prompt": "Read named files and report evidence.",
    "acceptance_criteria": ["Cite exact paths"],
    "expected_artifacts": [],
    "touches_shared_foundation": false,
    "requested_sandbox": "read-only",
    "requests_external_mutation": false,
    "timeout_hint_s": 300
  }],
  "chief_of_staff_actions": [{
    "kind": "note",
    "description": "Launch only the validated worker."
  }],
  "next_review_trigger": "When c1.1 is terminal."
}
```

Every initial, ambiguous-turn reconciliation, and one-time schema-repair prompt
contains a compact `EXACT_PROTOCOL_V1_JSON_TEMPLATE` block with all top-level,
gate, dispatch, and action keys and their concrete JSON types. It contains
literal `"protocol_version":"1"` and the current approved integer
`plan_revision`. An adjacent `EXACT_STATUS_GATE_DISPATCH_CARDINALITY` block
machine-describes all four legal status/gate/dispatch-count combinations.
`ALIASES_FORBIDDEN` explicitly rejects `success_criteria`, `sandbox`,
`requests_mcp`, `shared_foundation`, `artifacts`, `timeout_s`, and `notes`.
Repair text includes the observed diagnostic but repeats ALL required exact keys
and types; it never assumes the first validator error is the only defect.
Responses are not normalized or alias-mapped—the strict parser and validator
either accept the exact protocol object or use the bounded repair/gate path.

Coherent status/gate/cardinality combinations are:

| Status | Gate | Dispatches |
|---|---|---|
| `ready_for_dispatch` | `none` | 1–3 |
| `needs_human` | `human_approval` or `authority_expansion` | 0 |
| `blocked` | `blocked` | 0 |
| `complete` | `none` | 0 |

A higher `plan_revision` requires `needs_human`. `depends_on` is forbidden even
when empty. Chief-of-staff actions are non-executable structured notes or human
actions. Required field types and enums are strict; recursive unknown-key paths
are retained in the accepted event.

One `manifest_accepted` ledger event atomically stores the validated manifest,
unknown paths, effective dispatches, deferred/clamped dispatches, derived gate,
and outcome phase. There is no separate authority-derivation transaction.

## Locked State Machine

The main loop is:

```text
initialized -> awaiting_manifest -> dispatch_ready -> workers_running
workers_running -> evidence_ready -> awaiting_manifest
```

Paused/terminal phases are `needs_human`, `blocked`, and `complete`. Phase is
wave-aware: one collected worker does not produce `evidence_ready` while another
effective worker is launching or running. Deferred proposals are explicitly
`deferred` and are not open work.

Active gates are an ordered durable set keyed by `gate_id`. The displayed primary
gate is selected by severity, but every gate remains active until an approval
names that exact ID. Later outcomes cannot overwrite a higher-severity stop.

Only the event table encoded by the controller is accepted. In particular:

- `cycle_started`: `initialized` or `evidence_ready`;
- `manifest_accepted`: `awaiting_manifest`;
- `dispatch_launching`: `dispatch_ready` or `workers_running`;
- `dispatch_collected`: `workers_running` (or collection while a gate is active);
- approval events: `needs_human`.

## Exact Launch Procedure

`prepare-dispatch` records intent first and prints the immutable request:

```bash
umask 077
request_file="$(mktemp)"
launch_output="$(mktemp)"

${CLAUDE_PLUGIN_ROOT}/skills/fable-orchestrator/scripts/orchestrate.py \
  prepare-dispatch PROGRAM_ID c1.1 >"$request_file"

python3 - "$request_file" >"$launch_output" <<'PY'
import json, os, subprocess, sys
request = json.load(open(sys.argv[1], encoding="utf-8"))
env = dict(os.environ)
env.update(request["env"])
completed = subprocess.run(
    [request["wrapper"], *request["argv"]],
    input=request["prompt"],
    text=True,
    env=env,
    check=False,
)
raise SystemExit(completed.returncode)
PY

run_id="$(awk -F= '/^RUN_ID=/{print $2; exit}' "$launch_output")"
test -n "$run_id"
${CLAUDE_PLUGIN_ROOT}/skills/fable-orchestrator/scripts/orchestrate.py \
  record-launch PROGRAM_ID c1.1 "$run_id"
```

The wrapper in the request is `private-ask.sh`; it sets `umask 077`, puts the
controller-owned `codex` shim first in `PATH`, and executes the installed Ask
Codex wrapper. The shim verifies real CLI support and injects
`--ignore-user-config` immediately after `codex exec`. The actual isolated
command replaces `cmd.txt`; `isolation.json` must match the request and declare
zero user-configured external capabilities. The request environment sets
`ASK_RUN_ROOT=<program>/ask-runs`, producing the canonical path
`<program>/ask-runs/codex/<run-id>`.
The marker is followed by a controller-authored boundary containing objective,
workspace, sandbox, external-mutation decision, acceptance criteria, expected
artifacts, and a prohibition on treating the Fable-authored worker brief as an
authority override.

Keep `request_file` and `launch_output` private until launch is recorded, then
delete them using the operator's normal safe cleanup procedure. If the Python
launcher outcome is ambiguous, do not run it again; use:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/fable-orchestrator/scripts/orchestrate.py \
  reconcile PROGRAM_ID c1.1
```

One match is adopted. Multiple matches produce a durable `launch_ambiguity` gate.
No match produces `dispatch_reconciled_no_match` and prints the byte-identical
launch request. A repeated no-match reconciliation prints those same bytes.
The worker-run and `reserved_worker_seconds` reservations made at
`dispatch_launching` remain active through `retry_ready` and no-match re-emission.

Before the real worker can execute, the controller-owned `codex` shim calls
`setsid`, making its PID the process-group ID, writes that identity and deadline
to private `supervision.json`, and starts the watchdog in a separate session.
The private launcher waits briefly for this durable identity and fails closed if
it is absent. If the run remains active at the hard deadline, the watchdog invokes
the installed Ask wrapper's `cancel` command, sends TERM and then bounded KILL to
the recorded process group when necessary, and verifies both the PID and all
group members are gone. Private `watchdog.json` records the PID/PGID, signals,
grace period, and final liveness; deadline enforcement is false unless the
installed cancel succeeds and no process-group member remains.

An explicit cancel must also use `private-ask.sh`, with the same program-scoped
`ASK_RUN_ROOT`. The shim locates the canonical run, invokes the installed
wrapper's state/cancel path, then calls the shared group terminator. It reports
success only after `watchdog.json` records `trigger: "explicit_cancel"`,
`termination_verified: true`, and an empty final PID/process-group inventory.
Missing canonical supervision or termination evidence fails closed. Separately,
the long-running monitor never trusts a cancelled status by itself: if it
observes that status, it verifies or terminates the recorded worker group before
exiting.

To monitor, take `ASK_RUN_ROOT` from the saved request and use the same shim:

```bash
ASK_RUN_ROOT="/absolute/program/ask-runs" \
  ${CLAUDE_PLUGIN_ROOT}/skills/fable-orchestrator/scripts/private-ask.sh status "$run_id"
ASK_RUN_ROOT="/absolute/program/ask-runs" \
  ${CLAUDE_PLUGIN_ROOT}/skills/fable-orchestrator/scripts/private-ask.sh tail "$run_id" -n 20
ASK_RUN_ROOT="/absolute/program/ask-runs" \
  ${CLAUDE_PLUGIN_ROOT}/skills/fable-orchestrator/scripts/private-ask.sh cancel "$run_id"
```

When terminal, create private result input containing only controller inputs:

```json
{
  "dispatch_id": "c1.1",
  "run_id": "20260723-120000-abcdef",
  "artifacts": [],
  "output_kind": "verbatim"
}
```

Then run:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/fable-orchestrator/scripts/orchestrate.py \
  record-result PROGRAM_ID /private/path/result.json
```

The controller audits the full canonical run tree and derives prompt hash,
marker, workspace, sandbox, terminal status, exit code, thread ID, duration,
tokens, and final output. Input and output token telemetry are required; missing
telemetry raises a durable `missing_provenance` gate rather than counting zero.
`done` requires exit 0 and nonblank output;
`empty-output` requires exit 0 and blank output; contradictory provenance fails.
For a Codex-authored digest, set `output_kind` to `codex_digest` and add a
nonblank bounded `digest` field. The controller stores the digest while retaining
the original worker-output SHA-256 and byte count. `digest` is forbidden for
`verbatim`. Verbatim ledger storage is a bounded excerpt plus the raw byte count,
SHA-256, and canonical `final.txt` path.

## Approval Commands

General human or budget-warning gate:

```bash
orchestrate.py approve PROGRAM_ID \
  --gate-id GATE_ID \
  --note "Sponsor approved continuation."
```

Launch ambiguity:

```bash
orchestrate.py approve PROGRAM_ID \
  --gate-id GATE_ID \
  --adopt-run-id RUN_ID \
  --note "Sponsor selected the verified canonical run."
```

Gated plan revision:

```bash
orchestrate.py approve-plan PROGRAM_ID \
  --gate-id GATE_ID \
  --revision 2 \
  --plan /absolute/approved-plan-v2.md \
  --note "Sponsor approved revision 2."
```

`approve-plan` accepts only the exact manifest-derived plan gate ID recorded for
the proposed revision. A simultaneous budget or other gate ID is rejected before
any revision file or ledger event is written.

First worker failure permits one explicit retry:

```bash
orchestrate.py approve-retry PROGRAM_ID c1.1 \
  --gate-id GATE_ID \
  --note "One bounded retry approved after reviewing evidence."
```

A second failure cannot use `approve-retry`. `schema_failure` is not approvable.

Hard-limit or warning continuation uses an immutable budget revision:

```bash
orchestrate.py approve-budget PROGRAM_ID \
  --gate-id GATE_ID \
  --revision 2 \
  --budget /absolute/budget-v2.json \
  --note "Sponsor approved bounded expansion."
```

## Durable Event Types

- `program_initialized`
- `cycle_started`
- `fable_turn_started`
- `fable_turn_completed`
- `fable_turn_lease_reconciled`
- `fable_transport_failed`
- `manifest_invalid`
- `session_replaced`
- `manifest_accepted`
- `dispatch_launching`
- `dispatch_reconciled_no_match`
- `dispatch_launched`
- `dispatch_adopted`
- `dispatch_collected`
- `gate_raised`
- `approval_granted`
- `plan_revision_approved`
- `budget_revision_approved`
- `dispatch_retry_approved`

No undocumented `checkpoint` event is required; every accepted event is itself
the crash-replay checkpoint.

## Fable Recovery and Cold Start

Before each external Fable call, the controller acquires a durable single-turn
lease and persists the exact next
reconciliation prompt and its hash. A crash or ambiguous transport failure
therefore makes the next `cycle` automatically resume:

> If cycle N was already processed, re-emit its exact manifest; otherwise process
> the supplied checkpoint. Do not increment the cycle.

After one invalid manifest, the exact repair prompt is persisted. An interruption
uses that byte-identical remaining repair turn. A second invalid response gates.

A live lease blocks a duplicate turn. A stale owner must be reconciled explicitly:

```bash
orchestrate.py reconcile-turn PROGRAM_ID \
  --lease-id LEASE_ID \
  --note "Controller process is no longer live."
```

The active Fable session is derived from ledger events. `fable-session-id` is
only a verified cache and is rebuilt when it differs.

Cold-start prompts include bounded charter, current approved plan, decision record,
accepted-event digest, complete open-dispatch contracts, provenance, and explicit
`UNTRUSTED_WORKER_EVIDENCE` labels. Large worker output is truncated with original
byte count and SHA-256 digest. Open dispatches use per-field structured truncation:
every dispatch retains its ID, objective, criteria, effective authority, prompt
hash, and whole-record content digest. A manifest is rejected when the minimum
complete structured checkpoint cannot fit.
