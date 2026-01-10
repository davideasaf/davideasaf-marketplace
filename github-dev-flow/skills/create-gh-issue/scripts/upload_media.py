#!/usr/bin/env python3
"""
Upload media files to GitHub repository for issue embedding.

Uploads files to .github/issue-assets/ folder and returns markdown image syntax.

Usage:
    uv run python upload_media.py <file_path> [--repo OWNER/REPO] [--branch BRANCH]

Returns:
    Markdown image syntax: ![alt](url)
"""

import argparse
import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def get_gh_token() -> str | None:
    """Get GitHub token from gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def detect_repo() -> str | None:
    """Detect repo from current directory."""
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_default_branch(repo: str) -> str:
    """Get the default branch for a repository."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}", "-q", ".default_branch"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "main"


def file_exists_in_repo(repo: str, branch: str, path: str) -> bool:
    """Check if a file exists in the repository."""
    try:
        subprocess.run(
            ["gh", "api", f"repos/{repo}/contents/{path}?ref={branch}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def upload_file(repo: str, branch: str, local_path: Path, remote_path: str) -> str | None:
    """
    Upload a file to GitHub repository.

    Returns the raw URL for the file.
    """
    # Read and encode file
    content = local_path.read_bytes()
    content_b64 = base64.b64encode(content).decode("utf-8")

    # Check if file already exists (need SHA for update)
    sha = None
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/contents/{remote_path}?ref={branch}", "-q", ".sha"],
            capture_output=True,
            text=True,
            check=True,
        )
        sha = result.stdout.strip()
    except subprocess.CalledProcessError:
        pass  # File doesn't exist yet

    # Prepare API payload
    payload = {
        "message": f"Add issue asset: {local_path.name}",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    # Upload via GitHub API
    try:
        result = subprocess.run(
            [
                "gh", "api",
                f"repos/{repo}/contents/{remote_path}",
                "-X", "PUT",
                "-f", f"message={payload['message']}",
                "-f", f"content={content_b64}",
                "-f", f"branch={branch}",
            ] + (["-f", f"sha={sha}"] if sha else []),
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse response to get the download URL
        response = json.loads(result.stdout)
        download_url = response.get("content", {}).get("download_url")
        return download_url

    except subprocess.CalledProcessError as e:
        print(f"Error uploading file: {e.stderr}", file=sys.stderr)
        return None


def generate_asset_path(local_path: Path) -> str:
    """Generate a unique asset path based on file content hash."""
    content = local_path.read_bytes()
    content_hash = hashlib.sha256(content).hexdigest()[:12]
    suffix = local_path.suffix.lower()
    return f".github/issue-assets/{content_hash}{suffix}"


def upload_media(
    file_path: str,
    repo: str | None = None,
    branch: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Upload media file and return markdown syntax.

    Returns:
        Tuple of (markdown_syntax, raw_url) or (None, None) on failure.
    """
    local_path = Path(file_path)

    if not local_path.exists():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        return None, None

    # Detect repo if not provided
    if not repo:
        repo = detect_repo()
        if not repo:
            print("Error: Could not detect repository. Use --repo flag.", file=sys.stderr)
            return None, None

    # Get default branch if not provided
    if not branch:
        branch = get_default_branch(repo)

    # Generate unique asset path
    remote_path = generate_asset_path(local_path)

    # Upload file
    raw_url = upload_file(repo, branch, local_path, remote_path)

    if not raw_url:
        return None, None

    # Generate markdown
    alt_text = local_path.stem.replace("-", " ").replace("_", " ")
    markdown = f"![{alt_text}]({raw_url})"

    return markdown, raw_url


def main():
    parser = argparse.ArgumentParser(
        description="Upload media file to GitHub for issue embedding"
    )
    parser.add_argument(
        "file_path",
        help="Path to the media file (image/GIF)",
    )
    parser.add_argument(
        "--repo",
        help="Repository in owner/repo format (auto-detected if not provided)",
    )
    parser.add_argument(
        "--branch",
        help="Branch to upload to (default: repo's default branch)",
    )
    parser.add_argument(
        "--url-only",
        action="store_true",
        help="Output only the raw URL, not markdown syntax",
    )
    args = parser.parse_args()

    markdown, raw_url = upload_media(args.file_path, args.repo, args.branch)

    if markdown and raw_url:
        if args.url_only:
            print(raw_url)
        else:
            print(markdown)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
