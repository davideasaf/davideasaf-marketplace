---
name: fable-orchestrator
description: Use when the user asks Codex to manage a large multi-workstream project with Fable 5 as orchestrator, especially work expected to span hours or days.
---

# Fable Orchestrator

Codex is chief of staff and durable control plane. Fable proposes decomposition,
sequencing, worker briefs, acceptance criteria, and next waves. Ask Codex workers
perform bounded assignments.

Use `fable-advisor` for one difficult decision. Use this skill for a sustained
program with multiple workstreams. **Fable proposes; Codex launches.**

## Authority

| Actor | Owns |
|---|---|
| User | Objective, measurable budgets, approvals, external authority |
| Codex | Source of truth, permissions, workspace/worktrees, worker processes, recovery, communication |
| Fable | Declarative manifests, synthesis, proposed next wave |
| Worker | One bounded assignment and provenance-labelled evidence |

Never give Fable direct shell, worker-process, worktree, MCP, or mutation authority.
The private state root must be outside the active workspace or worktree.

## Start

1. Write a strict JSON charter, approved plan, and immutable decision record.
2. Ask `fable-advisor` to critique the plan and record accepted/rejected advice.
3. Start Fable as orchestrator in a **separate session**:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/fable-orchestrator/scripts/orchestrate.py init \
  --workspace /absolute/project/path \
  --charter /absolute/charter.json \
  --plan /absolute/plan.md \
  --decisions /absolute/decisions.md
```

The charter must include exact booleans, MCP policy, external-mutation policy,
worker/cycle limits, time and token budgets, and a warning ratio. Copy the charter
schema from [references/protocol.md](references/protocol.md).

MCPs are disabled by default and by every cycle unless `--with-mcps` is explicit
and within user authorization.
That option is accepted only when the charter lists exact trusted servers,
acknowledges Cursor's blanket `--approve-mcps` risk, and current
`agent mcp list` servers are a subset. Because the wrapper grants blanket MCP
approval, MCP-on also requires explicit authorization for the full mutating capability
of every configured trusted server. Keep MCP off for a
mutation-prohibited program.

## Bounded Loop

1. The controller accepts one strict protocol-v1 manifest and atomically derives
   its human gate, effective wave, and deferred dispatches.
   Every initial, reconciliation, and repair prompt embeds the same compact
   `EXACT_PROTOCOL_V1_JSON_TEMPLATE` and
   `EXACT_STATUS_GATE_DISPATCH_CARDINALITY` blocks. The template uses literal
   `"protocol_version":"1"`, the current integer plan revision, exact dispatch
   keys/types, and structured chief-of-staff actions. `ALIASES_FORBIDDEN` names
   common near-miss keys. A repair repeats ALL required exact keys and types,
   not only the first validation error. Never normalize a near-miss response;
   the strict parser and validator remain the authority boundary.
2. Run `prepare-dispatch <program> <dispatch_id>`. It writes
   `dispatch_launching`, reserves one run plus its timeout, and prints an exact
   launch request.
3. Execute that request through the private umask shim, then run `record-launch`.
   Follow the copy-safe procedure in the protocol reference; do not improvise
   arguments or environment merging. The shim puts a controller-owned `codex`
   first in `PATH`, injects `--ignore-user-config` immediately after `codex exec`,
   and fails closed unless the CLI proves support. `cmd.txt` and `isolation.json`
   must prove zero user-configured external capabilities. Before executing the
   real worker, the shim uses `setsid`, durably records its PID/PGID in
   `supervision.json`, and starts the watchdog outside that process group.
4. Monitor with the same program-scoped `ASK_RUN_ROOT`. When terminal, submit only
   `dispatch_id`, `run_id`, `artifacts`, and `output_kind` to `record-result`.
   The controller derives status, output, IDs, duration, tokens, and prompt hash
   from canonical Ask run artifacts. A controller watchdog enforces the hard
   deadline, cancels through the installed wrapper, sends bounded TERM/KILL to
   the recorded process group when needed, verifies no members remain, and
   records `watchdog.json`.
   Use the private shim for explicit cancel as well: it delegates state changes
   to the installed wrapper, then requires `termination_verified` group evidence
   before reporting success. The monitor also treats a cancelled status as a
   liveness claim to verify, not as proof that the worker stopped.
   Missing token telemetry is a `missing_provenance` stop gate.
5. After every effective dispatch is collected, run `cycle` again. Cold-start
   context is bounded and labels worker output as untrusted data.

Shared foundation (`shared-foundation`) work serializes the wave. Every dispatch explicitly declares
whether it requests external mutation; authority is clamped or gated by charter.

## Gates and Recovery

`needs_human`, `blocked`, `complete`, `dispatch_ready`, and `workers_running`
cannot start another Fable cycle. Active gates are an ordered durable set keyed
by `gate_id`; a later lower-severity outcome cannot overwrite an earlier stop.
Every approval names exactly one gate:

- `approve --gate-id ID --note ...` for a general gate; launch ambiguity also requires
  `--adopt-run-id`.
- `approve-plan --gate-id ID --revision N --plan FILE --note ...` only for the
  exact manifest-derived plan gate and proposed revision.
- `approve-retry DISPATCH --gate-id ID --note ...` for one bounded worker retry.
- `approve-budget --gate-id ID --revision N --budget FILE --note ...` for an
  immutable budget revision.

`schema_failure` is not approvable. A live Fable external-turn lease blocks a
duplicate cycle. If its owner is gone, use
`reconcile-turn --lease-id ID --note ...`; stale recovery is never implicit.

The program directory—not chat or the Fable session—is the source of truth.
`ledger.jsonl` replays through a locked transition table; authority hashes are
verified on every operational command.

After `dispatch_launching`, run `reconcile` before any uncertain retry:

- one matching canonical run is adopted;
- multiple matches durably raise a human gate;
- no match durably records that disposition and re-emits the byte-identical request.

Fable timeouts and crashes automatically resume from the persisted reconciliation
prompt for the same `cycle_id`. An interrupted schema repair resumes the exact
remaining repair prompt. One repair is allowed; the next invalid manifest gates.
The session sidecar is only a cache: ledger truth rebuilds it. Cold-start open
dispatches use per-field structured truncation so every dispatch retains its ID,
objective, criteria, effective authority, prompt hash, and content digest.

## Stop

Stop at authority expansion, a hard or warning budget gate, consequential plan
revision, repeated worker/schema failure, conflicting evidence, missing provenance,
permission-audit failure, or unreconciled launch ambiguity.

Budget state includes Fable cycles, reserved runs, `reserved_worker_seconds`,
actual worker time, and required input/output token telemetry. Reservations survive
no-match re-emission and reconcile to measured use only at collection.

Read [references/protocol.md](references/protocol.md) before the first live program.
