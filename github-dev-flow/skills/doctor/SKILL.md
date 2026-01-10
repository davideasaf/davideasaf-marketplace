---
name: doctor
description: Check environment setup for github-dev-flow skill - validates GitHub CLI, authentication, project board configuration, and Python dependencies.
---

# GitHub Dev Flow Doctor

Diagnostic tool to verify your environment is properly configured for the github-dev-flow workflow.

## Usage

Run `/doctor` to check all dependencies and configuration.

## Checks Performed

### 1. GitHub CLI Installation

```bash
gh --version
```

**Expected:** `gh version X.X.X`
**Fix if missing:** `brew install gh` (macOS) or see https://cli.github.com/

### 2. GitHub CLI Authentication

```bash
gh auth status
```

**Expected:** Shows logged-in status with required scopes
**Fix if not logged in:** `gh auth login`

### 3. Project Scope

```bash
gh auth status 2>&1 | grep -i "project"
```

**Expected:** `project` scope listed in scopes
**Fix if missing:** `gh auth refresh -s project`

### 4. Repository Access

```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```

**Expected:** Returns `owner/repo` format
**Fix:** Ensure you're in a git repository with a GitHub remote

### 5. GitHub Project Board

```bash
gh project list --owner <owner> --format json
```

**Expected:** At least one project linked to the repository
**Fix:** Create a project at https://github.com/orgs/<org>/projects or https://github.com/users/<user>/projects

### 6. Project Board Columns

Run `project_board.py columns` to verify required columns exist:

```bash
uv run python scripts/project_board.py columns
```

**Required columns:**
- Todo
- Planning
- Dev Ready
- In Progress
- Review
- Done

**Fix:** Add missing columns in the GitHub Projects UI

### 7. Python/uv Installation

```bash
uv --version
python3 --version
```

**Expected:** `uv X.X.X` and `Python 3.10+`
**Fix if uv missing:** `curl -LsSf https://astral.sh/uv/install.sh | sh`

### 8. .worktreeinclude File (Optional)

```bash
test -f .worktreeinclude && echo "Found" || echo "Missing (optional)"
```

**Expected:** File exists in repo root (optional but recommended)
**Fix:** Create `.worktreeinclude` to specify secrets to copy to worktrees

## Running the Doctor

When invoked, execute these checks in sequence and report results:

```bash
#!/bin/bash
set -e

echo "=== GitHub Dev Flow Doctor ==="
echo ""

# 1. Check gh CLI
echo "1. GitHub CLI..."
if command -v gh &> /dev/null; then
    echo "   ✓ $(gh --version | head -1)"
else
    echo "   ✗ gh CLI not found"
    echo "   Fix: brew install gh (macOS) or visit https://cli.github.com/"
    exit 1
fi

# 2. Check gh auth
echo "2. GitHub Authentication..."
if gh auth status &> /dev/null; then
    echo "   ✓ Authenticated"
else
    echo "   ✗ Not authenticated"
    echo "   Fix: gh auth login"
    exit 1
fi

# 3. Check project scope
echo "3. Project Scope..."
if gh auth status 2>&1 | grep -qi "project"; then
    echo "   ✓ Project scope enabled"
else
    echo "   ✗ Project scope missing"
    echo "   Fix: gh auth refresh -s project"
    exit 1
fi

# 4. Check repo access
echo "4. Repository Access..."
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
if [ -n "$REPO" ]; then
    echo "   ✓ Repository: $REPO"
else
    echo "   ✗ Not in a GitHub repository"
    echo "   Fix: Navigate to a cloned GitHub repository"
    exit 1
fi

# 5. Check for project board
echo "5. GitHub Project Board..."
OWNER=$(echo "$REPO" | cut -d'/' -f1)
PROJECTS=$(gh project list --owner "$OWNER" --format json 2>/dev/null | jq 'length' 2>/dev/null || echo "0")
if [ "$PROJECTS" -gt 0 ]; then
    echo "   ✓ Found $PROJECTS project(s)"
else
    echo "   ⚠ No projects found for $OWNER"
    echo "   Fix: Create a project at https://github.com/$OWNER"
fi

# 6. Check Python/uv
echo "6. Python Environment..."
if command -v uv &> /dev/null; then
    echo "   ✓ $(uv --version)"
else
    echo "   ✗ uv not found"
    echo "   Fix: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>/dev/null || echo "Not found")
echo "   ✓ $PYTHON_VERSION"

# 7. Check .worktreeinclude
echo "7. Worktree Configuration..."
if [ -f ".worktreeinclude" ]; then
    echo "   ✓ .worktreeinclude found"
else
    echo "   ⚠ .worktreeinclude not found (optional)"
    echo "   Note: Create this file to copy secrets to worktrees"
fi

# 8. Check project columns (if project exists)
echo "8. Project Board Columns..."
if [ "$PROJECTS" -gt 0 ] && [ -f "scripts/project_board.py" ]; then
    COLUMNS=$(uv run python scripts/project_board.py columns 2>/dev/null || echo "")
    if [ -n "$COLUMNS" ]; then
        echo "$COLUMNS" | while read -r line; do
            echo "   $line"
        done

        # Check for required columns
        REQUIRED="todo planning dev ready in progress review done"
        for col in $REQUIRED; do
            if echo "$COLUMNS" | grep -qi "$col"; then
                echo "   ✓ $col"
            else
                echo "   ⚠ Missing: $col"
            fi
        done
    else
        echo "   ⚠ Could not check columns"
    fi
else
    echo "   ⚠ Skipped (no project or scripts not found)"
fi

echo ""
echo "=== Doctor Complete ==="
```

## Diagnostic Output Format

Present results in this format:

```
=== GitHub Dev Flow Doctor ===

1. GitHub CLI.............. ✓ gh version 2.40.0
2. GitHub Authentication... ✓ Authenticated as username
3. Project Scope........... ✓ Enabled
4. Repository Access....... ✓ owner/repo
5. GitHub Project Board.... ✓ Found "Project Name"
6. Python Environment...... ✓ uv 0.4.0, Python 3.12.0
7. Worktree Config......... ⚠ .worktreeinclude not found (optional)
8. Project Columns:
   ✓ Todo
   ✓ Planning
   ✓ Dev Ready
   ✓ In Progress
   ✓ Review
   ✓ Done

=== All checks passed! Ready to use github-dev-flow ===
```

## Quick Fixes Reference

| Issue | Command |
|-------|---------|
| gh not installed | `brew install gh` |
| Not authenticated | `gh auth login` |
| Missing project scope | `gh auth refresh -s project` |
| uv not installed | `curl -LsSf https://astral.sh/uv/install.sh | sh` |
| No project board | Create at GitHub UI |
| Missing columns | Add columns in GitHub Projects UI |
