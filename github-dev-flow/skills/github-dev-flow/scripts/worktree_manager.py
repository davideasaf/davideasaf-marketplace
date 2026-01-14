#!/usr/bin/env python3
"""
Git worktree manager for GitHub issues.

Creates isolated worktrees for issue development using the shared git-worktree skill
for actual worktree creation and .worktreeinclude file copying.

Usage:
    # Create worktree for issue
    worktree_manager.py create 42

    # List active worktrees
    worktree_manager.py list

    # Remove worktree
    worktree_manager.py remove 42

Environment:
    Requires git, gh CLI, and the git-worktree skill installed at ~/.claude/skills/git-worktree/

Dependencies:
    This script requires the git-worktree skill to be installed.
    Install it from: https://github.com/davideasaf-marketplace (or copy to ~/.claude/skills/git-worktree/)
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


# Path to shared git-worktree skill
GIT_WORKTREE_SKILL = Path.home() / ".claude" / "skills" / "git-worktree" / "scripts" / "worktree_manager.py"


def run_cmd(cmd: list[str], capture: bool = True, check: bool = True, cwd: Optional[Path] = None) -> str:
    """Run a shell command."""
    result = subprocess.run(cmd, capture_output=capture, text=True, cwd=cwd)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result.stdout.strip() if capture else ""


def run_git(*args: str, cwd: Optional[Path] = None) -> str:
    """Run git command."""
    return run_cmd(["git"] + list(args), cwd=cwd)


def run_gh(*args: str) -> str:
    """Run gh command."""
    return run_cmd(["gh"] + list(args))


def get_repo_root() -> Path:
    """Get git repository root."""
    return Path(run_git("rev-parse", "--show-toplevel"))


def get_repo_name() -> str:
    """Get repository name."""
    return get_repo_root().name


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to URL-friendly slug."""
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug[:max_length]


def get_issue_title(number: int) -> str:
    """Get issue title from GitHub."""
    result = run_gh("issue", "view", str(number), "--json", "title", "-q", ".title")
    return result


def branch_name_for_issue(number: int) -> str:
    """Generate branch name for issue."""
    title = get_issue_title(number)
    slug = slugify(title)
    return f"issue/{number}-{slug}"


def check_git_worktree_skill() -> bool:
    """Check if git-worktree skill is installed."""
    if not GIT_WORKTREE_SKILL.exists():
        print(f"ERROR: git-worktree skill not found at {GIT_WORKTREE_SKILL}")
        print("Please install the git-worktree skill:")
        print("  1. Clone from davideasaf-marketplace, or")
        print("  2. Copy to ~/.claude/skills/git-worktree/")
        return False
    return True


def create_worktree(number: int, path: Optional[str] = None) -> tuple[str, Path]:
    """Create a worktree for an issue."""
    if not check_git_worktree_skill():
        sys.exit(1)

    # Generate branch name from issue
    branch = branch_name_for_issue(number)
    print(f"Creating worktree for issue #{number}")
    print(f"Branch: {branch}")

    # Calculate worktree path if not provided
    repo_root = get_repo_root()
    repo_name = get_repo_name()
    if not path:
        worktree_path = repo_root.parent / f"{repo_name}-{branch.replace('/', '-')}"
    else:
        worktree_path = Path(path).resolve()

    # Delegate to shared git-worktree skill
    cmd = ["uv", "run", "python", str(GIT_WORKTREE_SKILL), "create", branch]
    if path:
        cmd.extend(["--path", path])

    subprocess.run(cmd, check=True)

    return branch, worktree_path


def list_worktrees() -> None:
    """List all worktrees using shared skill."""
    if not check_git_worktree_skill():
        sys.exit(1)

    subprocess.run(["uv", "run", "python", str(GIT_WORKTREE_SKILL), "list"], check=True)


def remove_worktree(number: int) -> None:
    """Remove worktree for an issue."""
    if not check_git_worktree_skill():
        sys.exit(1)

    # Generate branch name from issue
    branch = branch_name_for_issue(number)
    print(f"Removing worktree for issue #{number}")
    print(f"Branch: {branch}")

    # Delegate to shared git-worktree skill
    subprocess.run(["uv", "run", "python", str(GIT_WORKTREE_SKILL), "remove", branch], check=True)


def main():
    parser = argparse.ArgumentParser(description="Git worktree manager for GitHub issues")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    create_p = subparsers.add_parser("create", help="Create worktree for issue")
    create_p.add_argument("number", type=int, help="Issue number")
    create_p.add_argument("--path", help="Custom worktree path")

    # list
    subparsers.add_parser("list", help="List active worktrees")

    # remove
    remove_p = subparsers.add_parser("remove", help="Remove worktree")
    remove_p.add_argument("number", type=int, help="Issue number")

    args = parser.parse_args()

    if args.command == "create":
        branch, path = create_worktree(args.number, getattr(args, 'path', None))
        print(f"\nTo start working:")
        print(f"  cd {path}")

    elif args.command == "list":
        list_worktrees()

    elif args.command == "remove":
        remove_worktree(args.number)


if __name__ == "__main__":
    main()
