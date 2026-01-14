#!/usr/bin/env python3
"""
Git worktree manager for Linear issues.

Creates isolated worktrees for issue development using the shared git-worktree skill
for actual worktree creation and .worktreeinclude file copying.

Usage:
    # Create worktree for Linear issue
    worktree_manager.py create ASA-42
    worktree_manager.py create ASA-42 --title "Fix login bug"

    # List active worktrees
    worktree_manager.py list

    # Remove worktree
    worktree_manager.py remove ASA-42

Environment:
    Requires git CLI, and the git-worktree skill installed at ~/.claude/skills/git-worktree/
    Optionally uses LINEAR_API_KEY to fetch issue title.

Dependencies:
    This script requires the git-worktree skill to be installed.
    Install it from: https://github.com/davideasaf-marketplace (or copy to ~/.claude/skills/git-worktree/)
"""

import argparse
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


def get_issue_title_from_linear(identifier: str) -> Optional[str]:
    """Get issue title from Linear API (if available)."""
    try:
        from linear_api import get_issue
        issue = get_issue(identifier)
        return issue.get('title') if issue else None
    except (ImportError, SystemExit, Exception):
        return None


def branch_name_for_issue(identifier: str, title: Optional[str] = None) -> str:
    """
    Generate branch name for Linear issue.

    Args:
        identifier: Issue identifier like "ASA-42"
        title: Optional issue title for slug generation
    """
    identifier_lower = identifier.lower()

    if title:
        slug = slugify(title)
        return f"issue/{identifier_lower}-{slug}"

    # Try to get title from Linear
    title = get_issue_title_from_linear(identifier)
    if title:
        slug = slugify(title)
        return f"issue/{identifier_lower}-{slug}"

    # Fallback: just use identifier
    return f"issue/{identifier_lower}"


def check_git_worktree_skill() -> bool:
    """Check if git-worktree skill is installed."""
    if not GIT_WORKTREE_SKILL.exists():
        print(f"ERROR: git-worktree skill not found at {GIT_WORKTREE_SKILL}")
        print("Please install the git-worktree skill:")
        print("  1. Clone from davideasaf-marketplace, or")
        print("  2. Copy to ~/.claude/skills/git-worktree/")
        return False
    return True


def create_worktree(identifier: str, title: Optional[str] = None, path: Optional[str] = None) -> tuple[str, Path]:
    """Create a worktree for a Linear issue."""
    if not check_git_worktree_skill():
        sys.exit(1)

    # Generate branch name from issue
    branch = branch_name_for_issue(identifier, title)
    print(f"Creating worktree for issue {identifier}")
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


def remove_worktree(identifier: str) -> None:
    """Remove worktree for a Linear issue."""
    if not check_git_worktree_skill():
        sys.exit(1)

    # Generate branch name from issue (without title, will match by identifier)
    branch = branch_name_for_issue(identifier)
    print(f"Removing worktree for issue {identifier}")
    print(f"Branch pattern: {branch}")

    # Delegate to shared git-worktree skill
    subprocess.run(["uv", "run", "python", str(GIT_WORKTREE_SKILL), "remove", branch], check=True)


def main():
    parser = argparse.ArgumentParser(description="Git worktree manager for Linear issues")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    create_p = subparsers.add_parser("create", help="Create worktree for issue")
    create_p.add_argument("identifier", help="Issue identifier (e.g., ASA-42)")
    create_p.add_argument("--title", help="Issue title for branch naming")
    create_p.add_argument("--path", help="Custom worktree path")

    # list
    subparsers.add_parser("list", help="List active worktrees")

    # remove
    remove_p = subparsers.add_parser("remove", help="Remove worktree")
    remove_p.add_argument("identifier", help="Issue identifier (e.g., ASA-42)")

    args = parser.parse_args()

    if args.command == "create":
        branch, path = create_worktree(args.identifier, getattr(args, 'title', None), getattr(args, 'path', None))
        print(f"\nTo start working:")
        print(f"  cd {path}")

    elif args.command == "list":
        list_worktrees()

    elif args.command == "remove":
        remove_worktree(args.identifier)


if __name__ == "__main__":
    main()
