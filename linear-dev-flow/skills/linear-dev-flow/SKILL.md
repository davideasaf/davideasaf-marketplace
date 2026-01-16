---
name: linear-dev-flow
description: Manages Linear issue-based development workflows with workflow state integration, worktree isolation, and structured planning phases. This skill should be used when working on Linear issues, creating implementation plans, executing development tasks, or managing issue state transitions. Supports manual pickup from Todo (planning) and Dev Ready (implementation).
---

# Linear Dev Flow

Autonomous development workflow for Linear issues with structured planning, implementation, and review phases. Manages issue state transitions through Linear's workflow states.

## Execution Environment

This skill primarily works locally with git worktrees for isolation:

| Environment | Isolation | When to Use |
|-------------|-----------|-------------|
| **Local (CLI)** | Git worktrees | Working on issues with isolated directories |

**Local:** Use `worktree_manager.py` to create isolated directories with `.worktreeinclude` secrets copied.

## Workflow States

```
Backlog → Todo → Dev Ready → In Progress → In Review → Done
```

| Column | Owner | Agent Action |
|--------|-------|--------------|
| **Backlog** | Human | None - human managed |
| **Todo** | Human → Agent | Analyze issue, build plan, post as comment |
| **Dev Ready** | Agent | PICKUP - Create worktree, implement, move to In Review |
| **In Progress** | Agent | Active implementation (transient state) |
| **In Review** | Human | STOP - Human validates, approves or returns |
| **Done** | Archive | Complete |

## Agent Pickup Points

The agent picks up work from two states (manual trigger only):

1. **Todo** → Analyze, build plan, add as comment, STOP (wait for human to move to Dev Ready)
2. **Dev Ready** → Create worktree, implement, move to In Progress, complete, move to In Review, STOP

## Manual Pickup Logic

When asked to pick up an issue:

1. **Find ready issues:** Query issues in pickup states (Todo, Dev Ready)
2. **Sort by priority:**
   - Linear priority: Urgent > High > Medium > Low > No priority
   - If same priority, use issue creation date (oldest first)
3. **Select top item:** Work on highest priority issue

To find the next issue to work on:
```bash
uv run python scripts/linear_dev.py pickup
uv run python scripts/linear_dev.py pickup --status "Dev Ready"
```

## Branch Naming Convention

**Format:** `issue/<identifier>-<slug>`

The identifier is lowercase (e.g., "asa-42"), and slug is derived from the issue title.

**Examples:**
- Issue ASA-42 "Fix login bug" → `issue/asa-42-fix-login-bug`
- Issue ASA-123 "Add dark mode support" → `issue/asa-123-add-dark-mode-support`

## Core Operations

### Discover Work

```bash
# List issues in Todo state (ready for planning)
uv run python scripts/linear_dev.py list --status "Todo"

# List issues in Dev Ready state (ready for implementation)
uv run python scripts/linear_dev.py list --status "Dev Ready"

# Find next issue to pickup (auto-selects by priority)
uv run python scripts/linear_dev.py pickup

# List available workflow states
uv run python scripts/linear_dev.py states
```

### View Issue Details

```bash
# Show issue with full details and comments
uv run python scripts/linear_dev.py show ASA-42
```

### Planning Phase (Todo → Todo with plan)

When asked to plan an issue in Todo:

1. **Show issue details**
   ```bash
   uv run python scripts/linear_dev.py show ASA-42
   ```

2. **Analyze issue**
   - Read issue description and all comments
   - Understand acceptance criteria
   - Identify any blockers or dependencies

3. **Generate implementation plan** using the Plan Template below

4. **Submit plan as comment**
   ```bash
   uv run python scripts/linear_dev.py comment ASA-42 --file plan.md
   # OR
   uv run python scripts/linear_dev.py comment ASA-42 --body "## Implementation Plan..."
   ```

5. **STOP** - Wait for human to review plan and move to Dev Ready

### Implementation Phase (Dev Ready → In Progress → In Review)

When asked to implement an issue in Dev Ready:

1. **Move to In Progress**
   ```bash
   uv run python scripts/linear_dev.py move ASA-42 --to "In Progress"
   ```

2. **Create worktree**
   ```bash
   uv run python scripts/worktree_manager.py create ASA-42
   cd ../<repo>-issue-asa-42-<slug>/
   ```

3. **Read the approved plan**
   ```bash
   uv run python scripts/linear_dev.py show ASA-42
   ```
   Review the plan comment that was previously approved.

4. **Execute implementation**
   - Follow the approved plan exactly
   - Make atomic commits with clear messages
   - Run tests after each significant change

5. **Run validation**
   - Execute all test suites
   - Run linting/type checking if configured
   - Verify build succeeds

6. **Push branch**
   ```bash
   git push -u origin issue/asa-42-<slug>
   ```

7. **Post completion and move to In Review**
   ```bash
   uv run python scripts/linear_dev.py complete ASA-42 \
     --summary "Implemented feature X with tests" \
     --confidence 85
   ```
   This:
   - Posts completion comment to issue
   - Moves issue to In Review

8. **STOP** - Wait for human review

### Review Feedback (In Review → Dev Ready → In Review)

When a human reviewer has feedback:

1. **Human provides feedback**
   - Comment on the Linear issue with change requests
   - Move issue back to "Dev Ready" state

2. **Agent picks up returning issue**

   When picking up from Dev Ready, check if this is a returning issue:
   ```bash
   uv run python scripts/linear_dev.py show ASA-42
   ```

   Signs of a returning issue:
   - Existing branch `issue/asa-<number>-*` exists
   - Previous implementation/completion comments exist

3. **Agent reads all feedback**
   Review all comments on the issue.

4. **Agent addresses feedback**
   ```bash
   # Navigate to existing worktree (create if needed)
   uv run python scripts/worktree_manager.py create ASA-42
   cd ../<repo>-issue-asa-42-<slug>/

   # Pull latest changes
   git pull origin issue/asa-42-<slug>

   # Make changes addressing feedback
   # ... implement fixes ...

   # Commit and push
   git add .
   git commit -m "Address review feedback: <summary>"
   git push
   ```

5. **Agent posts update and moves back to In Review**
   ```bash
   uv run python scripts/linear_dev.py comment ASA-42 --body "Addressed feedback: <summary>"
   uv run python scripts/linear_dev.py move ASA-42 --to "In Review"
   ```

6. **STOP** - Wait for human to re-review

## Plan Template

When creating implementation plans:

```markdown
## Implementation Plan for <identifier>: <title>

### Summary
<1-2 sentence overview of the approach>

### Tasks

1. **<Task description>**
   - File: `path/to/file.ts`
   - Changes: <what will be modified>
   - Validation: <how to verify>

2. **<Task description>**
   ...

### Test Strategy

**For Frontend tasks:**
- E2E tests: `e2e/<feature>.spec.ts` - <user flows covered>
- Component tests: `src/components/__tests__/` - <components tested>

**For Backend tasks:**
- Unit tests: `tests/unit/` - <functions tested>
- Integration tests: `tests/integration/` - <flows tested>

### Risks & Considerations
- <Potential blockers or dependencies>
- <Edge cases to handle>

### Estimated Scope
- Files: <count>
- Complexity: Low/Medium/High
```

## Completion Template

When completing work, the `complete` command posts this structure:

```markdown
## Implementation Complete for <identifier>

### Summary
<Brief description of what was implemented>

### Confidence Score: <0-100>/100

### Ready for Review
- Branch: `issue/<identifier>-<slug>`
- Issue: <Linear URL>

---
*Awaiting human review. Move to Done if acceptable, or back to Dev Ready with feedback.*
```

## Worktree Management

### .worktreeinclude File

Create this file in your repository root to specify which gitignored files to copy to new worktrees:

```
# Files to copy to new git worktrees
# Only files matching BOTH this file AND .gitignore are copied

# Environment variables
.env
.env.*

# Credentials
credentials/
secrets/

# Local configs
*.local.json
```

### Worktree Operations

```bash
# Create worktree for issue
uv run python scripts/worktree_manager.py create ASA-42

# List active worktrees
uv run python scripts/worktree_manager.py list

# Remove worktree after merge
uv run python scripts/worktree_manager.py remove ASA-42
```

## State Transitions

```bash
# Move issue to workflow state
uv run python scripts/linear_dev.py move ASA-42 --to "In Progress"
uv run python scripts/linear_dev.py move ASA-42 --to "In Review"
uv run python scripts/linear_dev.py move ASA-42 --to "Dev Ready"
```

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `linear_api.py` | Linear GraphQL API client |
| `linear_dev.py` | Issue operations: list, pickup, show, comment, complete, move, states |
| `workflow_states.py` | Workflow state mapping and transitions |
| `worktree_manager.py` | Worktree creation with .worktreeinclude support |

## Environment Requirements

### Authentication (one required, in priority order)

| Method | Variables | Token Validity | Use Case |
|--------|-----------|----------------|----------|
| Pre-generated token | `LINEAR_OAUTH_ACCESS_TOKEN` | 10 years | Quick setup with existing token |
| Client Credentials | `LINEAR_OAUTH_CLIENT_ID` + `LINEAR_OAUTH_CLIENT_SECRET` | 30 days (auto-refreshed) | Recommended for automation |
| Personal API key | `LINEAR_API_KEY` | Indefinite | Posts as your user account |

#### Client Credentials Setup (Recommended)

For Claude to post as an OAuth application using client credentials:

1. Go to **Linear Settings → API → OAuth Applications**
2. Create a new OAuth application (or use existing)
3. Copy the **Client ID** and **Client Secret**
4. Set both environment variables:

```bash
export LINEAR_OAUTH_CLIENT_ID="your_client_id_here"
export LINEAR_OAUTH_CLIENT_SECRET="your_client_secret_here"
```

The skill automatically exchanges these credentials for a 30-day access token.

#### Pre-generated Token Setup

If you already have a developer token (from Linear's OAuth app settings):

```bash
export LINEAR_OAUTH_ACCESS_TOKEN="lin_oauth_xxxxx..."
```

#### Personal API Key Setup

For Claude to post as your personal user:

1. Go to **Linear Settings → API → Personal API Keys**
2. Create a new API key
3. Set `LINEAR_API_KEY` to the generated key

```bash
export LINEAR_API_KEY="lin_api_xxxxx..."
```

### Optional Configuration

| Variable | Description |
|----------|-------------|
| `LINEAR_TEAM_KEY` | Team key (e.g., "ASA"). Defaults to first team if not set. |

### Other Requirements

- Python 3.10+ with `uv` package manager
- Git with worktree support (v2.5+)
- **git-worktree skill** installed at `~/.claude/skills/git-worktree/` (for worktree creation with `.worktreeinclude` support)

## Example Invocations

```
"Plan issue ASA-42"
→ Analyzes issue, creates implementation plan, posts as comment

"Pick up next Linear issue"
→ Finds highest priority issue in Todo or Dev Ready

"Work on ASA-42"
→ Implements the approved plan for ASA-42

"Complete ASA-42"
→ Posts completion comment, moves to In Review

"List Dev Ready issues"
→ Shows all issues ready for implementation

"Move ASA-42 to In Progress"
→ Transitions issue state
```
