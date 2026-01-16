# Linear Dev Flow

A Claude Code plugin for managing Linear issue-based development workflows with workflow state integration, worktree isolation, and structured planning phases.

## Features

- **Kanban Workflow**: Backlog → Todo → Dev Ready → In Progress → In Review → Done
- **Plan-then-Execute**: Agent creates implementation plans in Todo for human approval
- **Manual Pickup**: Agent picks up Dev Ready issues when triggered
- **Worktree Isolation**: Create isolated work directories for parallel development
- **Completion Workflow**: Agent moves to In Review for human validation

## Installation

Add this plugin to your Claude Code configuration:

```bash
claude plugin add /path/to/davideasaf-marketplace/linear-dev-flow
```

Or symlink to your plugins directory:

```bash
ln -s /path/to/davideasaf-marketplace/linear-dev-flow ~/.claude/plugins/linear-dev-flow
```

## Skills Included

### `linear-dev-flow`

Main workflow skill for working on Linear issues.

**Triggers:**
- "Plan issue ASA-42"
- "Pick up next Linear issue"
- "Work on ASA-42"
- "Complete ASA-42"
- "List Dev Ready issues"

## Commands Included

### `/linear-dev-doctor`

Environment diagnostic tool to verify setup.

**Usage:**
```
/linear-dev-doctor
```

Checks:
- Linear authentication (OAuth token or API key)
- API connection validity
- Team access
- Required workflow states exist
- Python/uv installation
- Git worktree support

## Setup Requirements

1. **Linear Authentication** (one of, in priority order):
   - **Client Credentials** (recommended):
     ```bash
     export LINEAR_OAUTH_CLIENT_ID=your_client_id
     export LINEAR_OAUTH_CLIENT_SECRET=your_client_secret
     ```
     - Auto-exchanges for 30-day token, posts as application
     - Get from: Linear Settings → API → OAuth Applications
   - **OAuth Token**: `export LINEAR_OAUTH_ACCESS_TOKEN=lin_oauth_xxxxx`
     - Pre-generated token, posts as application
     - Get from: Linear Settings → API → OAuth Applications → Developer token
   - **Personal API Key**: `export LINEAR_API_KEY=lin_api_xxxxx`
     - Posts as your personal user
     - Get from: Linear Settings → API → Personal API Keys
2. **Python 3.10+**: With `uv` package manager
3. **Workflow States**: Configure these in your Linear team:
   - Backlog
   - Todo
   - Dev Ready
   - In Progress
   - In Review
   - Done (or Completed)

## Workflow States

```
Backlog → Todo → Dev Ready → In Progress → In Review → Done
```

| Column | Owner | Agent Action |
|--------|-------|--------------|
| **Backlog** | Human | None - human managed |
| **Todo** | Human → Agent | Agent creates plan, posts as comment |
| **Dev Ready** | Agent | Pick up (manual), create worktree, implement |
| **In Progress** | Agent | Active implementation |
| **In Review** | Human | Validate, approve to Done or return to Dev Ready |
| **Done** | Archive | Cleanup |

## Scripts

| Script | Purpose |
|--------|---------|
| `linear_api.py` | Linear GraphQL API client |
| `linear_dev.py` | Issue operations: list, show, plan, pickup, comment, complete, move |
| `workflow_states.py` | Workflow state mapping and transitions |
| `worktree_manager.py` | Create/remove worktrees with secrets copied |

## Example Usage

```bash
# List issues by status
uv run python scripts/linear_dev.py list --status "Dev Ready"

# Show issue details
uv run python scripts/linear_dev.py show ASA-42

# Create plan for issue
uv run python scripts/linear_dev.py plan ASA-42

# Pick up next Dev Ready issue
uv run python scripts/linear_dev.py pickup

# Move issue to status
uv run python scripts/linear_dev.py move ASA-42 --to "In Progress"

# Complete issue
uv run python scripts/linear_dev.py complete ASA-42 \
  --summary "Implemented feature X" \
  --confidence 85

# Create worktree for issue
uv run python scripts/worktree_manager.py create ASA-42
```

## Environment Variables

```bash
# Authentication (one required, in priority order)
# Option 1: Client Credentials (recommended - auto-exchanges for 30-day token)
export LINEAR_OAUTH_CLIENT_ID=your_client_id
export LINEAR_OAUTH_CLIENT_SECRET=your_client_secret

# Option 2: Pre-generated OAuth token
export LINEAR_OAUTH_ACCESS_TOKEN=lin_oauth_xxxxx

# Option 3: Personal API key (posts as your user)
export LINEAR_API_KEY=lin_api_xxxxx

# Optional - defaults to first team if not set
export LINEAR_TEAM_KEY=ASA
```

## License

MIT
