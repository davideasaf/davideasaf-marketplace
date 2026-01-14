#!/bin/bash
# Linear Dev Flow Doctor - Environment diagnostics
# Run this script to verify your setup is ready for linear-dev-flow

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "   ${GREEN}✓${NC} $1"; }
fail() { echo -e "   ${RED}✗${NC} $1"; }
warn() { echo -e "   ${YELLOW}⚠${NC} $1"; }

echo "=== Linear Dev Flow Doctor ==="
echo ""

ERRORS=0

# Get the script directory to find Python scripts
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$(cd "$SCRIPT_DIR/../../skills/linear-dev-flow/scripts" && pwd)"

# 1. Check LINEAR_API_KEY
echo "1. Linear API Key..."
if [ -n "$LINEAR_API_KEY" ]; then
    # Mask the key for display
    MASKED_KEY="${LINEAR_API_KEY:0:8}..."
    pass "LINEAR_API_KEY set ($MASKED_KEY)"
else
    fail "LINEAR_API_KEY not set"
    echo "   Fix: export LINEAR_API_KEY=lin_api_xxxxx"
    echo "   Get from: Linear Settings → API → Personal API Keys"
    ERRORS=$((ERRORS + 1))
fi

# 2. Test API connection
echo "2. Linear API Connection..."
if [ -n "$LINEAR_API_KEY" ]; then
    # Test with a simple GraphQL query
    RESPONSE=$(curl -s -X POST https://api.linear.app/graphql \
        -H "Content-Type: application/json" \
        -H "Authorization: $LINEAR_API_KEY" \
        -d '{"query": "{ viewer { id name email } }"}' 2>/dev/null)

    if echo "$RESPONSE" | grep -q '"name"'; then
        USER_NAME=$(echo "$RESPONSE" | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
        USER_EMAIL=$(echo "$RESPONSE" | grep -o '"email":"[^"]*"' | head -1 | cut -d'"' -f4)
        pass "Connected as $USER_NAME ($USER_EMAIL)"
    else
        fail "API connection failed"
        echo "   Error: $RESPONSE"
        ERRORS=$((ERRORS + 1))
    fi
else
    fail "Skipped (no API key)"
    ERRORS=$((ERRORS + 1))
fi

# 3. Check team access
echo "3. Linear Team Access..."
if [ -n "$LINEAR_API_KEY" ]; then
    TEAMS_RESPONSE=$(curl -s -X POST https://api.linear.app/graphql \
        -H "Content-Type: application/json" \
        -H "Authorization: $LINEAR_API_KEY" \
        -d '{"query": "{ teams { nodes { id key name } } }"}' 2>/dev/null)

    if echo "$TEAMS_RESPONSE" | grep -q '"nodes"'; then
        TEAM_COUNT=$(echo "$TEAMS_RESPONSE" | grep -o '"key"' | wc -l | tr -d ' ')
        TEAM_KEYS=$(echo "$TEAMS_RESPONSE" | grep -o '"key":"[^"]*"' | cut -d'"' -f4 | tr '\n' ', ' | sed 's/,$//')
        pass "Found $TEAM_COUNT team(s): $TEAM_KEYS"

        # Check for specific team if LINEAR_TEAM_KEY is set
        if [ -n "$LINEAR_TEAM_KEY" ]; then
            if echo "$TEAMS_RESPONSE" | grep -qi "\"key\":\"$LINEAR_TEAM_KEY\""; then
                pass "Team $LINEAR_TEAM_KEY accessible"
            else
                warn "Team $LINEAR_TEAM_KEY not found in your teams"
            fi
        fi
    else
        fail "Could not fetch teams"
        ERRORS=$((ERRORS + 1))
    fi
else
    fail "Skipped (no API key)"
fi

# 4. Check workflow states
echo "4. Workflow States..."
REQUIRED_STATES=("Backlog" "Todo" "Dev Ready" "In Progress" "In Review" "Done")

if [ -n "$LINEAR_API_KEY" ]; then
    # Get first team's workflow states
    STATES_RESPONSE=$(curl -s -X POST https://api.linear.app/graphql \
        -H "Content-Type: application/json" \
        -H "Authorization: $LINEAR_API_KEY" \
        -d '{"query": "{ teams(first: 1) { nodes { id } } }"}' 2>/dev/null)

    TEAM_ID=$(echo "$STATES_RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

    if [ -n "$TEAM_ID" ]; then
        WORKFLOW_RESPONSE=$(curl -s -X POST https://api.linear.app/graphql \
            -H "Content-Type: application/json" \
            -H "Authorization: $LINEAR_API_KEY" \
            -d "{\"query\": \"{ workflowStates(filter: { team: { id: { eq: \\\"$TEAM_ID\\\" } } }) { nodes { name type } } }\"}" 2>/dev/null)

        FOUND_STATES=$(echo "$WORKFLOW_RESPONSE" | grep -o '"name":"[^"]*"' | cut -d'"' -f4)
        MISSING_STATES=()

        for state in "${REQUIRED_STATES[@]}"; do
            # Case-insensitive search
            if ! echo "$FOUND_STATES" | grep -qi "^$state$"; then
                # Try partial match for "Done" vs "Completed" etc.
                if [ "$state" = "Done" ]; then
                    if echo "$FOUND_STATES" | grep -qi "^Done$\|^Completed$\|^Complete$"; then
                        continue
                    fi
                fi
                MISSING_STATES+=("$state")
            fi
        done

        if [ ${#MISSING_STATES[@]} -eq 0 ]; then
            pass "All required workflow states found"
        else
            warn "Missing states: ${MISSING_STATES[*]}"
            echo "   Fix: Configure these states in Linear team settings"
            echo "   Required: Backlog, Todo, Dev Ready, In Progress, In Review, Done"
        fi
    else
        warn "Could not determine team ID"
    fi
else
    fail "Skipped (no API key)"
fi

# 5. Check Python/uv
echo "5. Python Environment..."
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

# 6. Check git
echo "6. Git..."
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version)
    pass "$GIT_VERSION"

    # Check worktree support
    if git worktree list &> /dev/null; then
        pass "Git worktree support available"
    else
        warn "Git worktree support not available (upgrade git)"
    fi
else
    fail "Git not found"
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

# 8. Check curl (needed for API calls)
echo "8. HTTP Client..."
if command -v curl &> /dev/null; then
    pass "curl available"
else
    fail "curl not found"
    echo "   Fix: Install curl for your system"
    ERRORS=$((ERRORS + 1))
fi

# 9. Check LINEAR_TEAM_KEY (optional)
echo "9. Team Configuration..."
if [ -n "$LINEAR_TEAM_KEY" ]; then
    pass "LINEAR_TEAM_KEY set: $LINEAR_TEAM_KEY"
else
    warn "LINEAR_TEAM_KEY not set (will use first team)"
    echo "   Note: Set LINEAR_TEAM_KEY to specify a team"
fi

echo ""
echo "=== Doctor Complete ==="

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}All critical checks passed! Ready to use linear-dev-flow${NC}"
    exit 0
else
    echo -e "${RED}$ERRORS critical issue(s) found. Please fix before proceeding.${NC}"
    exit 1
fi
