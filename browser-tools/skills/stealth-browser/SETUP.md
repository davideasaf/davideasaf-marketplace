# Setup (`/stealth-browser:setup`)

## Quick Setup

Set environment variables in `~/.zshrc` so stealth is the default when using `--profile`:

```bash
export AGENT_BROWSER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
export AGENT_BROWSER_HEADED=1
```

Then: `source ~/.zshrc`

## Verify

```bash
# Check env vars
echo "Executable: $AGENT_BROWSER_EXECUTABLE_PATH"
echo "Headed: $AGENT_BROWSER_HEADED"

# List available Chrome profiles
agent-browser profiles

# Test stealth launch
agent-browser --profile Default open "https://www.google.com"
agent-browser screenshot && agent-browser close
```

## Available Profiles

```bash
agent-browser profiles
```

Common profiles: `Default` (primary), `Profile 2`, `Profile 3`, etc. These map to Chrome's profile picker names.

## Persistent Profile Setup (Optional)

For sites needing cross-session continuity, create a dedicated persistent profile:

```bash
# First run creates it and copies your Default profile's state
agent-browser --profile ~/.chrome-stealth-persistent open "https://example.com"
```

Subsequent runs reuse this directory with all cookies/state intact.

## Limitations

- **macOS only** — Chrome path is `/Applications/Google Chrome.app/...`
- **Profile is a temp copy** — changes during automation don't sync back to real Chrome (this is a feature, not a bug)
- **One instance per profile path** — use named sessions or different profiles for parallel work
