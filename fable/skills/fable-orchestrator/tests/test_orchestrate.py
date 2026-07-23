import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "orchestrate.py"
SPEC = importlib.util.spec_from_file_location("fable_orchestrate_core", SCRIPT)
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
        "max_worker_timeout_s": 600,
        "max_fable_cycles": 10,
        "max_worker_runs": 10,
        "max_total_worker_seconds": 3600,
        "max_total_input_tokens": 100_000,
        "max_total_output_tokens": 50_000,
        "budget_warning_ratio": 0.8,
    }
    value.update(overrides)
    return value


def dispatch(index=1, cycle=1, **overrides):
    value = {
        "dispatch_id": f"c{cycle}.{index}",
        "objective": "Inspect the fixture and report evidence.",
        "worker_prompt": "Read the fixture. Do not modify it.",
        "acceptance_criteria": ["Name both source files", "Cite paths"],
        "expected_artifacts": [],
        "touches_shared_foundation": False,
        "requested_sandbox": "read-only",
        "requests_external_mutation": False,
        "timeout_hint_s": 300,
    }
    value.update(overrides)
    return value


def manifest(*, cycle=1, dispatches=None, **overrides):
    value = {
        "protocol_version": "1",
        "cycle_id": cycle,
        "program_status": "ready_for_dispatch",
        "summary": "One bounded inspection is ready.",
        "plan_revision": 1,
        "gate": {"kind": "none", "reason": ""},
        "dispatches": dispatches if dispatches is not None else [dispatch(cycle=cycle)],
        "chief_of_staff_actions": [
            {"kind": "note", "description": "Launch the validated read-only worker."}
        ],
        "next_review_trigger": "When the wave reaches a terminal state.",
    }
    value.update(overrides)
    return value


def make_program(base: Path):
    workspace = base / "repo"
    workspace.mkdir()
    program = orchestrate.create_program(
        root=base / "state",
        workspace=workspace,
        charter=charter(workspace),
        plan="Locked plan",
        decisions="Advisor recommendation accepted.",
        program_id="demo",
    )
    return program, workspace


def assert_exact_protocol_prompt(
    testcase: unittest.TestCase,
    prompt: str,
    *,
    cycle_id: int,
    plan_revision: int,
) -> None:
    template_text = prompt.split(
        "EXACT_PROTOCOL_V1_JSON_TEMPLATE\n", 1
    )[1].split("\nEND_EXACT_PROTOCOL_V1_JSON_TEMPLATE", 1)[0]
    template = json.loads(template_text)
    testcase.assertEqual(
        set(template),
        {
            "protocol_version",
            "cycle_id",
            "program_status",
            "summary",
            "plan_revision",
            "gate",
            "dispatches",
            "chief_of_staff_actions",
            "next_review_trigger",
        },
    )
    testcase.assertEqual(template["protocol_version"], "1")
    testcase.assertEqual(template["cycle_id"], cycle_id)
    testcase.assertIs(type(template["plan_revision"]), int)
    testcase.assertEqual(template["plan_revision"], plan_revision)
    testcase.assertEqual(set(template["gate"]), {"kind", "reason"})
    testcase.assertEqual(len(template["dispatches"]), 1)
    proposed = template["dispatches"][0]
    testcase.assertEqual(
        set(proposed),
        {
            "dispatch_id",
            "objective",
            "worker_prompt",
            "acceptance_criteria",
            "expected_artifacts",
            "touches_shared_foundation",
            "requested_sandbox",
            "requests_external_mutation",
            "timeout_hint_s",
        },
    )
    testcase.assertIsInstance(proposed["dispatch_id"], str)
    testcase.assertIsInstance(proposed["objective"], str)
    testcase.assertIsInstance(proposed["worker_prompt"], str)
    testcase.assertIsInstance(proposed["acceptance_criteria"], list)
    testcase.assertIsInstance(proposed["expected_artifacts"], list)
    testcase.assertIs(type(proposed["touches_shared_foundation"]), bool)
    testcase.assertIn(proposed["requested_sandbox"], {"read-only", "workspace-write"})
    testcase.assertIs(type(proposed["requests_external_mutation"]), bool)
    testcase.assertIs(type(proposed["timeout_hint_s"]), int)
    testcase.assertEqual(
        set(template["chief_of_staff_actions"][0]),
        {"kind", "description"},
    )
    cardinality_text = prompt.split(
        "EXACT_STATUS_GATE_DISPATCH_CARDINALITY\n", 1
    )[1].split("\nEND_EXACT_STATUS_GATE_DISPATCH_CARDINALITY", 1)[0]
    testcase.assertEqual(
        json.loads(cardinality_text),
        {
            "blocked": {"dispatch_count": 0, "gate_kinds": ["blocked"]},
            "complete": {"dispatch_count": 0, "gate_kinds": ["none"]},
            "needs_human": {
                "dispatch_count": 0,
                "gate_kinds": ["human_approval", "authority_expansion"],
            },
            "ready_for_dispatch": {
                "dispatch_count": "1-3",
                "gate_kinds": ["none"],
            },
        },
    )
    testcase.assertIn(
        "ALIASES_FORBIDDEN: success_criteria,sandbox,requests_mcp,"
        "shared_foundation,artifacts,timeout_s,notes",
        prompt,
    )


class ManifestTests(unittest.TestCase):
    def test_valid_manifest_preserves_unknown_keys(self):
        value = manifest(experimental_hint="keep me")
        parsed = orchestrate.validate_manifest(value, expected_cycle=1, minimum_plan_revision=1)
        self.assertEqual(parsed["experimental_hint"], "keep me")

    def test_cycle_and_protocol_must_echo_exactly(self):
        with self.assertRaisesRegex(orchestrate.ProtocolError, "cycle_id"):
            orchestrate.validate_manifest(
                manifest(cycle_id=2), expected_cycle=1, minimum_plan_revision=1
            )
        with self.assertRaisesRegex(orchestrate.ProtocolError, "protocol_version"):
            orchestrate.validate_manifest(
                manifest(protocol_version="2"), expected_cycle=1, minimum_plan_revision=1
            )

    def test_dispatch_contract_is_strict(self):
        with self.assertRaisesRegex(orchestrate.ProtocolError, "three"):
            orchestrate.validate_manifest(
                manifest(dispatches=[dispatch(i) for i in range(1, 5)]),
                expected_cycle=1,
                minimum_plan_revision=1,
            )
        with self.assertRaisesRegex(orchestrate.ProtocolError, "dispatch_id"):
            orchestrate.validate_manifest(
                manifest(dispatches=[dispatch(1), dispatch(1)]),
                expected_cycle=1,
                minimum_plan_revision=1,
            )
        with self.assertRaisesRegex(orchestrate.ProtocolError, "depends_on"):
            orchestrate.validate_manifest(
                manifest(dispatches=[dispatch(depends_on=[])]),
                expected_cycle=1,
                minimum_plan_revision=1,
            )

    def test_parser_requires_exactly_one_bare_object(self):
        raw = json.dumps(manifest())
        self.assertEqual(orchestrate.parse_manifest_text(raw)["cycle_id"], 1)
        with self.assertRaises(orchestrate.ProtocolError):
            orchestrate.parse_manifest_text("analysis\n" + raw)

    def test_one_prior_schema_failure_still_allows_the_repair(self):
        state = {"repair_attempts": {"1": 1}}
        self.assertEqual(orchestrate.invalid_manifest_action(state, cycle_id=1), "repair")
        state["repair_attempts"]["1"] = 2
        self.assertEqual(
            orchestrate.invalid_manifest_action(state, cycle_id=1), "needs_human"
        )

    def test_initial_and_reconciliation_prompts_embed_exact_protocol_template(self):
        initial = orchestrate.build_cold_start_prompt(
            charter_text="{}",
            plan_text="plan",
            decision_text="decisions",
            ledger_digest="digest",
            open_dispatches=[],
            evidence=[],
            cycle_id=3,
            plan_revision=2,
        )
        assert_exact_protocol_prompt(
            self, initial, cycle_id=3, plan_revision=2
        )
        reconciliation = orchestrate._reconciliation_prompt(
            3, "persisted checkpoint", plan_revision=2
        )
        assert_exact_protocol_prompt(
            self, reconciliation, cycle_id=3, plan_revision=2
        )


class StateAndAuthorityTests(unittest.TestCase):
    def test_create_program_enforces_private_permissions_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            program, _ = make_program(Path(tmp))
            orchestrate.verify_program_integrity(program)
            self.assertEqual(stat.S_IMODE(program.stat().st_mode), 0o700)
            for path in program.rglob("*"):
                expected = 0o700 if path.is_dir() else 0o600
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), expected, str(path))

    def test_atomic_state_has_private_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            program = Path(tmp)
            orchestrate.write_state(program, {"phase": "initialized"})
            target = program / "state.json"
            self.assertEqual(json.loads(target.read_text())["phase"], "initialized")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_sandbox_workspace_and_shared_wave_are_derived(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            value = manifest(
                dispatches=[
                    dispatch(1, requested_sandbox="workspace-write"),
                    dispatch(2, touches_shared_foundation=True),
                    dispatch(3),
                ]
            )
            validated = orchestrate.validate_manifest(
                value, expected_cycle=1, minimum_plan_revision=1
            )
            effective = orchestrate.effective_dispatches(validated, charter(workspace))
            self.assertEqual([item["dispatch_id"] for item in effective], ["c1.2"])
            self.assertEqual(effective[0]["workspace"], str(workspace.resolve()))
            self.assertEqual(effective[0]["effective_sandbox"], "read-only")


class TransportTests(unittest.TestCase):
    def _fake_advisor(self, base: Path, outputs):
        fake = base / "fake-advisor.py"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            "root=pathlib.Path(os.environ['FABLE_ADVISOR_STATE_DIR']); root.mkdir(parents=True,exist_ok=True)\n"
            "counter=root/'counter'; n=int(counter.read_text())+1 if counter.exists() else 1\n"
            "counter.write_text(str(n)); (root/'argv.jsonl').open('a').write(json.dumps(sys.argv)+'\\n')\n"
            "run=root/('run-'+str(n)); run.mkdir(); meta=run/'meta.json'\n"
            "meta.write_text(json.dumps({'returned_session_id':'session-1','terminal_status':'done','exit_code':0}))\n"
            f"outputs={json.dumps(outputs)}\n"
            "print(outputs[min(n-1,len(outputs)-1)])\n"
            "print('FABLE_ADVISOR_META='+str(meta),file=sys.stderr)\n",
            encoding="utf-8",
        )
        fake.chmod(0o700)
        return fake

    def test_transport_persists_session_and_single_manifest_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            program, _ = make_program(base)
            fake = self._fake_advisor(base, [json.dumps(manifest())])
            result = orchestrate.run_fable_cycle(
                program, cycle_id=1, advisor_runner=fake, timeout_s=10
            )
            self.assertEqual(result["cycle_id"], 1)
            self.assertEqual((program / "fable-session-id").read_text(), "session-1")
            events = orchestrate._read_events(program)
            self.assertEqual(
                len([event for event in events if event["type"] == "manifest_accepted"]), 1
            )
            self.assertNotIn("authority_derived", [event["type"] for event in events])

    def test_one_invalid_response_gets_one_same_session_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            program, _ = make_program(base)
            fake = self._fake_advisor(base, ["not json", json.dumps(manifest())])
            result = orchestrate.run_fable_cycle(
                program, cycle_id=1, advisor_runner=fake, timeout_s=10
            )
            self.assertEqual(result["program_status"], "ready_for_dispatch")
            invocations = [
                json.loads(line)
                for line in (program / "fable-runs" / "argv.jsonl").read_text().splitlines()
            ]
            self.assertNotIn("--resume", invocations[0])
            self.assertEqual(
                invocations[1][invocations[1].index("--resume") + 1], "session-1"
            )
            self.assertEqual(
                len(
                    [
                        event
                        for event in orchestrate._read_events(program)
                        if event["type"] == "manifest_invalid"
                    ]
                ),
                1,
            )

    def test_repair_prompt_repeats_complete_exact_protocol_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            program, _ = make_program(base)
            fake = self._fake_advisor(base, ["not json", "still not json"])
            with self.assertRaisesRegex(
                orchestrate.ProtocolError, "invalid after one repair"
            ):
                orchestrate.run_fable_cycle(
                    program, cycle_id=1, advisor_runner=fake, timeout_s=10
                )
            repair = (
                program / "cycles" / "0001" / "attempt-2" / "prompt.txt"
            ).read_text()
            assert_exact_protocol_prompt(
                self, repair, cycle_id=1, plan_revision=1
            )
            self.assertIn("ALL required exact keys and types", repair)
            self.assertIn("OBSERVED_VALIDATION_ERROR", repair)


class CliTests(unittest.TestCase):
    def test_help_lists_operational_and_approval_commands(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in (
            "init",
            "cycle",
            "status",
            "prepare-dispatch",
            "record-launch",
            "reconcile",
            "record-result",
            "approve",
            "approve-plan",
            "approve-retry",
            "approve-budget",
            "reconcile-turn",
        ):
            self.assertIn(command, result.stdout)


if __name__ == "__main__":
    unittest.main()
