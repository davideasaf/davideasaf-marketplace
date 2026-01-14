---
description: Check environment setup for github-dev-flow - validates GitHub CLI, authentication, project board configuration, and Python dependencies
---

# GitHub Dev Flow Doctor

Run diagnostic checks to verify your environment is ready for github-dev-flow.

## Instructions

Run the following checks and report results:

```bash
echo "=== GitHub Dev Flow Doctor ==="
echo ""

ERRORS=0

# 1. Check gh CLI
echo "1. GitHub CLI..."
if command -v gh &> /dev/null; then
    echo "   ✓ $(gh --version | head -1)"
else
    echo "   ✗ gh CLI not found"
    echo "   Fix: brew install gh (macOS) or visit https://cli.github.com/"
    ERRORS=$((ERRORS + 1))
fi

# 2. Check gh auth
echo "2. GitHub Authentication..."
if gh auth status &> /dev/null; then
    USER=$(gh auth status 2>&1 | grep "Logged in" | head -1 | sed 's/.*as //' | cut -d' ' -f1)
    echo "   ✓ Authenticated as $USER"
else
    echo "   ✗ Not authenticated"
    echo "   Fix: gh auth login"
    ERRORS=$((ERRORS + 1))
fi

# 3. Check project scope
echo "3. Project Scope..."
if gh auth status 2>&1 | grep -qi "project"; then
    echo "   ✓ Project scope enabled"
else
    echo "   ✗ Project scope missing"
    echo "   Fix: gh auth refresh -s project"
    ERRORS=$((ERRORS + 1))
fi

# 4. Check repo access
echo "4. Repository Access..."
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
if [ -n "$REPO" ]; then
    echo "   ✓ Repository: $REPO"
else
    echo "   ✗ Not in a GitHub repository"
    echo "   Fix: Navigate to a cloned GitHub repository"
    ERRORS=$((ERRORS + 1))
fi

# 5. Check for project board
echo "5. GitHub Project Board..."
if [ -n "$REPO" ]; then
    OWNER=$(echo "$REPO" | cut -d'/' -f1)
    PROJECTS=$(gh project list --owner "$OWNER" --format json 2>/dev/null | jq 'length' 2>/dev/null || echo "0")
    if [ "$PROJECTS" -gt 0 ]; then
        echo "   ✓ Found $PROJECTS project(s) for $OWNER"
    else
        echo "   ⚠ No projects found for $OWNER"
        echo "   Note: Create a project at https://github.com/$OWNER"
    fi
else
    echo "   ⚠ Skipped (no repository)"
fi

# 6. Check Python/uv
echo "6. Python Environment..."
if command -v uv &> /dev/null; then
    echo "   ✓ $(uv --version)"
else
    echo "   ✗ uv not found"
    echo "   Fix: curl -LsSf https://astral.sh/uv/install.sh | sh"
    ERRORS=$((ERRORS + 1))
fi

if command -v python3 &> /dev/null; then
    echo "   ✓ $(python3 --version 2>/dev/null)"
else
    echo "   ✗ Python 3 not found"
    ERRORS=$((ERRORS + 1))
fi

# 7. Check .worktreeinclude
echo "7. Worktree Configuration..."
if [ -f ".worktreeinclude" ]; then
    echo "   ✓ .worktreeinclude found"
else
    echo "   ⚠ .worktreeinclude not found (optional)"
    echo "   Note: Create this file to copy secrets to worktrees"
fi

# 8. Check jq
echo "8. JSON Processing..."
if command -v jq &> /dev/null; then
    echo "   ✓ jq $(jq --version)"
else
    echo "   ⚠ jq not found (optional but recommended)"
    echo "   Note: Install with: brew install jq"
fi

echo ""
echo "=== Doctor Complete ==="

if [ $ERRORS -eq 0 ]; then
    echo "All critical checks passed! Ready to use github-dev-flow"
else
    echo "$ERRORS critical issue(s) found. Please fix before proceeding."
fi
```

After running the checks, summarize:
- How many checks passed vs failed
- Any critical issues that need fixing
- Recommendations for optional improvements
