---
name: github-dev-flow
description: Manages GitHub issue-based development workflows with project board integration, worktree isolation, and structured planning phases. This skill should be used when working on GitHub issues, managing project board columns, creating implementation plans, executing development tasks, or coordinating autonomous development cycles. Supports single issue work, batch processing, milestone completion, and status reporting.
---

# GitHub Dev Flow

Autonomous development workflow for GitHub issues with structured planning, implementation, and review phases. Manages issue state transitions through project board columns.

## Execution Environments

This skill works in two environments with different isolation strategies:

| Environment | Isolation | When to Use |
|-------------|-----------|-------------|
| **Local (CLI)** | Git worktrees | Working on multiple issues in parallel locally |
| **Remote (GitHub Actions, Cloud)** | Git branches | @claude mentions, CI/CD triggered work |

**Local:** Use `worktree_manager.py` to create isolated directories with `.worktreeinclude` secrets copied.

**Remote:** Skip worktrees - the runner already has a fresh checkout. Just create a branch and work directly.

## Workflow States

```
Todo → Planning → Dev Ready → In Progress → Review → Done
```

| Column | Owner | Agent Action |
|--------|-------|--------------|
| **Todo** | Agent PICKUP | Analyze issue, build plan, move to Planning |
| **Planning** | Human | STOP - Wait for human to review plan |
| **Dev Ready** | Agent PICKUP | Create worktree, implement, create PR, move to Review |
| **In Progress** | Agent | Active implementation (transient state) |
| **Review** | Human | STOP - Human reviews PR, merges to main |
| **Done** | Archive | PR merged, cleanup worktree |

## Agent Pickup Points

The agent picks up work from two columns:

1. **Todo** → Build plan, add as comment, move to Planning, STOP
2. **Dev Ready** → Create worktree, implement, push branch, create PR, move to Review, STOP

## Auto-Pickup Logic

When invoked with a target (e.g., "tackle an issue in milestone 'Phase 1'"):

1. **Find ready issues:** Query issues in pickup columns (Todo, Dev Ready)
2. **Apply filters:** Milestone, labels, assignee, etc.
3. **Sort by priority:**
   - Labels: `priority:critical` > `priority:high` > `priority:medium` > `priority:low`
   - If no priority labels, use issue creation date (oldest first)
4. **Select top item:** Work on highest priority issue
5. **Tie-breaker:** If same priority, pick oldest issue

To find the next issue to work on:
```bash
uv run python scripts/gh_dev.py pickup --milestone "Phase 1"
```

## Branch Naming Convention

**Format:** `issue/<number>-<slug>`

The slug is derived from the issue title: lowercase, spaces to hyphens, special characters removed, truncated to 50 chars.

**Examples:**
- Issue #42 "Fix login bug" → `issue/42-fix-login-bug`
- Issue #123 "Add dark mode support" → `issue/123-add-dark-mode-support`

## Core Operations

### Discover Work

```bash
# List issues in Todo column (ready for planning)
uv run python scripts/gh_dev.py list --status todo

# List issues in Dev Ready column (ready for implementation)
uv run python scripts/gh_dev.py list --status "ready for dev"

# List issues in a specific milestone
uv run python scripts/gh_dev.py list --milestone "Phase 1"

# Find next issue to pickup (auto-selects by priority)
uv run python scripts/gh_dev.py pickup

# Get issue report by status/labels
uv run python scripts/gh_dev.py report --milestone "Phase 1"
```

### View Issue Details

```bash
# Show issue with full details
uv run python scripts/gh_dev.py show 42

# Download images from issue for analysis
uv run python scripts/gh_dev.py images 42 --output ./issue-images/
```

### Planning Phase (Todo → Planning)

To pick up an issue and create a plan:

1. **Set up workspace**

   **Local (CLI):** Create worktree for isolation
   ```bash
   uv run python scripts/worktree_manager.py create 42
   cd ../<repo>-issue-42-<slug>/
   ```

   **Remote (GitHub Actions):** Create branch directly
   ```bash
   git checkout -b issue/42-<slug>
   ```

2. **Analyze issue**
   - Read issue body and all comments
   - Download and analyze any attached images
   - Identify sub-issues if linked
   - Understand acceptance criteria

3. **Generate implementation plan** using the Plan Template below

4. **Submit plan as comment**
   ```bash
   uv run python scripts/gh_dev.py comment 42 --file plan.md
   ```

5. **Move to Planning**
   ```bash
   uv run python scripts/project_board.py move 42 --to planning
   ```

6. **STOP** - Wait for human review

### Implementation Phase (Dev Ready → In Progress → Review)

To implement an approved plan:

1. **Move to In Progress**
   ```bash
   uv run python scripts/project_board.py move 42 --to "in progress"
   ```

2. **Ensure workspace is ready**

   **Local (CLI):** Create worktree if it doesn't exist, then navigate
   ```bash
   # Create worktree (idempotent - skips if already exists)
   uv run python scripts/worktree_manager.py create 42
   cd ../<repo>-issue-42-<slug>/
   ```

   **Remote (GitHub Actions):** Checkout the branch
   ```bash
   git checkout issue/42-<slug> || git checkout -b issue/42-<slug>
   ```

3. **Execute implementation**
   - Follow the approved plan exactly
   - Make atomic commits with clear messages
   - Run tests after each significant change
   - No human intervention expected

4. **Run validation**
   - Execute all test suites
   - Run linting/type checking if configured
   - Verify build succeeds

5. **Push and create PR**
   ```bash
   git push -u origin issue/42-<slug>
   ```

6. **Post completion and create PR**
   ```bash
   uv run python scripts/gh_dev.py complete 42 \
     --summary "Implemented feature X with tests" \
     --confidence 85 \
     --test-results "All 42 tests passing"
   ```
   This:
   - Posts completion comment to issue
   - Creates PR linking to issue (`Closes #42`)
   - Moves issue to Review

7. **STOP** - Wait for human review

### Review Feedback (Review → Dev Ready → Review)

When a human reviewer has feedback on a PR:

1. **Human provides feedback**
   - Comment on the GitHub issue OR the PR with change requests
   - Move issue back to "Dev Ready" column

2. **Agent picks up returning issue**

   When picking up from Dev Ready, first check if this is a returning issue:
   ```bash
   # Check for existing work (shows branch, PR, comments)
   uv run python scripts/gh_dev.py show 42

   # Check for open PR
   gh pr list --head issue/42-* --state open
   ```

   Signs of a returning issue:
   - Existing branch `issue/<number>-*` exists
   - Open PR exists for the issue
   - Previous implementation/completion comments exist

   **If returning issue:** Read all feedback before making changes
   **If new issue:** Proceed with normal implementation

3. **Agent reads all feedback**
   ```bash
   # Review issue comments
   gh issue view 42 --comments

   # Review PR comments (if PR exists)
   gh pr view <pr-number> --comments
   ```

4. **Agent addresses feedback**
   ```bash
   # Navigate to existing worktree (create if needed - idempotent)
   uv run python scripts/worktree_manager.py create 42
   cd ../<repo>-issue-42-<slug>/

   # Pull latest changes
   git pull origin issue/42-<slug>

   # Make changes addressing feedback
   # ... implement fixes ...

   # Commit and push (PR auto-updates)
   git add .
   git commit -m "Address review feedback: <summary>"
   git push
   ```

5. **Agent posts update and moves back to Review**
   ```bash
   # Comment on issue with changes made
   uv run python scripts/gh_dev.py comment 42 --body "Addressed feedback: <summary of changes>"

   # Move back to Review
   uv run python scripts/project_board.py move 42 --to review
   ```

6. **STOP** - Wait for human to re-review

This cycle repeats until the human merges the PR.

## Plan Template

When creating implementation plans, follow this structure.

**Include the UI/UX Preview section when:**
- Issue involves visual/styling changes
- New UI components are being added
- Layout or user flow is changing
- Issue has attached mockups or screenshots

**Skip the UI/UX Preview section when:**
- Backend-only changes
- API/data layer work
- Infrastructure/config changes

**Tip:** Download attached images from the issue for reference:
```bash
uv run python scripts/gh_dev.py images 42 --output ./issue-images/
```

```markdown
## Implementation Plan for #<number>: <title>

### Summary
<1-2 sentence overview of the approach>

### Tasks

1. **<Task description>**
   - File: `path/to/file.ts`
   - Changes: <what will be modified>
   - Validation: <how to verify>

2. **<Task description>**
   ...

### Sub-Issues (if applicable)
- [ ] #<sub-issue-1>: <title>
- [ ] #<sub-issue-2>: <title>

### Test Strategy

**For Frontend tasks:**
- E2E tests: `e2e/<feature>.spec.ts` - <user flows covered>
- Component tests: `src/components/__tests__/` - <components tested>

**For Backend tasks:**
- Unit tests: `tests/unit/` - <functions tested>
- Integration tests: `tests/integration/` - <flows tested>

### UI/UX Preview (for visual changes)

**Current State:**
<screenshot or description of current UI>

**Proposed Changes:**
- Component: `<ComponentName>` → <what changes>
- Layout: <layout modifications>
- Styling: <color/spacing/typography changes>

**Visual Mockup:**
```
┌─────────────────────────────┐
│  <ASCII representation>     │
│  of the proposed UI         │
└─────────────────────────────┘
```

**User Flow Impact:**
1. User does X → sees Y (new/changed)
2. User does Z → sees W (unchanged)

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
## Implementation Complete for #<number>

### Summary
<Brief description of what was implemented>

### Changes Made
- `path/to/file1.ts` - <what changed>
- `path/to/file2.ts` - <what changed>

### Test Results
```
<test output summary>
```

### Confidence Score: <0-100>/100

**Justification:** <Brief explanation of confidence level>

### Ready for Review
- Branch: `issue/<number>-<slug>`
- PR: <link to PR>
```

## Handling Sub-Issues

When an issue has linked sub-issues (child issues):

1. List sub-issues in the plan
2. Plan addresses all sub-issues collectively
3. Track completion of each sub-issue
4. Only mark parent complete when all children done

## Batch Processing

To work on multiple issues:

```bash
# Process all Dev Ready issues
uv run python scripts/gh_dev.py list --status "dev ready" --format json | \
  jq -r '.[].number' | while read issue; do
    echo "Processing issue #$issue"
    # ... implement each issue ...
done
```

For milestones:
```bash
# List all issues in a milestone
uv run python scripts/gh_dev.py list --milestone "v1.0"
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
uv run python scripts/worktree_manager.py create 42

# List active worktrees
uv run python scripts/worktree_manager.py list

# Remove worktree after merge
uv run python scripts/worktree_manager.py remove 42
```

## Project Board Operations

```bash
# List available columns
uv run python scripts/project_board.py columns

# Move issue to column
uv run python scripts/project_board.py move 42 --to "in progress"
uv run python scripts/project_board.py move 42 --to review
```

## Status Reporting

```bash
# Get report on all issues
uv run python scripts/gh_dev.py report

# Get report for a milestone
uv run python scripts/gh_dev.py report --milestone "Phase 1"
```

The report shows:
- Issues by status column
- Issues by label
- Blocked/stale issues

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `gh_dev.py` | Issue operations: list, pickup, show, comment, complete, images, report |
| `worktree_manager.py` | Worktree creation with .worktreeinclude support |
| `project_board.py` | GitHub Projects V2 column transitions |

## Environment Requirements

- `gh` CLI authenticated with repo access
- `gh auth status` shows logged in
- Project scope enabled: `gh auth refresh -s project`
- Python 3.10+ with `uv` package manager

## GitHub Actions Integration

To enable @claude mentions in GitHub issues/PRs, ensure your `.github/workflows/claude.yml` has write permissions:

```yaml
permissions:
  contents: write      # Create branches, commit code
  pull-requests: write # Create/update PRs
  issues: write        # Comment on issues, update project board
```

See `references/github-actions-setup.md` for detailed configuration.

## Example Invocations

```
"Tackle an issue in milestone 'Phase 1'"
→ Finds highest priority issue in Phase 1 that's in Todo or Dev Ready

"Work on issue #42"
→ Directly picks up issue #42 regardless of current status

"Complete all Dev Ready issues"
→ Batch processes all implementation-ready issues

"Report on Phase 1 status"
→ Shows breakdown of issues by column/status

"What issues are blocked?"
→ Lists issues with 'blocked' label or stale in In Progress
```
