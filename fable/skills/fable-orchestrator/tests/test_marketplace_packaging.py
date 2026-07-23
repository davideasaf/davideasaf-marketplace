import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = SKILL_ROOT.parents[1]
ORCHESTRATE = SKILL_ROOT / "scripts" / "orchestrate.py"


def read_controller_defaults(env: dict[str, str]) -> dict[str, str]:
    program = (
        "import importlib.util, json\n"
        f"spec = importlib.util.spec_from_file_location('orchestrate_under_test', {str(ORCHESTRATE)!r})\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
        "print(json.dumps({"
        "'advisor': str(module.DEFAULT_ADVISOR_RUNNER), "
        "'ask_codex': str(module.DEFAULT_ASK_CODEX)"
        "}))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return json.loads(result.stdout)


class MarketplacePackagingTests(unittest.TestCase):
    def test_default_advisor_runner_is_plugin_relative(self):
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env["HOME"] = home
            env.pop("FABLE_ORCHESTRATOR_ADVISOR_RUNNER", None)
            env.pop("FABLE_ORCHESTRATOR_ASK_CODEX", None)
            defaults = read_controller_defaults(env)

        expected = PLUGIN_ROOT / "skills" / "fable-advisor" / "scripts" / "advise.py"
        self.assertEqual(Path(defaults["advisor"]), expected)

    def test_external_runner_paths_accept_environment_overrides(self):
        env = os.environ.copy()
        env["FABLE_ORCHESTRATOR_ADVISOR_RUNNER"] = "/tmp/custom-fable-advisor"
        env["FABLE_ORCHESTRATOR_ASK_CODEX"] = "/tmp/custom-ask-codex"
        defaults = read_controller_defaults(env)

        self.assertEqual(defaults["advisor"], "/tmp/custom-fable-advisor")
        self.assertEqual(defaults["ask_codex"], "/tmp/custom-ask-codex")

    def test_skill_invocations_are_plugin_relative(self):
        advisor_skill = (
            PLUGIN_ROOT / "skills" / "fable-advisor" / "SKILL.md"
        ).read_text(encoding="utf-8")
        orchestrator_skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        protocol = (SKILL_ROOT / "references" / "protocol.md").read_text(encoding="utf-8")

        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills/fable-advisor", advisor_skill)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills/fable-orchestrator", orchestrator_skill)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills/fable-orchestrator", protocol)
        for content in (advisor_skill, orchestrator_skill, protocol):
            self.assertNotIn("~/.agents/skills/fable-advisor", content)
            self.assertNotIn("~/.agents/skills/fable-orchestrator", content)

    def test_directly_invoked_scripts_are_executable(self):
        scripts = [
            PLUGIN_ROOT / "skills" / "fable-advisor" / "scripts" / "advise.py",
            SKILL_ROOT / "scripts" / "orchestrate.py",
            SKILL_ROOT / "scripts" / "private-ask.sh",
            SKILL_ROOT / "scripts" / "codex",
            SKILL_ROOT / "scripts" / "watchdog.py",
        ]
        for script in scripts:
            with self.subTest(script=script.name):
                self.assertTrue(script.stat().st_mode & stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
