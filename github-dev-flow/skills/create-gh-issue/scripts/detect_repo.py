#!/usr/bin/env python3
"""
Detect GitHub repository from git remote.

Usage:
    uv run python detect_repo.py [--remote REMOTE]

Returns owner/repo string (e.g., "anthropics/claude-code")
"""

import argparse
import re
import subprocess
import sys


def get_remote_url(remote: str = "origin") -> str | None:
    """Get the URL of a git remote."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", remote],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def parse_github_url(url: str) -> str | None:
    """
    Parse a GitHub URL to extract owner/repo.

    Handles:
    - SSH: git@github.com:owner/repo.git
    - HTTPS: https://github.com/owner/repo.git
    - HTTPS (no .git): https://github.com/owner/repo
    """
    patterns = [
        # SSH format: git@github.com:owner/repo.git
        r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        # HTTPS format: https://github.com/owner/repo.git
        r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
    ]

    for pattern in patterns:
        match = re.match(pattern, url)
        if match:
            owner, repo = match.groups()
            return f"{owner}/{repo}"

    return None


def detect_repo(remote: str = "origin") -> str | None:
    """Detect GitHub owner/repo from git remote."""
    url = get_remote_url(remote)
    if not url:
        return None
    return parse_github_url(url)


def main():
    parser = argparse.ArgumentParser(
        description="Detect GitHub repository from git remote"
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Git remote name (default: origin)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress error messages, exit with code 1 on failure",
    )
    args = parser.parse_args()

    repo = detect_repo(args.remote)

    if repo:
        print(repo)
        sys.exit(0)
    else:
        if not args.quiet:
            print("Error: Could not detect GitHub repository.", file=sys.stderr)
            print("Make sure you're in a git repository with a GitHub remote.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
