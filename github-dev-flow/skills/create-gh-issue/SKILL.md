---
name: create-gh-issue
description: Creates well-documented GitHub issues with evidence collection. For bugs, validates and reproduces using Claude Chrome, captures screenshots/GIFs as evidence. For features, assesses fit (UX consistency, technical feasibility, scope, roadmap alignment) and enhances with suggestions. Auto-detects repository, applies appropriate labels (bug/enhancement + needs-triage), and adds to project board "Todo" column. This skill should be used when the user reports a bug, describes unexpected behavior, requests a new feature, or asks to create/log/file a GitHub issue.
---

# Create GitHub Issue

A skill for creating well-documented GitHub issues with evidence collection and validation.

## Prerequisites

- **Claude Chrome**: Enable with `--chrome` flag or `/chrome` command for bug reproduction
- **gh CLI**: Authenticated with repo access (`gh auth status`)
- **Project scope**: For project board integration (`gh auth refresh -s project`)

## Workflow Overview

```
User Report → Classify (Bug/Feature) → Investigate → Document → Create Issue → Add to Board
```

## Bug Report Workflow

When a user reports a bug or unexpected behavior:

### 1. Understand the Issue

Gather information from the user:
- What were they trying to do?
- What happened instead?
- Can they provide a URL or steps?

### 2. Reproduce with Claude Chrome

Use Claude Chrome to validate the bug:

```
Navigate to [URL], then [steps]. Record a GIF showing what happens.
```

Key commands:
- "Go to [URL] and record a GIF showing [the issue]"
- "Take a screenshot of [the error/state]"
- "Navigate to [page], click [element], observe [behavior]"

If Claude Chrome is unavailable, document the reported steps without reproduction and note `❌ Could not reproduce (Claude Chrome unavailable)`.

### 3. Capture Evidence

During reproduction, capture:
- **Screenshot**: Key error states, visual bugs
- **GIF**: Multi-step issues, animations, timing bugs
- **Console errors**: If applicable ("Check the console for errors")

Save evidence files locally. Claude Chrome saves to the current directory or temp.

### 4. Upload Evidence

Upload captured media to the repository:

```bash
uv run python scripts/upload_media.py screenshot.png
```

Returns markdown image syntax for embedding in the issue.

### 5. Create the Issue

Use the bug report template from `references/issue-templates.md`:

```bash
uv run python scripts/create_issue.py bug "Issue title" --body-file issue.md
```

The script:
- Adds `bug` and `needs-triage` labels
- Creates the issue
- Moves to project board "Todo" column

## Feature Request Workflow

When a user requests a new feature or enhancement:

### 1. Understand the Request

Gather details:
- What feature do they want?
- Why do they need it? (use case)
- How do they envision it working?

### 2. Assess Fit

Evaluate the feature against four criteria:

| Criteria | Questions to Consider |
|----------|----------------------|
| **UX Consistency** | Does it match existing patterns? Will users expect this behavior? |
| **Technical Feasibility** | How complex to implement? Any blockers? Dependencies? |
| **Scope** | Is it well-contained? Risk of creep? Can it be broken down? |
| **Roadmap Alignment** | Does it fit the project direction? Priority vs other work? |

Rate each: 🟢 Good / 🟡 Moderate / 🔴 Concern

### 3. Enhance with Suggestions

Based on the assessment, provide:
- Improvements to the original request
- Alternative approaches if concerns exist
- Ways to reduce scope or complexity
- Related features that could be bundled

### 4. Create the Issue

Use the feature request template from `references/issue-templates.md`:

```bash
uv run python scripts/create_issue.py feature "Feature title" --body-file issue.md
```

The script:
- Adds `enhancement` and `needs-triage` labels
- Creates the issue
- Moves to project board "Todo" column

## Scripts Reference

### detect_repo.py

Auto-detect GitHub repository from git remote:

```bash
uv run python scripts/detect_repo.py
# Output: owner/repo
```

### upload_media.py

Upload images/GIFs to repository for embedding:

```bash
# Returns markdown image syntax
uv run python scripts/upload_media.py path/to/image.png

# URL only
uv run python scripts/upload_media.py image.gif --url-only
```

Files are stored in `.github/issue-assets/` with content-based naming.

### create_issue.py

Create issue with labels and project board:

```bash
# Bug issue
uv run python scripts/create_issue.py bug "Title" --body "Description..."

# Feature issue from file
uv run python scripts/create_issue.py feature "Title" --body-file issue.md

# Additional labels
uv run python scripts/create_issue.py bug "Title" --body "..." --label priority:high

# Skip project board
uv run python scripts/create_issue.py bug "Title" --body "..." --no-project
```

## Project Board Integration

Uses `github-dev-flow` skill's `project_board.py` to add issues to the board:

```bash
uv run python ../github-dev-flow/scripts/project_board.py move <issue_number> --to todo
```

Requires: `gh auth refresh -s project`

## Edge Cases

### No Git Repository

If not in a git repository:
```
Error: Could not detect GitHub repository.
Make sure you're in a git repository with a GitHub remote.
```

### Claude Chrome Unavailable

If Claude Chrome is not enabled:
1. Document reported steps in issue body
2. Mark reproduction status: `❌ Could not reproduce (Claude Chrome unavailable)`
3. Suggest user enable Claude Chrome: `claude --chrome` or `/chrome`

### No Project Board

If no project board is configured:
1. Issue is still created with labels
2. Warning displayed: "Could not add to project board"
3. User can manually add to board

### Private Repository

Works the same - `gh` CLI handles authentication.

## Example Invocations

```
"The login button doesn't work on mobile"
→ Bug workflow: reproduce on mobile viewport, capture GIF, create bug issue

"Add a dark mode toggle to settings"
→ Feature workflow: assess fit, suggest implementation, create enhancement issue

"I'm seeing a console error when I click submit"
→ Bug workflow: reproduce, capture screenshot + console, create bug issue

"Can we add export to CSV?"
→ Feature workflow: assess scope/feasibility, create enhancement issue
```

## Templates

See `references/issue-templates.md` for:
- Full Bug Report template
- Full Feature Request template
- Quick Bug template (minimal)
- Quick Feature template (minimal)
