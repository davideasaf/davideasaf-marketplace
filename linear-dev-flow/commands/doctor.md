---
description: Check environment setup for linear-dev-flow - validates Linear authentication (OAuth, client credentials, or API key), team access, workflow states, and Python dependencies
---

# Linear Dev Flow Doctor

Run diagnostic checks to verify your environment is ready for linear-dev-flow.

## Instructions

Run the following checks and report results:

```bash
echo "=== Linear Dev Flow Doctor ==="
echo ""

ERRORS=0

# 1. Check Linear Authentication
echo "1. Linear Authentication..."
AUTH_TOKEN=""
AUTH_METHOD=""

if [ -n "$LINEAR_OAUTH_ACCESS_TOKEN" ]; then
    MASKED_TOKEN="${LINEAR_OAUTH_ACCESS_TOKEN:0:12}..."
    echo "   ✓ LINEAR_OAUTH_ACCESS_TOKEN set ($MASKED_TOKEN)"
    echo "   → Using pre-generated OAuth token"
    AUTH_TOKEN="$LINEAR_OAUTH_ACCESS_TOKEN"
    AUTH_METHOD="oauth_token"
elif [ -n "$LINEAR_OAUTH_CLIENT_ID" ] && [ -n "$LINEAR_OAUTH_CLIENT_SECRET" ]; then
    MASKED_ID="${LINEAR_OAUTH_CLIENT_ID:0:8}..."
    echo "   ✓ LINEAR_OAUTH_CLIENT_ID set ($MASKED_ID)"
    echo "   ✓ LINEAR_OAUTH_CLIENT_SECRET set"
    echo "   → Using Client Credentials flow (will exchange for token)"
    # Exchange client credentials for token
    TOKEN_RESPONSE=$(curl -s -X POST https://api.linear.app/oauth/token \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "grant_type=client_credentials&client_id=$LINEAR_OAUTH_CLIENT_ID&client_secret=$LINEAR_OAUTH_CLIENT_SECRET&scope=read,write,issues:create,comments:create" 2>/dev/null)
    AUTH_TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    if [ -n "$AUTH_TOKEN" ]; then
        echo "   ✓ Token exchange successful"
        AUTH_METHOD="client_credentials"
    else
        echo "   ✗ Token exchange failed"
        echo "   Response: $TOKEN_RESPONSE"
        ERRORS=$((ERRORS + 1))
    fi
elif [ -n "$LINEAR_API_KEY" ]; then
    MASKED_KEY="${LINEAR_API_KEY:0:8}..."
    echo "   ✓ LINEAR_API_KEY set ($MASKED_KEY)"
    echo "   → Using personal API key authentication"
    AUTH_TOKEN="$LINEAR_API_KEY"
    AUTH_METHOD="api_key"
else
    echo "   ✗ No Linear authentication configured"
    echo "   Set one of these:"
    echo "     LINEAR_OAUTH_ACCESS_TOKEN - Pre-generated OAuth token"
    echo "     LINEAR_OAUTH_CLIENT_ID + LINEAR_OAUTH_CLIENT_SECRET - Client Credentials"
    echo "     LINEAR_API_KEY - Personal API key (lin_api_*)"
    echo "   Get from: Linear Settings → API"
    ERRORS=$((ERRORS + 1))
fi

# 2. Test API connection
echo "2. Linear API Connection..."
if [ -n "$AUTH_TOKEN" ]; then
    RESPONSE=$(curl -s -X POST https://api.linear.app/graphql \
        -H "Content-Type: application/json" \
        -H "Authorization: $AUTH_TOKEN" \
        -d '{"query": "{ viewer { id name email } }"}' 2>/dev/null)

    if echo "$RESPONSE" | grep -q '"name"'; then
        USER_NAME=$(echo "$RESPONSE" | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
        USER_EMAIL=$(echo "$RESPONSE" | grep -o '"email":"[^"]*"' | head -1 | cut -d'"' -f4)
        echo "   ✓ Connected as $USER_NAME ($USER_EMAIL)"
        if [ "$AUTH_METHOD" = "oauth_token" ] || [ "$AUTH_METHOD" = "client_credentials" ]; then
            echo "   → Authenticated via OAuth application"
        fi
    else
        echo "   ✗ API connection failed"
        echo "   Error: $RESPONSE"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "   ✗ Skipped (no authentication configured)"
    ERRORS=$((ERRORS + 1))
fi

# 3. Check team access
echo "3. Linear Team Access..."
if [ -n "$AUTH_TOKEN" ]; then
    TEAMS_RESPONSE=$(curl -s -X POST https://api.linear.app/graphql \
        -H "Content-Type: application/json" \
        -H "Authorization: $AUTH_TOKEN" \
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
    echo "   ✗ Skipped (no authentication configured)"
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
