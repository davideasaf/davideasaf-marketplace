#!/usr/bin/env python3
"""
Git worktree manager with .worktreeinclude support.

Creates isolated worktrees for development, copying gitignored files
that are specified in .worktreeinclude.

Usage:
    # Create worktree for a branch
    worktree_manager.py create feature-branch
    worktree_manager.py create feature-branch --path /custom/path

    # List active worktrees
    worktree_manager.py list

    # Remove worktree
    worktree_manager.py remove feature-branch
    worktree_manager.py remove /path/to/worktree

Environment:
    Requires git CLI.
"""

import argparse
import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


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


def get_default_branch() -> str:
    """Get default branch (main or master)."""
    try:
        result = run_git("symbolic-ref", "refs/remotes/origin/HEAD")
        return result.split("/")[-1]
    except subprocess.CalledProcessError:
        # Fallback: check if main exists
        try:
            run_git("rev-parse", "--verify", "main")
            return "main"
        except subprocess.CalledProcessError:
            return "master"


def read_worktreeinclude(repo_root: Path) -> list[str]:
    """Read .worktreeinclude patterns."""
    include_file = repo_root / ".worktreeinclude"
    if not include_file.exists():
        return []

    patterns = []
    for line in include_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def get_gitignored_files(repo_root: Path) -> set[Path]:
    """Get set of gitignored file paths."""
    try:
        result = run_cmd(
            ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "-z"],
            check=False,
            cwd=repo_root
        )
        if not result:
            return set()

        files = set()
        for path_str in result.split('\0'):
            if path_str:
                files.add(repo_root / path_str)
        return files
    except Exception:
        return set()


def matches_pattern(path: Path, pattern: str, repo_root: Path) -> bool:
    """Check if path matches a .worktreeinclude pattern."""
    rel_path = str(path.relative_to(repo_root))

    # Handle directory patterns (ending with /)
    if pattern.endswith('/'):
        dir_pattern = pattern.rstrip('/')
        return rel_path.startswith(dir_pattern + '/') or rel_path == dir_pattern

    # Handle glob patterns
    if '*' in pattern:
        return fnmatch.fnmatch(rel_path, pattern)

    # Exact match or directory match
    return rel_path == pattern or rel_path.startswith(pattern + '/')


def copy_worktree_files(repo_root: Path, worktree_path: Path) -> int:
    """
    Copy files matching .worktreeinclude patterns that are also gitignored.

    Returns the number of files/directories copied.
    """
    patterns = read_worktreeinclude(repo_root)
    if not patterns:
        print("  No .worktreeinclude file found, skipping file copy")
        return 0

    gitignored = get_gitignored_files(repo_root)
    if not gitignored:
        print("  No gitignored files found to copy")
        return 0

    copied = set()

    for gitignored_path in gitignored:
        for pattern in patterns:
            if matches_pattern(gitignored_path, pattern, repo_root):
                # Calculate destination path
                rel_path = gitignored_path.relative_to(repo_root)
                dst = worktree_path / rel_path

                # Skip if already copied (from parent directory copy)
                if dst in copied:
                    continue

                dst.parent.mkdir(parents=True, exist_ok=True)

                if gitignored_path.is_dir():
                    if not dst.exists():
                        shutil.copytree(gitignored_path, dst, dirs_exist_ok=True)
                        copied.add(dst)
                        print(f"  Copied directory: {rel_path}")
                elif gitignored_path.is_file():
                    shutil.copy2(gitignored_path, dst)
                    copied.add(dst)
                    print(f"  Copied: {rel_path}")

                break  # Don't check more patterns for this file

    if not copied:
        print("  No matching files found to copy")

    return len(copied)


def create_worktree(branch: str, path: Optional[str] = None) -> tuple[str, Path]:
    """
    Create a worktree for a branch.

    Args:
        branch: Branch name (will be created if doesn't exist)
        path: Optional custom worktree path

    Returns:
        Tuple of (branch_name, worktree_path)
    """
    repo_root = get_repo_root()
    repo_name = get_repo_name()

    if not path:
        # Create worktree in parent directory
        # Replace slashes in branch name for path
        safe_branch = branch.replace('/', '-')
        worktree_path = repo_root.parent / f"{repo_name}-{safe_branch}"
    else:
        worktree_path = Path(path).resolve()

    if worktree_path.exists():
        print(f"Worktree already exists: {worktree_path}")
        return branch, worktree_path

    # Get default branch
    default_branch = get_default_branch()

    # Check if branch already exists
    try:
        run_git("rev-parse", "--verify", branch)
        # Branch exists, just add worktree
        run_git("worktree", "add", str(worktree_path), branch)
        print(f"Created worktree from existing branch: {branch}")
    except subprocess.CalledProcessError:
        # Branch doesn't exist, create new branch from default
        run_git("worktree", "add", "-b", branch, str(worktree_path), default_branch)
        print(f"Created worktree with new branch: {branch}")

    print(f"Worktree path: {worktree_path}")

    # Copy gitignored files from .worktreeinclude
    print("\nCopying gitignored files from .worktreeinclude:")
    copy_worktree_files(repo_root, worktree_path)

    return branch, worktree_path


def list_worktrees() -> None:
    """List all worktrees."""
    result = run_git("worktree", "list", "--porcelain")

    worktrees = []
    current = {}

    for line in result.splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line[9:]}
        elif line.startswith("HEAD "):
            current["head"] = line[5:]
        elif line.startswith("branch "):
            current["branch"] = line[7:].replace("refs/heads/", "")
        elif line == "bare":
            current["bare"] = True
        elif line == "detached":
            current["detached"] = True

    if current:
        worktrees.append(current)

    print("Active worktrees:")
    for wt in worktrees:
        path = wt.get("path", "unknown")
        branch = wt.get("branch", "")

        if wt.get("bare"):
            print(f"  {path} (bare)")
        elif wt.get("detached"):
            head = wt.get("head", "unknown")[:8]
            print(f"  {path} (detached at {head})")
        else:
            print(f"  {path} [{branch}]")


def remove_worktree(identifier: str) -> None:
    """
    Remove a worktree by branch name or path.

    Args:
        identifier: Either a branch name or a path to the worktree
    """
    # Check if identifier is a path
    if '/' in identifier and Path(identifier).exists():
        worktree_path = Path(identifier).resolve()
    else:
        # Try to find worktree by branch name
        repo_root = get_repo_root()
        repo_name = get_repo_name()

        result = run_git("worktree", "list", "--porcelain")
        worktree_path = None
        current_path = None

        for line in result.splitlines():
            if line.startswith("worktree "):
                current_path = line[9:]
            elif line.startswith("branch ") and identifier in line:
                worktree_path = Path(current_path)
                break

        if not worktree_path:
            # Try conventional path
            safe_branch = identifier.replace('/', '-')
            worktree_path = repo_root.parent / f"{repo_name}-{safe_branch}"

    if not worktree_path or not worktree_path.exists():
        print(f"Could not find worktree for: {identifier}")
        return

    # Remove worktree
    run_git("worktree", "remove", str(worktree_path), "--force")
    print(f"Removed worktree: {worktree_path}")


def main():
    parser = argparse.ArgumentParser(description="Git worktree manager with .worktreeinclude support")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    create_p = subparsers.add_parser("create", help="Create worktree for a branch")
    create_p.add_argument("branch", help="Branch name")
    create_p.add_argument("--path", help="Custom worktree path")

    # list
    subparsers.add_parser("list", help="List active worktrees")

    # remove
    remove_p = subparsers.add_parser("remove", help="Remove worktree")
    remove_p.add_argument("identifier", help="Branch name or worktree path")

    args = parser.parse_args()

    if args.command == "create":
        branch, path = create_worktree(args.branch, getattr(args, 'path', None))
        print(f"\nTo start working:")
        print(f"  cd {path}")

    elif args.command == "list":
        list_worktrees()

    elif args.command == "remove":
        remove_worktree(args.identifier)


if __name__ == "__main__":
    main()
