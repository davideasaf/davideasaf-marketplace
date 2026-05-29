---
name: git-worktree
description: Manages git worktrees with .worktreeinclude file copy support. Creates isolated development environments that include gitignored secrets/credentials. Use this skill when creating worktrees for development branches.
---

# Git Worktree Manager

Creates isolated git worktrees with automatic copying of gitignored secrets and credentials specified in `.worktreeinclude`.

## Usage

```bash
# Create worktree for a branch
uv run python ~/.claude/skills/git-worktree/scripts/worktree_manager.py create <branch> [--path PATH]

# List active worktrees
uv run python ~/.claude/skills/git-worktree/scripts/worktree_manager.py list

# Remove a worktree
uv run python ~/.claude/skills/git-worktree/scripts/worktree_manager.py remove <branch-or-path>
```

## .worktreeinclude File

Create a `.worktreeinclude` file in your repository root to specify which gitignored files should be copied to new worktrees:

```
# Files to copy to new git worktrees
# Only files matching BOTH this file AND .gitignore are copied

# Environment variables
.env
.env.*

# App-specific environment files
apps/*/.env.local
apps/*/.env

# Credentials
credentials/
secrets/
```

### Pattern Syntax

- `filename` - Exact file match
- `*.ext` - Glob pattern
- `dir/` - Directory (trailing slash)
- `path/to/file` - Relative path
- Lines starting with `#` are comments

## Integration with Dev-Flow Skills

This skill provides the core worktree functionality used by:
- `github-dev-flow` - Creates worktrees for GitHub issues
- `linear-dev-flow` - Creates worktrees for Linear issues

Those skills handle issue-specific logic (branch naming, API calls) and delegate worktree creation to this skill.

## How It Works

1. Reads patterns from `.worktreeinclude`
2. Gets list of gitignored files via `git ls-files --others --ignored`
3. Creates the worktree with `git worktree add`
4. Copies files that match BOTH `.worktreeinclude` patterns AND are gitignored
