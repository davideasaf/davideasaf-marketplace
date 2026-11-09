import concurrent.futures
import shlex
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class MetadataConcurrencyTest(unittest.TestCase):
    def test_missing_child_exit_is_not_reported_as_success(self):
        wrapper = Path(__file__).with_name("ask.sh")
        definitions = "export ASK_CLAUDE_HELPER=" + shlex.quote(str(wrapper.with_name("lifecycle.py"))) + "\n" + wrapper.read_text().split("# ----------------------------- dispatch")[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "meta.json").write_text('{"status":"running"}')
            (root / "events.jsonl").write_text("")
            script = root / "finalize.sh"
            script.write_text(definitions + '\nfinalize_run "$1"\n')
            result = subprocess.run(["bash", str(script), str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            meta = json.loads((root / "meta.json").read_text())
            self.assertEqual(meta["status"], "failed")

    def test_child_failure_records_exit_code_and_failed_status(self):
        wrapper = Path(__file__).with_name("ask.sh")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            fake_claude = fake_bin / "claude"
            fake_claude.write_text("#!/bin/sh\nexit 42\n")
            fake_claude.chmod(0o755)
            env = {
                **os.environ,
                "ASK_RUN_ROOT": str(root / "runs"),
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
            }
            started = subprocess.run(
                ["bash", str(wrapper), "start", "diagnostic prompt"],
                capture_output=True, text=True, env=env, check=True,
            )
            run_id = next(line.split("=", 1)[1] for line in started.stdout.splitlines()
                          if line.startswith("RUN_ID="))
            subprocess.run(
                ["bash", str(wrapper), "wait", run_id, "--timeout", "10"],
                capture_output=True, text=True, env=env,
            )
            meta = json.loads((root / "runs" / "claude" / run_id / "meta.json").read_text())
            self.assertEqual(meta["status"], "failed")
            self.assertEqual(meta["exit_code"], 42)

    def test_multiline_final_response_is_not_truncated(self):
        wrapper = Path(__file__).with_name("ask.sh")
        definitions = "export ASK_CLAUDE_HELPER=" + shlex.quote(str(wrapper.with_name("lifecycle.py"))) + "\n" + wrapper.read_text().split("# ----------------------------- dispatch")[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "meta.json").write_text('{"status":"running"}')
            response = "Review complete.\n\nFinding one.\nFinding two."
            (root / "events.jsonl").write_text(json.dumps({
                "type": "result", "is_error": False, "result": response,
            }) + "\n")
            script = root / "finalize.sh"
            script.write_text(definitions + '\nfinalize_run "$1"\n')
            result = subprocess.run(["bash", str(script), str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "final.txt").read_text().strip(), response)

    def test_concurrent_updates_preserve_every_field(self):
        wrapper = Path(__file__).with_name("ask.sh")
        definitions = "export ASK_CLAUDE_HELPER=" + shlex.quote(str(wrapper.with_name("lifecycle.py"))) + "\n" + wrapper.read_text().split("# ----------------------------- dispatch")[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "meta.json").write_text('{"status":"running"}')
            script = root / "update.sh"
            script.write_text(definitions + '\nwrite_meta_num "$1" "$2" "$3"\n')
            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                results = list(pool.map(
                    lambda i: subprocess.run(
                        ["bash", str(script), str(root), f"field_{i}", str(i)],
                        capture_output=True, text=True,
                    ), range(24)
                ))
            self.assertTrue(all(r.returncode == 0 for r in results),
                            "\n".join(r.stderr for r in results))
            actual = json.loads((root / "meta.json").read_text())
            self.assertEqual(actual, {"status": "running", **{f"field_{i}": i for i in range(24)}})


if __name__ == "__main__":
    unittest.main()
