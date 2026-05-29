---
name: stealth-browser
description: Use when standard agent-browser gets blocked by CAPTCHAs or bot detection on sites like Google, Cloudflare-protected sites, or any site with anti-automation measures. Launches real Google Chrome binary with the user's actual profile for maximum stealth.
---

# Stealth Browser Automation

Launches the real Google Chrome binary with the user's actual browser profile — real cookies, real extensions, real browsing history, real trust signals. agent-browser manages the entire lifecycle.

## Default Usage

```bash
agent-browser \
  --executable-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --profile Default \
  --headed \
  open <url>
```

This:
- Launches **real Chrome** (not bundled Chromium) — genuine browser fingerprint
- Auto-copies your `Default` profile to a temp dir (original untouched)
- Runs **headed** (visible) — headless is more detectable
- agent-browser owns the process — cleanup is just `agent-browser close`

After opening, use standard `agent-browser` commands (snapshot, click, fill, etc.).

## Environment Setup (Recommended)

Set once in `~/.zshrc` so stealth is the default:

```bash
export AGENT_BROWSER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
export AGENT_BROWSER_HEADED=1
```

Then stealth becomes:

```bash
agent-browser --profile Default open <url>
```

## When to Use

| Scenario | Stealth | Regular agent-browser |
|----------|---------|----------------------|
| Google Search | Yes | No (CAPTCHA) |
| Cloudflare-protected sites | Yes | Maybe (often blocked) |
| Sites with bot detection | Yes | No |
| Logged-in sessions needed | Yes (real cookies) | Only with auth vault/state |
| Simple internal tools | No | Yes (faster) |
| CI/CD pipelines | No | Yes (no profile needed) |

## Using Other Chrome Profiles

```bash
agent-browser profiles   # List available profiles
```

Use a specific one:

```bash
agent-browser --profile "Profile 2" --headed \
  --executable-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  open <url>
```

## Named Tab Sessions (Same-Account Multi-Site)

For multiple sites sharing authentication (e.g., Microsoft SSO across Outlook, Teams, DevOps), use named sessions on one Chrome instance. Cookies are shared across tabs.

```bash
# First site creates the Chrome instance
agent-browser --profile Default --session outlook \
  --executable-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headed open "https://outlook.office.com"

# Additional sites open in new tabs on the same instance
agent-browser --session teams tab new
agent-browser --session teams open "https://teams.microsoft.com"

agent-browser --session devops tab new
agent-browser --session devops open "https://dev.azure.com"

# Switch by name — each remembers its tab
agent-browser --session outlook snapshot -i
agent-browser --session teams get url

# List all
agent-browser session list
```

**Tab isolation**: navigating in one session does NOT affect others.
**Shared cookies**: SSO login in one tab authenticates all tabs.

| Situation | Named tab sessions | Separate profiles |
|-----------|-------------------|-------------------|
| Multiple sites, same auth (Microsoft 365, Google Workspace) | Yes | No |
| Different accounts/identities | No | Yes |
| Complete cookie isolation needed | No | Yes |

## Persistent Profile (Cross-Session Continuity)

When a site needs state to persist across separate runs (not just a temp copy):

```bash
agent-browser \
  --executable-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --profile ~/.chrome-stealth-persistent \
  --headed \
  open <url>
```

First run creates the profile dir. Subsequent runs reuse it. Login once, stay logged in.

## Multi-Account Isolation

Different identities need different Chrome profiles:

```bash
# Work account (Profile 2)
agent-browser --profile "Profile 2" --headed --session work \
  --executable-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  open "https://outlook.office.com"

# Personal account (Default)
agent-browser --profile Default --headed --session personal \
  --executable-path "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  open "https://mail.google.com"
```

## Cleanup

```bash
agent-browser close          # Close current session
agent-browser close --all    # Close all sessions
```

agent-browser handles Chrome process cleanup automatically (process groups since v0.24.1).

---

## Edge Case: Manual CDP Attach

Only needed when connecting to Chrome that's **already running** — e.g., you solved a 2FA challenge manually, or need to hand off a pre-existing session to the agent.

### Auto-discover (preferred)

```bash
agent-browser --auto-connect snapshot -i
```

Discovers running Chrome via `DevToolsActivePort` and common debugging ports.

### Explicit CDP port

```bash
# If Chrome is already running with --remote-debugging-port=9222:
agent-browser --cdp 9222 snapshot -i
```

### Launch Chrome manually for CDP (rare)

Only when you need full manual control over the Chrome instance:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome" \
  --profile-directory="Default" &
sleep 3

agent-browser connect 9222
# ... use agent-browser commands ...
agent-browser close
pkill -f "remote-debugging-port=9222"
```

---

## Troubleshooting

### Still getting CAPTCHAs
- Some sites detect CDP regardless — a known limitation
- Add delays between actions to appear more human-like
- Verify `--headed` is set (headless is more detectable)
- If profile cookies are stale, close Chrome and re-run (fresh temp copy)

### Profile locked error
- `--profile Default` auto-copies to temp, so this shouldn't happen
- If using a persistent profile path, only one Chrome process can use it at a time

### Sessions not cleaned up
- `agent-browser close --all` kills all managed sessions
- `agent-browser session list` to check for orphans
- Stale daemons auto-restart on agent-browser version change (v0.24.1+)
