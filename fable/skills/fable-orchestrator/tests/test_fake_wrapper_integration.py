import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "orchestrate.py"
SPEC = importlib.util.spec_from_file_location("fable_orchestrate_integration", SCRIPT)
orchestrate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(orchestrate)


def charter(workspace):
    return {
        "workspace": str(workspace.resolve()),
        "maximum_sandbox": "read-only",
        "max_workers_per_wave": 1,
        "mcps_allowed": False,
        "trusted_mcp_servers": [],
        "mcp_blanket_approval_acknowledged": False,
        "external_mutations_allowed": False,
        "max_worker_timeout_s": 60,
        "max_fable_cycles": 3,
        "max_worker_runs": 3,
        "max_total_worker_seconds": 600,
        "max_total_input_tokens": 10_000,
        "max_total_output_tokens": 10_000,
        "budget_warning_ratio": 1.0,
    }


def manifest():
    return {
        "protocol_version": "1",
        "cycle_id": 1,
        "program_status": "ready_for_dispatch",
        "summary": "One fake-wrapper worker is ready.",
        "plan_revision": 1,
        "gate": {"kind": "none", "reason": ""},
        "dispatches": [{
            "dispatch_id": "c1.1",
            "objective": "Exercise the private Ask wrapper boundary.",
            "worker_prompt": "Return deterministic offline evidence.",
            "acceptance_criteria": ["Return the expected text"],
            "expected_artifacts": [],
            "touches_shared_foundation": False,
            "requested_sandbox": "read-only",
            "requests_external_mutation": False,
            "timeout_hint_s": 30,
        }],
        "chief_of_staff_actions": [
            {"kind": "note", "description": "Run the offline fake wrapper."}
        ],
        "next_review_trigger": "When c1.1 is terminal.",
    }


class FakeWrapperIntegrationTests(unittest.TestCase):
    def _fake_transport(self, base: Path):
        fake_codex = base / "codex"
        fake_codex.write_text(
            "#!/usr/bin/env python3\n"
            "import os,pathlib,sys,time\n"
            "args=sys.argv[1:]\n"
            "if args==['exec','--help']:\n"
            " print('Usage: codex exec [--ignore-user-config]')\n"
            " raise SystemExit(0)\n"
            "assert args[:2]==['exec','--ignore-user-config'],args\n"
            "out=pathlib.Path(args[args.index('-o')+1])\n"
            "time.sleep(float(os.environ.get('FAKE_CODEX_SLEEP','0')))\n"
            "out.write_text('deterministic offline evidence\\n')\n",
            encoding="utf-8",
        )
        fake_codex.chmod(0o700)
        fake_ask = base / "fake-ask.py"
        fake_ask.write_text(
            "#!/usr/bin/env python3\n"
            "import json,os,pathlib,signal,subprocess,sys\n"
            "root=pathlib.Path(os.environ['ASK_RUN_ROOT'])/'codex'\n"
            "root.mkdir(parents=True,exist_ok=True)\n"
            "if sys.argv[1]=='cancel':\n"
            " run=root/sys.argv[2]; meta=json.loads((run/'meta.json').read_text())\n"
            " os.kill(int(meta['pid']),signal.SIGTERM)\n"
            " meta.update(status='cancelled',exit_code=143,duration_seconds=0.2,"
            " input_tokens=1,output_tokens=0)\n"
            " (run/'meta.json').write_text(json.dumps(meta))\n"
            " (run/'cancelled').write_text('yes')\n"
            " raise SystemExit(0)\n"
            "args=sys.argv[2:]\n"
            "sandbox=args[args.index('--sandbox')+1]; workspace=args[-1]\n"
            "prompt=sys.stdin.read(); run_id=os.environ.get('FAKE_RUN_ID','offline-run')\n"
            "run=root/run_id; run.mkdir(parents=True,exist_ok=False)\n"
            "(run/'prompt.txt').write_text(prompt)\n"
            "cmd=['codex','exec','-s',sandbox,'--json','-o',str(run/'final.txt'),"
            "'-C',workspace,'-']\n"
            "meta={'status':'running','project_dir':workspace,'sandbox':sandbox,"
            "'session_id':'offline-thread'}\n"
            "if os.environ.get('FAKE_ASK_ASYNC')=='1':\n"
            " stdin=(run/'prompt.txt').open(); stdout=(run/'events.jsonl').open('w');"
            " stderr=(run/'stderr.log').open('w')\n"
            " child=subprocess.Popen(cmd,stdin=stdin,stdout=stdout,stderr=stderr,text=True)\n"
            " meta['pid']=child.pid\n"
            "else:\n"
            " child=subprocess.run(cmd,input=prompt,text=True,capture_output=True,check=False)\n"
            " meta.update(status='done',exit_code=child.returncode,duration_seconds=0.25,"
            " input_tokens=8,output_tokens=3)\n"
            "(run/'meta.json').write_text(json.dumps(meta))\n"
            "print('RUN_ID='+run_id); print('RUN_DIR='+str(run))\n",
            encoding="utf-8",
        )
        fake_ask.chmod(0o700)
        return fake_codex, fake_ask

    def test_crash_reconcile_private_launch_and_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "repo"
            workspace.mkdir()
            program = orchestrate.create_program(
                root=base / "state",
                workspace=workspace,
                charter=charter(workspace),
                plan="Offline integration plan.",
                decisions="No live model calls.",
                program_id="offline",
            )
            orchestrate.append_event(program, {"type": "cycle_started", "cycle_id": 1})
            orchestrate.accept_manifest(program, manifest())
            _, fake = self._fake_transport(base)

            # Mandatory interruption checkpoint: intent exists, no process was launched.
            with mock.patch.dict(
                os.environ, {"PATH": f"{base}:{os.environ.get('PATH', '')}"}
            ):
                request = orchestrate.prepare_dispatch_by_id(program, "c1.1")
            recovered = orchestrate.reconcile_dispatch(program, dispatch_id="c1.1")
            self.assertEqual(recovered["disposition"], "no_match")
            self.assertEqual(recovered["launch_request"], request)
            env = dict(os.environ)
            env.update(request["env"])
            env["FABLE_ORCHESTRATOR_ASK_CODEX"] = str(fake)
            launched = subprocess.run(
                [request["wrapper"], *request["argv"]],
                input=request["prompt"],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertEqual(launched.returncode, 0, launched.stderr)
            self.assertIn("RUN_ID=offline-run", launched.stdout)
            run = program / "ask-runs" / "codex" / "offline-run"
            command = (run / "cmd.txt").read_text()
            self.assertIn("exec --ignore-user-config", command)
            self.assertEqual(
                json.loads((run / "isolation.json").read_text()),
                request["isolation"],
            )
            orchestrate.record_launch(
                program, dispatch_id="c1.1", run_id="offline-run"
            )

            # The fake dependency inherited umask 077 from private-ask.sh.
            for path in [run, *run.rglob("*")]:
                expected = 0o700 if path.is_dir() else 0o600
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), expected, str(path))
            orchestrate.collect_run_result(
                program,
                dispatch_id="c1.1",
                run_id="offline-run",
                artifacts=[],
                output_kind="verbatim",
            )
            replayed = orchestrate.replay_ledger(program)
            self.assertEqual(replayed["phase"], "evidence_ready")
            self.assertEqual(
                replayed["dispatches"]["c1.1"]["result"]["output"],
                "deterministic offline evidence\n",
            )
            orchestrate.audit_private_tree(program)

    def test_watchdog_cancels_async_run_through_wrapper_and_records_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "repo"
            workspace.mkdir()
            program = orchestrate.create_program(
                root=base / "state",
                workspace=workspace,
                charter=charter(workspace),
                plan="Watchdog plan.",
                decisions="Offline only.",
                program_id="watchdog",
            )
            orchestrate.append_event(program, {"type": "cycle_started", "cycle_id": 1})
            orchestrate.accept_manifest(program, manifest())
            _, fake = self._fake_transport(base)
            with mock.patch.dict(
                os.environ, {"PATH": f"{base}:{os.environ.get('PATH', '')}"}
            ):
                request = orchestrate.prepare_dispatch_by_id(program, "c1.1")
            env = dict(os.environ)
            env.update(request["env"])
            env.update(
                {
                    "FABLE_ORCHESTRATOR_ASK_CODEX": str(fake),
                    "FABLE_ORCHESTRATOR_WATCHDOG_TIMEOUT_S": "0.2",
                    "FAKE_ASK_ASYNC": "1",
                    "FAKE_CODEX_SLEEP": "5",
                    "FAKE_RUN_ID": "timeout-run",
                }
            )
            launched = subprocess.run(
                [request["wrapper"], *request["argv"]],
                input=request["prompt"],
                text=True,
                capture_output=True,
                check=False,
                env=env,
            )
            self.assertEqual(launched.returncode, 0, launched.stderr)
            run = program / "ask-runs" / "codex" / "timeout-run"
            deadline = time.monotonic() + 5
            while not (run / "watchdog.json").is_file() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue((run / "watchdog.json").is_file())
            evidence = json.loads((run / "watchdog.json").read_text())
            self.assertTrue(evidence["deadline_enforced"])
            self.assertEqual(evidence["cancel_exit_code"], 0)
            self.assertTrue((run / "cancelled").is_file())
            self.assertEqual(json.loads((run / "meta.json").read_text())["status"], "cancelled")

    def test_actual_installed_wrapper_process_tree_is_killed_and_verified(self):
        installed_wrapper = Path.home() / ".agents/skills/ask-codex/scripts/ask.sh"
        self.assertTrue(installed_wrapper.is_file())
        child_pid = None
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "repo"
            workspace.mkdir()
            child_record = base / "fake-child.json"
            term_record = base / "fake-child-term"
            fake_codex = base / "codex"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import json,os,pathlib,signal,sys,time\n"
                "args=sys.argv[1:]\n"
                "if args==['exec','--help']:\n"
                " print('Usage: codex exec [--ignore-user-config]')\n"
                " raise SystemExit(0)\n"
                "assert args[:2]==['exec','--ignore-user-config'],args\n"
                "record=pathlib.Path(os.environ['FAKE_CHILD_RECORD'])\n"
                "term=pathlib.Path(os.environ['FAKE_TERM_RECORD'])\n"
                "signal.signal(signal.SIGTERM,lambda *_: term.write_text('TERM'))\n"
                "record.write_text(json.dumps({'pid':os.getpid(),'pgid':os.getpgid(0)}))\n"
                "while True: time.sleep(0.1)\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o700)
            program = orchestrate.create_program(
                root=base / "state",
                workspace=workspace,
                charter=charter(workspace),
                plan="Production-shaped watchdog plan.",
                decisions="Use only the offline fake executable.",
                program_id="actual-wrapper",
            )
            orchestrate.append_event(program, {"type": "cycle_started", "cycle_id": 1})
            orchestrate.accept_manifest(program, manifest())
            with mock.patch.dict(
                os.environ, {"PATH": f"{base}:{os.environ.get('PATH', '')}"}
            ):
                request = orchestrate.prepare_dispatch_by_id(program, "c1.1")
            env = dict(os.environ)
            env.update(request["env"])
            env.update(
                {
                    "FABLE_ORCHESTRATOR_ASK_CODEX": str(installed_wrapper),
                    "FABLE_ORCHESTRATOR_WATCHDOG_TIMEOUT_S": "0.5",
                    "FABLE_ORCHESTRATOR_WATCHDOG_GRACE_S": "0.2",
                    "FAKE_CHILD_RECORD": str(child_record),
                    "FAKE_TERM_RECORD": str(term_record),
                }
            )
            try:
                launched = subprocess.run(
                    [request["wrapper"], *request["argv"]],
                    input=request["prompt"],
                    text=True,
                    capture_output=True,
                    check=False,
                    env=env,
                    timeout=10,
                )
                self.assertEqual(launched.returncode, 0, launched.stderr)
                run_id = next(
                    line.split("=", 1)[1]
                    for line in launched.stdout.splitlines()
                    if line.startswith("RUN_ID=")
                )
                run = program / "ask-runs" / "codex" / run_id
                deadline = time.monotonic() + 8
                while (
                    not child_record.is_file()
                    or not (run / "watchdog.json").is_file()
                ) and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(child_record.is_file(), "fake Codex child never started")
                child = json.loads(child_record.read_text())
                child_pid = child["pid"]
                evidence = json.loads((run / "watchdog.json").read_text())
                self.assertEqual(evidence["target_pid"], child_pid)
                self.assertEqual(evidence["target_pgid"], child["pgid"])
                self.assertIn("term", evidence)
                self.assertIn("kill", evidence)
                self.assertFalse(evidence["final_liveness"]["pid_alive"])
                self.assertFalse(evidence["final_liveness"]["group_alive"])
                self.assertEqual(evidence["final_liveness"]["remaining_members"], [])
                self.assertTrue(evidence["deadline_enforced"])
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid, 0)
            finally:
                if child_pid is not None:
                    try:
                        os.kill(child_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_actual_installed_wrapper_early_cancel_kills_and_verifies_worker_group(self):
        installed_wrapper = Path.home() / ".agents/skills/ask-codex/scripts/ask.sh"
        self.assertTrue(installed_wrapper.is_file())
        child_pid = None
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "repo"
            workspace.mkdir()
            child_record = base / "early-cancel-child.json"
            fake_codex = base / "codex"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import json,os,pathlib,signal,sys,time\n"
                "args=sys.argv[1:]\n"
                "if args==['exec','--help']:\n"
                " print('Usage: codex exec [--ignore-user-config]')\n"
                " raise SystemExit(0)\n"
                "assert args[:2]==['exec','--ignore-user-config'],args\n"
                "signal.signal(signal.SIGTERM,lambda *_: None)\n"
                "pathlib.Path(os.environ['FAKE_CHILD_RECORD']).write_text("
                "json.dumps({'pid':os.getpid(),'pgid':os.getpgid(0)}))\n"
                "while True: time.sleep(0.1)\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o700)
            program = orchestrate.create_program(
                root=base / "state",
                workspace=workspace,
                charter=charter(workspace),
                plan="Production-shaped early-cancel plan.",
                decisions="Use only the offline fake executable.",
                program_id="actual-wrapper-early-cancel",
            )
            orchestrate.append_event(program, {"type": "cycle_started", "cycle_id": 1})
            orchestrate.accept_manifest(program, manifest())
            with mock.patch.dict(
                os.environ, {"PATH": f"{base}:{os.environ.get('PATH', '')}"}
            ):
                request = orchestrate.prepare_dispatch_by_id(program, "c1.1")
            env = dict(os.environ)
            env.update(request["env"])
            env.update(
                {
                    "FABLE_ORCHESTRATOR_ASK_CODEX": str(installed_wrapper),
                    "FABLE_ORCHESTRATOR_WATCHDOG_TIMEOUT_S": "30",
                    "FABLE_ORCHESTRATOR_WATCHDOG_GRACE_S": "0.2",
                    "FAKE_CHILD_RECORD": str(child_record),
                }
            )
            try:
                launch_stdout = base / "launch.stdout"
                launch_stderr = base / "launch.stderr"
                with (
                    launch_stdout.open("w") as stdout_handle,
                    launch_stderr.open("w") as stderr_handle,
                ):
                    launched = subprocess.Popen(
                        [request["wrapper"], *request["argv"]],
                        stdin=subprocess.PIPE,
                        stdout=stdout_handle,
                        stderr=stderr_handle,
                        text=True,
                        env=env,
                    )
                    assert launched.stdin is not None
                    launched.stdin.write(request["prompt"])
                    launched.stdin.close()
                start_deadline = time.monotonic() + 5
                while not child_record.is_file() and time.monotonic() < start_deadline:
                    time.sleep(0.05)
                self.assertTrue(child_record.is_file(), "fake Codex child never started")
                child = json.loads(child_record.read_text())
                child_pid = child["pid"]
                run_root = program / "ask-runs" / "codex"
                runs = [
                    path for path in run_root.iterdir()
                    if path.is_dir() and (path / "supervision.json").is_file()
                ]
                self.assertEqual(len(runs), 1)
                run = runs[0]
                run_id = run.name
                cancelled = subprocess.run(
                    [request["wrapper"], "cancel", run_id],
                    text=True,
                    capture_output=True,
                    check=False,
                    env=env,
                    timeout=10,
                )
                self.assertEqual(cancelled.returncode, 0, cancelled.stderr)
                self.assertEqual(
                    launched.wait(timeout=5),
                    0,
                    launch_stderr.read_text(),
                )
                evidence_deadline = time.monotonic() + 5
                while (
                    not (run / "watchdog.json").is_file()
                    and time.monotonic() < evidence_deadline
                ):
                    time.sleep(0.05)
                self.assertTrue(
                    (run / "watchdog.json").is_file(),
                    "early cancel produced no durable group-verification evidence",
                )
                evidence = json.loads((run / "watchdog.json").read_text())
                self.assertEqual(evidence["trigger"], "explicit_cancel")
                self.assertEqual(evidence["target_pid"], child_pid)
                self.assertEqual(evidence["target_pgid"], child["pgid"])
                self.assertIn("term", evidence)
                self.assertIn("kill", evidence)
                self.assertFalse(evidence["final_liveness"]["pid_alive"])
                self.assertFalse(evidence["final_liveness"]["group_alive"])
                self.assertEqual(evidence["final_liveness"]["remaining_members"], [])
                self.assertTrue(evidence["termination_verified"])
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid, 0)
            finally:
                if child_pid is not None:
                    try:
                        os.kill(child_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_watchdog_verifies_cancelled_status_from_installed_wrapper(self):
        installed_wrapper = Path.home() / ".agents/skills/ask-codex/scripts/ask.sh"
        self.assertTrue(installed_wrapper.is_file())
        child_pid = None
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "repo"
            workspace.mkdir()
            child_record = base / "observed-cancel-child.json"
            fake_codex = base / "codex"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import json,os,pathlib,signal,sys,time\n"
                "args=sys.argv[1:]\n"
                "if args==['exec','--help']:\n"
                " print('Usage: codex exec [--ignore-user-config]')\n"
                " raise SystemExit(0)\n"
                "assert args[:2]==['exec','--ignore-user-config'],args\n"
                "signal.signal(signal.SIGTERM,lambda *_: None)\n"
                "pathlib.Path(os.environ['FAKE_CHILD_RECORD']).write_text("
                "json.dumps({'pid':os.getpid(),'pgid':os.getpgid(0)}))\n"
                "while True: time.sleep(0.1)\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o700)
            program = orchestrate.create_program(
                root=base / "state",
                workspace=workspace,
                charter=charter(workspace),
                plan="Observed-cancel watchdog plan.",
                decisions="Use only the offline fake executable.",
                program_id="observed-cancel",
            )
            orchestrate.append_event(program, {"type": "cycle_started", "cycle_id": 1})
            orchestrate.accept_manifest(program, manifest())
            with mock.patch.dict(
                os.environ, {"PATH": f"{base}:{os.environ.get('PATH', '')}"}
            ):
                request = orchestrate.prepare_dispatch_by_id(program, "c1.1")
            env = dict(os.environ)
            env.update(request["env"])
            env.update(
                {
                    "FABLE_ORCHESTRATOR_ASK_CODEX": str(installed_wrapper),
                    "FABLE_ORCHESTRATOR_WATCHDOG_TIMEOUT_S": "30",
                    "FABLE_ORCHESTRATOR_WATCHDOG_GRACE_S": "0.2",
                    "FAKE_CHILD_RECORD": str(child_record),
                }
            )
            try:
                with (
                    (base / "launch.stdout").open("w") as stdout_handle,
                    (base / "launch.stderr").open("w") as stderr_handle,
                ):
                    launched = subprocess.Popen(
                        [request["wrapper"], *request["argv"]],
                        stdin=subprocess.PIPE,
                        stdout=stdout_handle,
                        stderr=stderr_handle,
                        text=True,
                        env=env,
                    )
                    assert launched.stdin is not None
                    launched.stdin.write(request["prompt"])
                    launched.stdin.close()
                start_deadline = time.monotonic() + 5
                while not child_record.is_file() and time.monotonic() < start_deadline:
                    time.sleep(0.05)
                self.assertTrue(child_record.is_file(), "fake Codex child never started")
                child = json.loads(child_record.read_text())
                child_pid = child["pid"]
                run_root = program / "ask-runs" / "codex"
                runs = [
                    path for path in run_root.iterdir()
                    if path.is_dir() and (path / "supervision.json").is_file()
                ]
                self.assertEqual(len(runs), 1)
                run = runs[0]
                directly_cancelled = subprocess.run(
                    [str(installed_wrapper), "cancel", run.name],
                    text=True,
                    capture_output=True,
                    check=False,
                    env=env,
                    timeout=10,
                )
                self.assertEqual(directly_cancelled.returncode, 0)
                self.assertEqual(launched.wait(timeout=5), 0)
                evidence_deadline = time.monotonic() + 5
                while (
                    not (run / "watchdog.json").is_file()
                    and time.monotonic() < evidence_deadline
                ):
                    time.sleep(0.05)
                self.assertTrue((run / "watchdog.json").is_file())
                evidence = json.loads((run / "watchdog.json").read_text())
                self.assertIn(
                    evidence["trigger"],
                    {"observed_cancelled", "observed_terminal_live"},
                )
                self.assertIn(
                    evidence["observed_terminal_status"],
                    {"cancelled", "failed", "empty-output"},
                )
                self.assertTrue(evidence["termination_verified"])
                self.assertFalse(evidence["final_liveness"]["pid_alive"])
                self.assertFalse(evidence["final_liveness"]["group_alive"])
                self.assertEqual(evidence["final_liveness"]["remaining_members"], [])
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid, 0)
            finally:
                if child_pid is not None:
                    try:
                        os.kill(child_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    unittest.main()
