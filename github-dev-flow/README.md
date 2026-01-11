# GitHub Dev Flow

A Claude Code plugin for managing GitHub issue-based development workflows with project board integration, worktree isolation, and structured planning phases.

## Features

- **Kanban Workflow**: Todo → Planning → Dev Ready → In Progress → Review → Done
- **Auto-Pickup**: Automatically selects highest priority issues from pickup columns
- **Worktree Isolation**: Create isolated work directories for parallel development
- **Plan-then-Execute**: Generate implementation plans for human approval before coding
- **PR Automation**: Creates PRs with confidence scores on completion
- **GitHub Actions Support**: Works with @claude mentions in issues/PRs

## Installation

Add this plugin to your Claude Code configuration:

```bash
claude plugin add /path/to/davideasaf-marketplace/github-dev-flow
```

Or symlink to your plugins directory:

```bash
ln -s /path/to/davideasaf-marketplace/github-dev-flow ~/.claude/plugins/github-dev-flow
```

## Skills Included

### `github-dev-flow`

Main workflow skill for working on GitHub issues.

**Triggers:**
- "Tackle an issue in milestone 'Phase 1'"
- "Work on issue #42"
- "Complete all Dev Ready issues"
- "Report on Phase 1 status"

### `create-gh-issue`

Create well-documented GitHub issues with evidence collection and structured formatting.

**Triggers:**
- "Create a bug report for the login issue"
- "File a feature request for dark mode"
- "Document this bug with screenshots"

## Commands Included

### `/github-dev-doctor`

Environment diagnostic tool to verify setup.

**Usage:**
```
/github-dev-doctor
```

Checks:
- GitHub CLI installation and authentication
- Project scope enabled
- Repository access
- Project board configuration
- Python/uv installation
- Worktree configuration

## Setup Requirements

1. **GitHub CLI**: `brew install gh` (macOS) or visit https://cli.github.com/
2. **Authenticate**: `gh auth login`
3. **Enable project scope**: `gh auth refresh -s project`
4. **Python 3.10+**: With `uv` package manager
5. **Project Board**: Create a GitHub Project with columns:
   - Todo
   - Planning
   - Dev Ready
   - In Progress
   - Review
   - Done

## Workflow States

```
Todo → Planning → Dev Ready → In Progress → Review → Done
```

| Column | Owner | Agent Action |
|--------|-------|--------------|
| **Todo** | Agent | Analyze issue, build plan, move to Planning |
| **Planning** | Human | Review plan, approve or provide feedback |
| **Dev Ready** | Agent | Create worktree, implement, create PR |
| **In Progress** | Agent | Active implementation |
| **Review** | Human | Review PR, merge to main |
| **Done** | Archive | Cleanup |

## Scripts

| Script | Purpose |
|--------|---------|
| `gh_dev.py` | Issue operations: list, pickup, show, comment, complete, images, report |
| `worktree_manager.py` | Create/remove worktrees with secrets copied |
| `project_board.py` | Move issues between project board columns |

## Example Usage

```bash
# Find next issue to work on
uv run python scripts/gh_dev.py pickup --milestone "Phase 1"

# Show issue details
uv run python scripts/gh_dev.py show 42

# Download images from issue
uv run python scripts/gh_dev.py images 42 --output ./issue-images/

# Create worktree for issue
uv run python scripts/worktree_manager.py create 42

# Move issue to column
uv run python scripts/project_board.py move 42 --to "in progress"

# Complete issue with PR
uv run python scripts/gh_dev.py complete 42 \
  --summary "Implemented feature X" \
  --confidence 85 \
  --test-results "All tests passing"
```

## GitHub Actions

Add to `.github/workflows/claude.yml`:

```yaml
permissions:
  contents: write
  pull-requests: write
  issues: write
```

See `skills/github-dev-flow/references/github-actions-setup.md` for full configuration.

## License

MIT
