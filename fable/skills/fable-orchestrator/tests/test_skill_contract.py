from pathlib import Path
import re
import stat
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
PROTOCOL = ROOT / "references" / "protocol.md"
SCRIPT = ROOT / "scripts" / "orchestrate.py"


class SkillContractTests(unittest.TestCase):
    def test_frontmatter_is_discoverable_and_trigger_only(self):
        text = SKILL.read_text()
        match = re.match(r"---\nname: ([^\n]+)\ndescription: ([^\n]+)\n---", text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "fable-orchestrator")
        self.assertTrue(match.group(2).startswith("Use when "))
        self.assertLess(len(match.group(2)), 500)
        self.assertNotIn("dispatches workers", match.group(2).lower())

    def test_skill_teaches_mediated_authority_and_recovery(self):
        text = SKILL.read_text().lower()
        required = [
            "chief of staff",
            "fable proposes",
            "codex launches",
            "source of truth",
            "cycle_id",
            "dispatch_launching",
            "ask_run_root",
            "cold-start",
            "one repair",
            "separate session",
            "shared foundation",
            "human gate",
            "approve-plan",
            "approve-retry",
            "exact trusted servers",
            "untrusted data",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_workspace_and_mcps_are_conditional(self):
        text = SKILL.read_text().lower()
        self.assertIn("active workspace or worktree", text)
        self.assertIn("mcps are disabled by default", text)
        self.assertIn("trusted", text)
        self.assertIn("user authorization", text)

    def test_rereview_contract_is_explicit_in_skill_and_protocol(self):
        combined = (SKILL.read_text() + "\n" + PROTOCOL.read_text()).lower()
        for phrase in (
            "--ignore-user-config",
            "zero user-configured external capabilities",
            "watchdog",
            "reserved_worker_seconds",
            "token telemetry",
            "approve-budget",
            "gate_id",
            "ordered durable set",
            "schema_failure",
            "reconcile-turn",
            "full mutating capability",
            "structured truncation",
            "isolation.json",
            "watchdog.json",
            "supervision.json",
            "setsid",
            "process group",
            "term",
            "kill",
            "manifest-derived plan gate",
            "explicit cancel",
            "cancelled status",
            "termination_verified",
            "exact_protocol_v1_json_template",
            "exact_status_gate_dispatch_cardinality",
            "aliases_forbidden",
            "all required exact keys and types",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, combined)

    def test_unsafe_cursor_flag_is_absent(self):
        for path in (SKILL, PROTOCOL, SCRIPT):
            self.assertNotIn("--yolo", path.read_text())

    def test_protocol_reference_resolves_and_documents_contract(self):
        text = PROTOCOL.read_text().lower()
        for phrase in (
            "protocol_version",
            "ready_for_dispatch",
            "dispatch_id",
            "program nonce",
            "ledger.jsonl",
            "reconciliation",
            "verbatim",
            "prompt hash",
            "ask-runs/codex",
            "manifest_accepted",
            "private-ask.sh",
            "budget_warning_ratio",
            "dispatch_reconciled_no_match",
            "budget_revision_approved",
            "fable_turn_lease_reconciled",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_cli_is_executable(self):
        mode = stat.S_IMODE(SCRIPT.stat().st_mode)
        self.assertTrue(mode & stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
