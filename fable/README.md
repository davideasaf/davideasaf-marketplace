# Fable

Two complementary skills for consulting Cursor-hosted Fable 5:

- `fable-advisor` asks Fable for a bounded second opinion while the calling agent
  retains execution authority.
- `fable-orchestrator` lets Fable propose durable, multi-wave plans while a chief
  of staff controls permissions, worker launches, recovery, and approvals.

## Requirements

- Python 3.11+ on macOS or Linux.
- Cursor's `agent` CLI, authenticated with access to
  `claude-fable-5-thinking-high`.
- The `ask-codex` skill and Codex CLI for orchestrated worker programs.

The orchestrator uses the bundled advisor automatically. It looks for Ask Codex
at `~/.agents/skills/ask-codex/scripts/ask.sh` by default. Set
`FABLE_ORCHESTRATOR_ASK_CODEX` to another absolute wrapper path when needed.

MCP access is disabled by default. Enabling it requires an explicit trusted-server
allowlist and authorization for the complete configured MCP capability set,
because Cursor exposes blanket MCP approval rather than per-tool read-only
enforcement.

## Skills

- [Fable Advisor](skills/fable-advisor/SKILL.md)
- [Fable Orchestrator](skills/fable-orchestrator/SKILL.md)
- [Orchestration protocol](skills/fable-orchestrator/references/protocol.md)
