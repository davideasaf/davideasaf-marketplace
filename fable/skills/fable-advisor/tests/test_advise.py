import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


SKILL_DIR = Path(__file__).resolve().parents[1]
ADVISE = SKILL_DIR / "scripts" / "advise.py"
SMOKE = SKILL_DIR / "tests" / "smoke-safety.sh"


class AdviseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.log = self.root / "calls.jsonl"
        self.agent = self.root / "fake-agent"
        self.write_agent("""
            import json, os, sys
            args = sys.argv[1:]
            with open(os.environ['FAKE_AGENT_LOG'], 'a') as log:
                log.write(json.dumps(args) + '\\n')
            if args == ['models']:
                print(os.environ.get(
                    'FAKE_MODELS',
                    'claude-fable-5-thinking-high - Fable 5 1M Thinking (NO ZDR)\\n'
                    'claude-fable-5-fast - Fable 5 Fast'
                ))
                raise SystemExit(0)
            behavior = os.environ.get('FAKE_BEHAVIOR', 'success')
            if behavior == 'timeout':
                import time; time.sleep(5)
            if behavior == 'nonzero':
                print('agent stdout before failure')
                print('agent stderr before failure', file=sys.stderr)
                raise SystemExit(7)
            if behavior == 'malformed':
                print('not json')
                raise SystemExit(0)
            if behavior == 'missing_session':
                print(json.dumps({'result': 'advisor answer'}))
                raise SystemExit(0)
            if behavior == 'blank_session':
                print(json.dumps({'result': 'advisor answer', 'session_id': '   '}))
                raise SystemExit(0)
            if behavior == 'smoke':
                print(json.dumps({
                    'type': 'result', 'is_error': False,
                    'result': 'Ask mode refused the write.', 'session_id': 'smoke-session'
                }))
                raise SystemExit(0)
            print('noise before json')
            print(json.dumps({'result': os.environ.get('FAKE_RESPONSE', 'advisor answer'), 'session_id': 'session-123'}))
        """)

    def tearDown(self):
        self.tmp.cleanup()

    def write_agent(self, body):
        self.agent.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(body))
        self.agent.chmod(0o755)

    def run_cli(self, *args, input=None, **extra_env):
        env = os.environ | {
            "FABLE_ADVISOR_AGENT_BIN": str(self.agent),
            "FABLE_ADVISOR_STATE_DIR": str(self.state),
            "FAKE_AGENT_LOG": str(self.log),
        } | extra_env
        return subprocess.run(
            [sys.executable, str(ADVISE), *args], input=input, text=True,
            capture_output=True, env=env, cwd=self.root,
        )

    def run_cli_direct(self, *args, input=None, **extra_env):
        env = os.environ | {
            "FABLE_ADVISOR_AGENT_BIN": str(self.agent),
            "FABLE_ADVISOR_STATE_DIR": str(self.state),
            "FAKE_AGENT_LOG": str(self.log),
        } | extra_env
        return subprocess.run(
            [str(ADVISE), *args], input=input, text=True,
            capture_output=True, env=env, cwd=self.root,
        )

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def metadata(self, result):
        marker = "FABLE_ADVISOR_META="
        path = next(line[len(marker):] for line in result.stderr.splitlines() if line.startswith(marker))
        return json.loads(Path(path).read_text()), Path(path)

    def test_safe_default_command_omits_execution_and_mcp_flags(self):
        result = self.run_cli("analyze this")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "advisor answer\n")
        calls = self.calls()
        self.assertEqual(calls[0], ["models"])
        self.assertEqual(calls[1][:-1], [
            "-p", "--model", "claude-fable-5-thinking-high", "--output-format", "json",
            "--trust", "--mode", "ask", "--sandbox", "enabled", "--workspace", str(self.root.resolve()),
        ])
        self.assertNotIn("--yolo", calls[1])
        self.assertNotIn("--approve-mcps", calls[1])
        self.assertNotIn("--resume", calls[1])

    def test_documented_runner_is_directly_executable(self):
        result = self.run_cli_direct("brief")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "advisor answer\n")

    def test_mcp_approval_is_opt_in(self):
        result = self.run_cli("--with-mcps", "brief")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--approve-mcps", self.calls()[1])

    def test_resume_is_only_the_explicit_id(self):
        result = self.run_cli("--resume", "abc-42", "brief")
        self.assertEqual(result.returncode, 0, result.stderr)
        call = self.calls()[1]
        self.assertEqual(call[call.index("--resume") + 1], "abc-42")

    def test_stdin_prompt_is_preserved_after_advisory_prefix(self):
        brief = "Read this exactly\n  including spacing.\n"
        result = self.run_cli("-", input=brief)
        self.assertEqual(result.returncode, 0, result.stderr)
        prompt = self.calls()[1][-1]
        self.assertTrue(prompt.endswith(brief))
        self.assertIn("on-demand advisor", prompt)
        self.assertIn("Codex remains executor", prompt)
        self.assertIn("must not edit files", prompt)
        self.assertIn("state-changing shell commands", prompt)
        self.assertIn("mutate external systems through MCPs", prompt)

    def test_missing_model_lists_available_fable_variants(self):
        result = self.run_cli(
            "--model", "claude-fable-unknown", "brief",
            FAKE_MODELS=(
                "claude-fable-5-thinking-high - Fable 5 1M Thinking (NO ZDR)\n"
                "claude-fable-5-fast - Fable 5 Fast\n"
                "other-model - Other Model"
            ),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("claude-fable-unknown", result.stderr)
        self.assertIn("claude-fable-5-thinking-high", result.stderr)
        self.assertIn("claude-fable-5-fast", result.stderr)
        self.assertNotIn("other-model", result.stderr)
        self.assertNotIn("Fable 5 1M Thinking", result.stderr)
        self.assertNotIn("Fable 5 Fast", result.stderr)
        self.assertEqual(self.calls(), [["models"]])

    def test_json_array_models_supports_string_and_id_object_entries(self):
        model_ids = ["claude-fable-array-string", "claude-fable-array-object"]
        listing = json.dumps([model_ids[0], {"id": model_ids[1]}])
        for model_id in model_ids:
            with self.subTest(model_id=model_id):
                result = self.run_cli(
                    "--model", model_id, "brief", FAKE_MODELS=listing
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "advisor answer\n")
                self.assertEqual(self.metadata(result)[0]["terminal_status"], "done")

    def test_json_object_models_supports_string_and_id_object_entries(self):
        model_ids = ["claude-fable-object-string", "claude-fable-object-object"]
        listing = json.dumps({"models": [model_ids[0], {"id": model_ids[1]}]})
        for model_id in model_ids:
            with self.subTest(model_id=model_id):
                result = self.run_cli(
                    "--model", model_id, "brief", FAKE_MODELS=listing
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "advisor answer\n")
                self.assertEqual(self.metadata(result)[0]["terminal_status"], "done")

    def test_timeout_returns_124_and_records_timed_out_status(self):
        result = self.run_cli("--timeout", "0.1", "brief", FAKE_BEHAVIOR="timeout")
        self.assertEqual(result.returncode, 124)
        meta, _ = self.metadata(result)
        self.assertEqual(meta["terminal_status"], "timed_out")
        self.assertEqual(meta["exit_code"], 124)

    def test_nonzero_and_malformed_output_are_non_success(self):
        nonzero = self.run_cli("brief", FAKE_BEHAVIOR="nonzero")
        self.assertEqual(nonzero.returncode, 7)
        meta, meta_path = self.metadata(nonzero)
        self.assertEqual(meta["terminal_status"], "agent_nonzero")
        self.assertIn("exited with code 7", meta["error"])
        self.assertEqual(
            (meta_path.parent / "agent.stdout.txt").read_text(),
            "agent stdout before failure\n",
        )
        self.assertEqual(
            (meta_path.parent / "agent.stderr.txt").read_text(),
            "agent stderr before failure\n",
        )
        malformed = self.run_cli("brief", FAKE_BEHAVIOR="malformed")
        self.assertNotEqual(malformed.returncode, 0)
        malformed_meta, malformed_path = self.metadata(malformed)
        self.assertEqual(malformed_meta["terminal_status"], "invalid_json")
        self.assertIn("invalid JSON", malformed_meta["error"])
        self.assertEqual((malformed_path.parent / "agent.stdout.txt").read_text(), "not json\n")

    def test_model_check_failure_persists_error_and_captured_output(self):
        self.write_agent("""
            import sys
            if sys.argv[1:] == ['models']:
                print('models stdout')
                print('models stderr', file=sys.stderr)
                raise SystemExit(9)
            raise AssertionError('consultation must not launch')
        """)
        result = self.run_cli("brief")
        self.assertEqual(result.returncode, 9)
        meta, meta_path = self.metadata(result)
        self.assertEqual(meta["terminal_status"], "model_check_failed")
        self.assertIn("exit code 9", meta["error"])
        self.assertEqual((meta_path.parent / "model-check.stdout.txt").read_text(), "models stdout\n")
        self.assertEqual((meta_path.parent / "model-check.stderr.txt").read_text(), "models stderr\n")

    def test_success_requires_nonblank_session_id(self):
        for behavior in ("missing_session", "blank_session"):
            with self.subTest(behavior=behavior):
                result = self.run_cli("brief", FAKE_BEHAVIOR=behavior)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                meta, meta_path = self.metadata(result)
                self.assertEqual(meta["terminal_status"], "missing_session_id")
                self.assertNotEqual(meta["terminal_status"], "done")
                self.assertIn("session ID", meta["error"])
                self.assertEqual((meta_path.parent / "response.txt").read_text(), "advisor answer")

    def test_workspace_must_exist_and_be_a_directory_before_cursor_launch(self):
        cases = (
            (self.root / "missing", "workspace_missing"),
            (self.root / "not-a-directory", "workspace_not_directory"),
        )
        cases[1][0].write_text("file")
        for workspace, expected_status in cases:
            with self.subTest(workspace=workspace):
                result = self.run_cli("--workspace", str(workspace), "brief")
                self.assertNotEqual(result.returncode, 0)
                meta, _ = self.metadata(result)
                self.assertEqual(meta["terminal_status"], expected_status)
                self.assertIn(str(workspace.resolve()), meta["error"])
        self.assertFalse(self.log.exists(), "Cursor must not launch for an invalid workspace")

    def test_run_artifacts_are_private_even_with_permissive_umask(self):
        env = os.environ | {
            "FABLE_ADVISOR_AGENT_BIN": str(self.agent),
            "FABLE_ADVISOR_STATE_DIR": str(self.state),
            "FAKE_AGENT_LOG": str(self.log),
        }
        result = subprocess.run(
            [sys.executable, str(ADVISE), "brief"], text=True, capture_output=True,
            env=env, cwd=self.root, preexec_fn=lambda: os.umask(0),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        _, meta_path = self.metadata(result)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertEqual(meta_path.parent.stat().st_mode & 0o777, 0o700)
        for name in ("prompt.txt", "response.txt", "meta.json"):
            self.assertEqual((meta_path.parent / name).stat().st_mode & 0o777, 0o600, name)

    def test_failure_diagnostic_files_are_private(self):
        result = self.run_cli("brief", FAKE_BEHAVIOR="nonzero")
        self.assertEqual(result.returncode, 7)
        _, meta_path = self.metadata(result)
        for name in ("agent.stdout.txt", "agent.stderr.txt"):
            self.assertEqual((meta_path.parent / name).stat().st_mode & 0o777, 0o600, name)

    def test_safety_smoke_audit_is_private(self):
        audit_dir = self.root / "audits"
        env = os.environ | {
            "FABLE_ADVISOR_AGENT_BIN": str(self.agent),
            "FABLE_ADVISOR_SMOKE_AUDIT_DIR": str(audit_dir),
            "FAKE_AGENT_LOG": str(self.log),
            "FAKE_BEHAVIOR": "smoke",
        }
        result = subprocess.run(
            [str(SMOKE)], text=True, capture_output=True, env=env,
            cwd=self.root, preexec_fn=lambda: os.umask(0),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        audit_file = next(audit_dir.glob("smoke-*.json"))
        self.assertEqual(audit_dir.stat().st_mode & 0o777, 0o700)
        self.assertEqual(audit_file.stat().st_mode & 0o777, 0o600)

    def test_invocations_have_unique_metadata_and_capture_session(self):
        first = self.run_cli("brief one")
        second = self.run_cli("brief two")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        meta_one, path_one = self.metadata(first)
        meta_two, path_two = self.metadata(second)
        self.assertNotEqual(path_one.parent, path_two.parent)
        self.assertNotEqual(meta_one["run_id"], meta_two["run_id"])
        self.assertEqual(meta_one["returned_session_id"], "session-123")
        self.assertEqual(meta_one["terminal_status"], "done")
        self.assertTrue((path_one.parent / "prompt.txt").is_file())
        self.assertTrue((path_one.parent / "response.txt").is_file())
        for key in ("model", "workspace", "with_mcps", "started_at", "ended_at", "duration_seconds", "exit_code", "terminal_status"):
            self.assertIn(key, meta_one)


if __name__ == "__main__":
    unittest.main()
