---
description: Check environment setup for linear-dev-flow - validates LINEAR_API_KEY, team access, workflow states, and Python dependencies
---

# Linear Dev Flow Doctor

Run diagnostic checks to verify your environment is ready for linear-dev-flow.

## Instructions

Run the following checks and report results:

```bash
echo "=== Linear Dev Flow Doctor ==="
echo ""

ERRORS=0

# 1. Check LINEAR_API_KEY
echo "1. Linear API Key..."
if [ -n "$LINEAR_API_KEY" ]; then
    MASKED_KEY="${LINEAR_API_KEY:0:8}..."
    echo "   ✓ LINEAR_API_KEY set ($MASKED_KEY)"
else
    echo "   ✗ LINEAR_API_KEY not set"
    echo "   Fix: export LINEAR_API_KEY=lin_api_xxxxx"
    echo "   Get from: Linear Settings → API → Personal API Keys"
    ERRORS=$((ERRORS + 1))
fi

# 2. Test API connection
echo "2. Linear API Connection..."
if [ -n "$LINEAR_API_KEY" ]; then
    RESPONSE=$(curl -s -X POST https://api.linear.app/graphql \
        -H "Content-Type: application/json" \
        -H "Authorization: $LINEAR_API_KEY" \
        -d '{"query": "{ viewer { id name email } }"}' 2>/dev/null)

    if echo "$RESPONSE" | grep -q '"name"'; then
        USER_NAME=$(echo "$RESPONSE" | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
        USER_EMAIL=$(echo "$RESPONSE" | grep -o '"email":"[^"]*"' | head -1 | cut -d'"' -f4)
        echo "   ✓ Connected as $USER_NAME ($USER_EMAIL)"
    else
        echo "   ✗ API connection failed"
        echo "   Error: $RESPONSE"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "   ✗ Skipped (no API key)"
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
        echo "   ✓ Found $TEAM_COUNT team(s): $TEAM_KEYS"
    else
        echo "   ✗ Could not fetch teams"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "   ✗ Skipped (no API key)"
fi

# 4. Check Python/uv
echo "4. Python Environment..."
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

# 5. Check git
echo "5. Git..."
if command -v git &> /dev/null; then
    echo "   ✓ $(git --version)"
    if git worktree list &> /dev/null 2>&1; then
        echo "   ✓ Git worktree support available"
    else
        echo "   ⚠ Git worktree may not be available"
    fi
else
    echo "   ✗ Git not found"
    ERRORS=$((ERRORS + 1))
fi

# 6. Check .worktreeinclude
echo "6. Worktree Configuration..."
if [ -f ".worktreeinclude" ]; then
    echo "   ✓ .worktreeinclude found"
else
    echo "   ⚠ .worktreeinclude not found (optional)"
    echo "   Note: Create this file to copy secrets to worktrees"
fi

# 7. Check curl
echo "7. HTTP Client..."
if command -v curl &> /dev/null; then
    echo "   ✓ curl available"
else
    echo "   ✗ curl not found"
    echo "   Fix: Install curl for your system"
    ERRORS=$((ERRORS + 1))
fi

# 8. Check LINEAR_TEAM_KEY
echo "8. Team Configuration..."
if [ -n "$LINEAR_TEAM_KEY" ]; then
    echo "   ✓ LINEAR_TEAM_KEY set: $LINEAR_TEAM_KEY"
else
    echo "   ⚠ LINEAR_TEAM_KEY not set (will use first team)"
    echo "   Note: Set LINEAR_TEAM_KEY to specify a team"
fi

echo ""
echo "=== Doctor Complete ==="

if [ $ERRORS -eq 0 ]; then
    echo "All critical checks passed! Ready to use linear-dev-flow"
else
    echo "$ERRORS critical issue(s) found. Please fix before proceeding."
fi
```

After running the checks, summarize:
- How many checks passed vs failed
- Any critical issues that need fixing (especially LINEAR_API_KEY)
- Recommendations for optional improvements
