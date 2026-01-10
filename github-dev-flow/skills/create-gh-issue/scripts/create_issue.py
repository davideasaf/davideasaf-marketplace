#!/usr/bin/env python3
"""
Create a GitHub issue with labels and project board integration.

Usage:
    # Create bug issue
    uv run python create_issue.py bug "Login button broken" --body "Steps to reproduce..."

    # Create feature issue
    uv run python create_issue.py feature "Add dark mode" --body "Users want dark mode..."

    # Create from file
    uv run python create_issue.py bug "Login broken" --body-file issue.md

    # Skip project board
    uv run python create_issue.py bug "Quick fix" --body "..." --no-project

Environment:
    Requires `gh` CLI authenticated with repo access.
    For project board: `gh auth refresh -s project`
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


# Path to github-dev-flow's project_board.py (relative within plugin)
_SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_BOARD_SCRIPT = _SCRIPT_DIR / "../../github-dev-flow/scripts/project_board.py"


def run_gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run gh CLI command."""
    cmd = ["gh"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result


def ensure_label_exists(label: str, color: str | None = None, description: str | None = None) -> None:
    """Create label if it doesn't exist."""
    result = run_gh("label", "list", "--json", "name", check=False)
    if result.returncode != 0:
        return

    labels = json.loads(result.stdout)
    existing = [l["name"].lower() for l in labels]

    if label.lower() not in existing:
        args = ["label", "create", label]
        if color:
            args.extend(["--color", color])
        if description:
            args.extend(["--description", description])
        run_gh(*args, check=False)


def add_to_project_board(issue_number: int, status: str = "todo") -> bool:
    """Add issue to project board using github-dev-flow's script."""
    if not PROJECT_BOARD_SCRIPT.exists():
        print(f"Warning: project_board.py not found at {PROJECT_BOARD_SCRIPT}", file=sys.stderr)
        return False

    try:
        result = subprocess.run(
            ["uv", "run", "python", str(PROJECT_BOARD_SCRIPT), "move", str(issue_number), "--to", status],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(result.stdout.strip())
            return True
        else:
            print(f"Warning: Could not add to project board: {result.stderr.strip()}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"Warning: Project board error: {e}", file=sys.stderr)
        return False


def create_issue(
    issue_type: str,
    title: str,
    body: str | None = None,
    body_file: str | None = None,
    labels: list[str] | None = None,
    add_to_project: bool = True,
    project_status: str = "todo",
) -> int | None:
    """
    Create a GitHub issue.

    Returns:
        Issue number on success, None on failure.
    """
    # Determine labels based on type
    type_labels = {
        "bug": ["bug", "needs-triage"],
        "feature": ["enhancement", "needs-triage"],
        "enhancement": ["enhancement", "needs-triage"],
    }

    final_labels = type_labels.get(issue_type.lower(), ["needs-triage"])
    if labels:
        final_labels.extend(labels)

    # Ensure labels exist with appropriate colors
    label_colors = {
        "bug": "d73a4a",
        "enhancement": "a2eeef",
        "needs-triage": "fbca04",
    }
    for label in final_labels:
        ensure_label_exists(label, color=label_colors.get(label))

    # Build command
    args = ["issue", "create", "--title", title]

    if body_file:
        args.extend(["--body-file", body_file])
    elif body:
        args.extend(["--body", body])
    else:
        args.extend(["--body", ""])

    for label in final_labels:
        args.extend(["--label", label])

    # Create the issue
    result = run_gh(*args)
    output = result.stdout.strip()

    # Parse issue URL to get number
    # Output is like: https://github.com/owner/repo/issues/123
    if "/issues/" in output:
        issue_number = int(output.split("/issues/")[-1])
        print(f"Created issue #{issue_number}: {output}")

        # Add to project board
        if add_to_project:
            add_to_project_board(issue_number, project_status)

        return issue_number
    else:
        print(f"Issue created: {output}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Create GitHub issue with labels and project board integration"
    )
    parser.add_argument(
        "type",
        choices=["bug", "feature", "enhancement"],
        help="Issue type (determines labels)",
    )
    parser.add_argument(
        "title",
        help="Issue title",
    )
    parser.add_argument(
        "--body", "-b",
        help="Issue body (markdown)",
    )
    parser.add_argument(
        "--body-file", "-f",
        help="Read issue body from file",
    )
    parser.add_argument(
        "--label", "-l",
        action="append",
        dest="labels",
        help="Additional labels (can be repeated)",
    )
    parser.add_argument(
        "--no-project",
        action="store_true",
        help="Don't add to project board",
    )
    parser.add_argument(
        "--project-status",
        default="todo",
        help="Project board status/column (default: todo)",
    )

    args = parser.parse_args()

    if not args.body and not args.body_file:
        print("Error: Either --body or --body-file is required", file=sys.stderr)
        sys.exit(1)

    issue_number = create_issue(
        issue_type=args.type,
        title=args.title,
        body=args.body,
        body_file=args.body_file,
        labels=args.labels,
        add_to_project=not args.no_project,
        project_status=args.project_status,
    )

    if issue_number:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
