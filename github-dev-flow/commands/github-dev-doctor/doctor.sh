#!/bin/bash
# GitHub Dev Flow Doctor - Environment diagnostics
# Run this script to verify your setup is ready for github-dev-flow

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "   ${GREEN}✓${NC} $1"; }
fail() { echo -e "   ${RED}✗${NC} $1"; }
warn() { echo -e "   ${YELLOW}⚠${NC} $1"; }

echo "=== GitHub Dev Flow Doctor ==="
echo ""

ERRORS=0

# 1. Check gh CLI
echo "1. GitHub CLI..."
if command -v gh &> /dev/null; then
    pass "$(gh --version | head -1)"
else
    fail "gh CLI not found"
    echo "   Fix: brew install gh (macOS) or visit https://cli.github.com/"
    ERRORS=$((ERRORS + 1))
fi

# 2. Check gh auth
echo "2. GitHub Authentication..."
if gh auth status &> /dev/null; then
    USER=$(gh auth status 2>&1 | grep "Logged in" | head -1 | sed 's/.*as //' | cut -d' ' -f1)
    pass "Authenticated as $USER"
else
    fail "Not authenticated"
    echo "   Fix: gh auth login"
    ERRORS=$((ERRORS + 1))
fi

# 3. Check project scope
echo "3. Project Scope..."
if gh auth status 2>&1 | grep -qi "project"; then
    pass "Project scope enabled"
else
    fail "Project scope missing"
    echo "   Fix: gh auth refresh -s project"
    ERRORS=$((ERRORS + 1))
fi

# 4. Check repo access
echo "4. Repository Access..."
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
if [ -n "$REPO" ]; then
    pass "Repository: $REPO"
else
    fail "Not in a GitHub repository"
    echo "   Fix: Navigate to a cloned GitHub repository"
    ERRORS=$((ERRORS + 1))
fi

# 5. Check for project board
echo "5. GitHub Project Board..."
if [ -n "$REPO" ]; then
    OWNER=$(echo "$REPO" | cut -d'/' -f1)
    PROJECTS=$(gh project list --owner "$OWNER" --format json 2>/dev/null | jq 'length' 2>/dev/null || echo "0")
    if [ "$PROJECTS" -gt 0 ]; then
        pass "Found $PROJECTS project(s) for $OWNER"
    else
        warn "No projects found for $OWNER"
        echo "   Note: Create a project at https://github.com/$OWNER"
    fi
else
    warn "Skipped (no repository)"
fi

# 6. Check Python/uv
echo "6. Python Environment..."
if command -v uv &> /dev/null; then
    pass "$(uv --version)"
else
    fail "uv not found"
    echo "   Fix: curl -LsSf https://astral.sh/uv/install.sh | sh"
    ERRORS=$((ERRORS + 1))
fi

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>/dev/null)
    pass "$PYTHON_VERSION"
else
    fail "Python 3 not found"
    ERRORS=$((ERRORS + 1))
fi

# 7. Check .worktreeinclude
echo "7. Worktree Configuration..."
if [ -f ".worktreeinclude" ]; then
    pass ".worktreeinclude found"
else
    warn ".worktreeinclude not found (optional)"
    echo "   Note: Create this file to copy secrets to worktrees"
fi

# 8. Check jq (needed for some operations)
echo "8. JSON Processing..."
if command -v jq &> /dev/null; then
    pass "jq $(jq --version)"
else
    warn "jq not found (optional but recommended)"
    echo "   Note: Install with: brew install jq"
fi

# 9. Check priority labels
echo "9. Priority Labels..."
if [ -n "$REPO" ]; then
    REQUIRED_LABELS=("P: Critical" "P: HIGH" "P: Medium" "P: low")
    EXISTING_LABELS=$(gh label list -R "$REPO" --json name -q '.[].name' 2>/dev/null || echo "")
    MISSING_LABELS=()

    for label in "${REQUIRED_LABELS[@]}"; do
        if ! echo "$EXISTING_LABELS" | grep -qF "$label"; then
            MISSING_LABELS+=("$label")
        fi
    done

    if [ ${#MISSING_LABELS[@]} -eq 0 ]; then
        pass "All priority labels configured"
    else
        warn "Missing labels: ${MISSING_LABELS[*]}"
        echo "   Fix: Create labels at https://github.com/$REPO/labels"
    fi
else
    warn "Skipped (no repository)"
fi

# 10. Check issue types
echo "10. Issue Types..."
if [ -n "$REPO" ]; then
    REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)
    # GitHub's issue types are a newer feature - check via GraphQL if available
    ISSUE_TYPES=$(gh api graphql -f query='
      query($owner: String!, $name: String!) {
        repository(owner: $owner, name: $name) {
          issueTypes(first: 10) {
            nodes { name }
          }
        }
      }
    ' -f owner="$OWNER" -f name="$REPO_NAME" --jq '.data.repository.issueTypes.nodes[].name' 2>/dev/null || echo "")

    if [ -n "$ISSUE_TYPES" ]; then
        REQUIRED_TYPES=("Bug" "Feature" "Task")
        MISSING_TYPES=()
        for type in "${REQUIRED_TYPES[@]}"; do
            if ! echo "$ISSUE_TYPES" | grep -qF "$type"; then
                MISSING_TYPES+=("$type")
            fi
        done

        if [ ${#MISSING_TYPES[@]} -eq 0 ]; then
            pass "Issue types configured: Bug, Feature, Task"
        else
            warn "Missing issue types: ${MISSING_TYPES[*]}"
            echo "   Fix: Enable in repository Settings > Features > Issues > Issue Types"
        fi
    else
        warn "Issue types not available (may require GitHub Team or newer repo)"
    fi
else
    warn "Skipped (no repository)"
fi

echo ""
echo "=== Doctor Complete ==="

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}All critical checks passed! Ready to use github-dev-flow${NC}"
    exit 0
else
    echo -e "${RED}$ERRORS critical issue(s) found. Please fix before proceeding.${NC}"
    exit 1
fi
