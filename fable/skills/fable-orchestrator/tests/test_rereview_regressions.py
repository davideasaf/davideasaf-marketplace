import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "orchestrate.py"
SPEC = importlib.util.spec_from_file_location("fable_orchestrate_rereview", SCRIPT)
orchestrate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(orchestrate)


def charter(workspace: Path, **overrides):
    value = {
        "workspace": str(workspace.resolve()),
        "maximum_sandbox": "read-only",
        "max_workers_per_wave": 3,
        "mcps_allowed": False,
        "trusted_mcp_servers": [],
        "mcp_blanket_approval_acknowledged": False,
        "external_mutations_allowed": False,
        "max_worker_timeout_s": 60,
        "max_fable_cycles": 10,
        "max_worker_runs": 10,
        "max_total_worker_seconds": 600,
        "max_total_input_tokens": 100_000,
        "max_total_output_tokens": 50_000,
        "budget_warning_ratio": 1.0,
    }
    value.update(overrides)
    return value


def dispatch(index=1, **overrides):
    value = {
        "dispatch_id": f"c1.{index}",
        "objective": f"OBJECTIVE-{index}",
        "worker_prompt": f"PROMPT-{index}",
        "acceptance_criteria": [f"CRITERION-{index}"],
        "expected_artifacts": [],
        "touches_shared_foundation": False,
        "requested_sandbox": "read-only",
        "requests_external_mutation": False,
        "timeout_hint_s": 60,
    }
    value.update(overrides)
    return value


def manifest(dispatches=None):
    return {
        "protocol_version": "1",
        "cycle_id": 1,
        "program_status": "ready_for_dispatch",
        "summary": "Bounded wave.",
        "plan_revision": 1,
        "gate": {"kind": "none", "reason": ""},
        "dispatches": dispatches or [dispatch()],
        "chief_of_staff_actions": [{"kind": "note", "description": "Launch."}],
        "next_review_trigger": "After collection.",
    }


def make_program(base: Path, **overrides):
    workspace = base / "repo"
    workspace.mkdir()
    state_root = base / "state"
    program = orchestrate.create_program(
        root=state_root,
        workspace=workspace,
        charter=charter(workspace, **overrides),
        plan="Plan.",
        decisions="Decision.",
        program_id="demo",
    )
    return program, workspace, state_root


def accept(program: Path, value=None):
    orchestrate.append_event(program, {"type": "cycle_started", "cycle_id": 1})
    orchestrate.accept_manifest(program, value or manifest())


def write_run(program: Path, request: dict, run_id: str, *, tokens=True, output="ok"):
    run = program / "ask-runs" / "codex" / run_id
    run.mkdir(parents=True, mode=0o700)
    (run / "prompt.txt").write_text(request["prompt"])
    meta = {
        "status": "done",
        "project_dir": request["workspace"],
        "sandbox": request["effective_sandbox"],
        "session_id": "thread",
        "exit_code": 0,
        "duration_seconds": 1.0,
    }
    if tokens:
        meta.update({"input_tokens": 4, "output_tokens": 2})
    (run / "meta.json").write_text(json.dumps(meta))
    (run / "final.txt").write_text(output)
    (run / "cmd.txt").write_text(
        f"{request['isolation']['real_codex']} exec --ignore-user-config "
        "-s read-only --json -o final.txt -\n"
    )
    (run / "isolation.json").write_text(
        json.dumps(request.get("isolation", {}), sort_keys=True)
    )
    (run / "supervision.json").write_text(
        json.dumps(
            {
                "mode": request["watchdog"]["mode"],
                "identity_ready": True,
                "watchdog_started": True,
                "recorded_before_exec": True,
                "target_pid": 424242,
                "target_pgid": 424242,
                "watchdog_pid": 424243,
                "run_id": run_id,
                "real_codex": request["isolation"]["real_codex"],
                "codex_shim_sha256": request["isolation"]["codex_shim_sha256"],
                "timeout_s": request["watchdog"]["timeout_s"],
                "grace_s": request["watchdog"]["grace_s"],
                "deadline_epoch": time.time() + request["watchdog"]["timeout_s"],
            },
            sort_keys=True,
        )
    )
    for path in run.rglob("*"):
        path.chmod(0o700 if path.is_dir() else 0o600)
    run.chmod(0o700)
    (program / "ask-runs" / "codex").chmod(0o700)
    return run


class IsolationAndBudgetTests(unittest.TestCase):
    def test_launch_request_requires_ignored_user_config_and_watchdog(self):
        with tempfile.TemporaryDirectory() as tmp:
            program, _, _ = make_program(Path(tmp))
            accept(program)
            request = orchestrate.prepare_dispatch_by_id(program, "c1.1")
            self.assertTrue(request["isolation"]["ignore_user_config"])
            self.assertEqual(request["isolation"]["external_capabilities"], [])
            self.assertEqual(request["watchdog"]["timeout_s"], 60)
            self.assertEqual(request["watchdog"]["mode"], "setsid_process_group")
            self.assertTrue(request["watchdog"]["started_before_exec"])
            self.assertEqual(request["watchdog"]["supervision_file"], "supervision.json")
            self.assertIn("FABLE_ORCHESTRATOR_REAL_CODEX", request["env"])
            self.assertIn("FABLE_ORCHESTRATOR_WATCHDOG", request["env"])

    def test_launching_and_no_match_retain_run_and_time_reservations(self):
        with tempfile.TemporaryDirectory() as tmp:
            program, _, _ = make_program(
                Path(tmp), max_worker_runs=1, max_total_worker_seconds=60
            )
            accept(program, manifest([dispatch(1), dispatch(2)]))
            orchestrate.prepare_dispatch_by_id(program, "c1.1")
            state = orchestrate.replay_ledger(program)
            self.assertEqual(state["budget"]["worker_runs"], 1)
            self.assertEqual(state["budget"]["reserved_worker_seconds"], 60)
            orchestrate.reconcile_dispatch(program, dispatch_id="c1.1")
            state = orchestrate.replay_ledger(program)
            self.assertEqual(state["budget"]["worker_runs"], 1)
            self.assertEqual(state["budget"]["reserved_worker_seconds"], 60)
            with self.assertRaisesRegex(orchestrate.ProtocolError, "budget"):
                orchestrate.prepare_dispatch_by_id(program, "c1.2")

    def test_missing_token_telemetry_durably_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            program, _, _ = make_program(Path(tmp))
            accept(program)
            request = orchestrate.prepare_dispatch_by_id(program, "c1.1")
            write_run(program, request, "run-1", tokens=False)
            orchestrate.record_launch(program, dispatch_id="c1.1", run_id="run-1")
            with self.assertRaisesRegex(orchestrate.ProtocolError, "token"):
                orchestrate.collect_run_result(
                    program,
                    dispatch_id="c1.1",
                    run_id="run-1",
                    artifacts=[],
                    output_kind="verbatim",
                )
            kinds = [gate["kind"] for gate in orchestrate.replay_ledger(program)["gates"]]
            self.assertIn("missing_provenance", kinds)

    def test_fable_cycles_participate_in_warning_and_budget_revision_is_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            program, _, _ = make_program(
                Path(tmp), max_fable_cycles=2, budget_warning_ratio=0.5
            )
            with self.assertRaisesRegex(orchestrate.ProtocolError, "warning"):
                orchestrate.start_cycle(program, 1)
            state = orchestrate.replay_ledger(program)
            gate = next(g for g in state["gates"] if g["kind"] == "budget_warning")
            limits = dict(state["budget_limits"])
            limits["max_fable_cycles"] = 4
            orchestrate.approve_budget_revision(
                program,
                gate_id=gate["gate_id"],
                revision=2,
                limits=limits,
                note="Sponsor raised the immutable limit.",
            )
            state = orchestrate.replay_ledger(program)
            self.assertEqual(state["budget_limits"]["max_fable_cycles"], 4)
            self.assertTrue((program / "budgets" / "revision-2.json").is_file())
            orchestrate.verify_program_integrity(program)


class GateAndLeaseTests(unittest.TestCase):
    def test_stop_gates_are_ordered_and_severity_preserved_in_both_orders(self):
        for order in (
            ("repeated_worker_failure", "worker_failure"),
            ("worker_failure", "repeated_worker_failure"),
        ):
            with self.subTest(order=order), tempfile.TemporaryDirectory() as tmp:
                program, _, _ = make_program(Path(tmp))
                for kind in order:
                    orchestrate.append_event(
                        program,
                        {
                            "type": "gate_raised",
                            "gate": {
                                "kind": kind,
                                "reason": kind,
                                "dispatch_id": f"d-{kind}",
                            },
                        },
                    )
                state = orchestrate.replay_ledger(program)
                self.assertEqual([g["kind"] for g in state["gates"]], list(order))
                self.assertEqual(state["gate"]["kind"], "repeated_worker_failure")

    def test_approval_requires_exact_gate_id_and_schema_failure_is_not_approvable(self):
        with tempfile.TemporaryDirectory() as tmp:
            program, _, _ = make_program(Path(tmp))
            orchestrate.append_event(
                program,
                {
                    "type": "gate_raised",
                    "gate": {"kind": "schema_failure", "reason": "exhausted"},
                },
            )
            gate_id = orchestrate.replay_ledger(program)["gate"]["gate_id"]
            with self.assertRaises(TypeError):
                orchestrate.approve_gate(program, note="missing id")
            with self.assertRaisesRegex(orchestrate.ProtocolError, "schema"):
                orchestrate.approve_gate(
                    program, gate_id=gate_id, note="cannot approve"
                )

    def test_live_fable_turn_lease_blocks_duplicate_and_stale_requires_reconcile(self):
        with tempfile.TemporaryDirectory() as tmp:
            program, _, _ = make_program(Path(tmp))
            orchestrate.start_cycle(program, 1)
            lease = orchestrate.acquire_fable_turn_lease(
                program, cycle_id=1, controller_pid=os.getpid()
            )
            with self.assertRaisesRegex(orchestrate.ProtocolError, "lease"):
                orchestrate.acquire_fable_turn_lease(
                    program, cycle_id=1, controller_pid=os.getpid()
                )
            with mock.patch.object(orchestrate, "_pid_is_live", return_value=False):
                with self.assertRaisesRegex(orchestrate.ProtocolError, "reconcile"):
                    orchestrate.acquire_fable_turn_lease(
                        program, cycle_id=1, controller_pid=999_999
                    )
                orchestrate.reconcile_fable_turn_lease(
                    program, lease_id=lease["lease_id"], note="Owner is gone."
                )
            self.assertIsNone(orchestrate.replay_ledger(program).get("turn_lease"))

    def test_plan_approval_rejects_unrelated_budget_gate_without_any_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            program, _, _ = make_program(Path(tmp))
            value = manifest()
            value["dispatches"] = []
            value.update(
                {
                    "program_status": "needs_human",
                    "plan_revision": 2,
                    "gate": {
                        "kind": "human_approval",
                        "reason": "Approve plan revision two.",
                    },
                }
            )
            orchestrate.append_event(program, {"type": "cycle_started", "cycle_id": 1})
            orchestrate.accept_manifest(program, value)
            plan_gate = orchestrate.replay_ledger(program)["gate"]
            orchestrate.append_event(
                program,
                {
                    "type": "gate_raised",
                    "gate": {
                        "kind": "budget_warning",
                        "reason": "Independent budget warning.",
                    },
                },
            )
            before_state = orchestrate.replay_ledger(program)
            before_plan = (program / "plan.md").read_bytes()
            budget_gate = next(
                gate
                for gate in before_state["gates"]
                if gate["kind"] == "budget_warning"
            )
            with self.assertRaisesRegex(orchestrate.ProtocolError, "plan gate"):
                orchestrate.approve_plan_revision(
                    program,
                    gate_id=budget_gate["gate_id"],
                    revision=2,
                    plan_text="Plan revision two.",
                    note="Wrong gate must not work.",
                )
            after_state = orchestrate.replay_ledger(program)
            self.assertEqual(after_state, before_state)
            self.assertEqual((program / "plan.md").read_bytes(), before_plan)
            self.assertFalse((program / "plans" / "revision-2.md").exists())
            self.assertIn(plan_gate["gate_id"], [g["gate_id"] for g in after_state["gates"]])
            self.assertIn(budget_gate["gate_id"], [g["gate_id"] for g in after_state["gates"]])


class IntegrityCheckpointAndProvenanceTests(unittest.TestCase):
    def test_program_moved_under_workspace_is_rejected_on_every_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            program, workspace, _ = make_program(base)
            moved = workspace / "controller-state"
            program.rename(moved)
            with self.assertRaisesRegex(orchestrate.ProtocolError, "workspace"):
                orchestrate.verify_program_integrity(moved)

    def test_every_open_dispatch_survives_structured_checkpoint_bounds(self):
        huge = "X" * 32_000
        opened = []
        for index in range(1, 4):
            opened.append(
                {
                    "dispatch_id": f"c1.{index}",
                    "state": "ready",
                    "objective": f"OBJECTIVE-{index}-" + huge,
                    "worker_prompt": f"PROMPT-{index}-" + huge,
                    "acceptance_criteria": [f"CRITERION-{index}-" + huge],
                    "effective": {
                        "workspace": "/repo",
                        "effective_sandbox": "read-only",
                        "timeout_s": 60,
                        "external_mutation_authorized": False,
                    },
                    "prompt_hash": str(index) * 64,
                }
            )
        prompt = orchestrate.build_cold_start_prompt(
            charter_text="{}",
            plan_text="plan",
            decision_text="decision",
            ledger_digest="digest",
            open_dispatches=opened,
            evidence=[],
            cycle_id=2,
        )
        section = prompt.split("COMPLETE BOUNDED OPEN-DISPATCH CONTRACTS\n", 1)[1]
        rendered = section.split("\n\nUNTRUSTED_WORKER_EVIDENCE", 1)[0]
        parsed = json.loads(rendered)
        self.assertEqual([item["dispatch_id"] for item in parsed], ["c1.1", "c1.2", "c1.3"])
        for index, item in enumerate(parsed, 1):
            self.assertIn(f"OBJECTIVE-{index}", item["objective"]["excerpt"])
            self.assertIn(f"CRITERION-{index}", item["acceptance_criteria"][0]["excerpt"])
            self.assertRegex(item["content_digest"], r"^[0-9a-f]{64}$")

    def test_verbatim_ledger_output_is_bounded_with_hash_bytes_and_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            program, _, _ = make_program(Path(tmp))
            accept(program)
            request = orchestrate.prepare_dispatch_by_id(program, "c1.1")
            output = "evidence " * 20_000
            write_run(program, request, "run-1", output=output)
            orchestrate.record_launch(program, dispatch_id="c1.1", run_id="run-1")
            orchestrate.collect_run_result(
                program,
                dispatch_id="c1.1",
                run_id="run-1",
                artifacts=[],
                output_kind="verbatim",
            )
            result = orchestrate.replay_ledger(program)["dispatches"]["c1.1"]["result"]
            self.assertLessEqual(
                len(result["output"].encode()), orchestrate.MAX_SINGLE_EVIDENCE_BYTES
            )
            self.assertEqual(result["worker_output_bytes"], len(output.encode()))
            self.assertEqual(result["output_path"], "ask-runs/codex/run-1/final.txt")

    def test_ledger_session_rebuilds_sidecar_and_invalid_match_durably_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            program, _, _ = make_program(Path(tmp))
            orchestrate.append_event(
                program,
                {
                    "type": "cycle_started",
                    "cycle_id": 1,
                    "next_prompt_path": "x",
                    "next_prompt_hash": "y",
                },
            )
            orchestrate.append_event(
                program,
                {"type": "session_replaced", "cycle_id": 1, "session_id": "ledger"},
            )
            (program / "fable-session-id").write_text("tampered")
            (program / "fable-session-id").chmod(0o600)
            self.assertEqual(orchestrate.sync_fable_session_cache(program), "ledger")
            self.assertEqual((program / "fable-session-id").read_text(), "ledger")

        with tempfile.TemporaryDirectory() as tmp:
            program, _, _ = make_program(Path(tmp))
            accept(program)
            request = orchestrate.prepare_dispatch_by_id(program, "c1.1")
            run = write_run(program, request, "run-bad")
            (run / "prompt.txt").write_text(request["prompt"])
            (run / "meta.json").write_text("{bad")
            for path in run.rglob("*"):
                path.chmod(0o600)
            result = orchestrate.reconcile_dispatch(program, dispatch_id="c1.1")
            self.assertEqual(result["disposition"], "invalid_match")
            self.assertEqual(
                orchestrate.replay_ledger(program)["gate"]["kind"],
                "missing_provenance",
            )


if __name__ == "__main__":
    unittest.main()
