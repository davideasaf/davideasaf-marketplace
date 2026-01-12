#!/usr/bin/env python3
"""
Create a GitHub issue with priority labels and project board integration.

Usage:
    # Create bug issue with high priority
    uv run python create_issue.py --type bug --priority high "Login button broken" --body "Steps to reproduce..."

    # Create feature issue (defaults to medium priority)
    uv run python create_issue.py --type feature "Add dark mode" --body "Users want dark mode..."

    # Create task with critical priority
    uv run python create_issue.py --type task --priority critical "Deploy hotfix" --body "..."

    # Create from file
    uv run python create_issue.py --type bug "Login broken" --body-file issue.md

    # Skip project board
    uv run python create_issue.py --type bug "Quick fix" --body "..." --no-project

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

# Priority labels mapping (CLI argument -> GitHub label)
PRIORITY_LABELS = {
    "critical": "P: Critical",
    "high": "P: HIGH",
    "medium": "P: Medium",
    "low": "P: low",
}

# Label colors for automatic creation
LABEL_COLORS = {
    "P: Critical": "7d0303",  # Dark red
    "P: HIGH": "b60205",      # Red
    "P: Medium": "fbca04",    # Yellow
    "P: low": "c5def5",       # Light blue
}

# Cache for issue type IDs
_issue_type_cache: dict[str, str] = {}


def run_gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run gh CLI command."""
    cmd = ["gh"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result


def get_repo_info() -> tuple[str, str] | None:
    """Get owner and repo name from current directory."""
    result = run_gh("repo", "view", "--json", "owner,name", check=False)
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    return data["owner"]["login"], data["name"]


def get_issue_type_id(owner: str, repo: str, type_name: str) -> str | None:
    """Get issue type ID via GraphQL. Returns None if not available."""
    cache_key = f"{owner}/{repo}"

    # Check cache first
    if cache_key not in _issue_type_cache:
        query = """
        query($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            issueTypes(first: 10) {
              nodes { id, name }
            }
          }
        }
        """
        result = subprocess.run(
            ["gh", "api", "graphql",
             "-H", "GraphQL-Features: issue_types",
             "-f", f"query={query}",
             "-f", f"owner={owner}",
             "-f", f"name={repo}"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return None

        try:
            data = json.loads(result.stdout)
            types = data.get("data", {}).get("repository", {}).get("issueTypes", {}).get("nodes", [])
            _issue_type_cache[cache_key] = {t["name"].lower(): t["id"] for t in types}
        except (json.JSONDecodeError, KeyError):
            return None

    return _issue_type_cache.get(cache_key, {}).get(type_name.lower())


def get_issue_node_id(issue_number: int) -> str | None:
    """Get the GraphQL node ID for an issue."""
    result = run_gh("issue", "view", str(issue_number), "--json", "id", check=False)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)["id"]
    except (json.JSONDecodeError, KeyError):
        return None


def set_issue_type(issue_node_id: str, issue_type_id: str) -> bool:
    """Set the issue type via GraphQL mutation."""
    mutation = """
    mutation($issueId: ID!, $issueTypeId: ID!) {
      updateIssueIssueType(input: { issueId: $issueId, issueTypeId: $issueTypeId }) {
        issue { id }
      }
    }
    """
    result = subprocess.run(
        ["gh", "api", "graphql",
         "-H", "GraphQL-Features: issue_types",
         "-f", f"query={mutation}",
         "-f", f"issueId={issue_node_id}",
         "-f", f"issueTypeId={issue_type_id}"],
        capture_output=True, text=True
    )
    return result.returncode == 0


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
    title: str,
    issue_type: str | None = None,
    priority: str = "medium",
    body: str | None = None,
    body_file: str | None = None,
    labels: list[str] | None = None,
    add_to_project: bool = True,
    project_status: str = "todo",
) -> int | None:
    """
    Create a GitHub issue with priority label and optional issue type.

    Args:
        title: Issue title
        issue_type: GitHub native issue type (bug, feature, task)
        priority: Priority level (critical, high, medium, low)
        body: Issue body text
        body_file: Path to file containing issue body
        labels: Additional labels to add
        add_to_project: Whether to add to project board
        project_status: Project board column (default: todo)

    Returns:
        Issue number on success, None on failure.
    """
    # Get priority label
    priority_label = PRIORITY_LABELS.get(priority.lower(), PRIORITY_LABELS["medium"])
    final_labels = [priority_label]

    # Add any additional labels
    if labels:
        final_labels.extend(labels)

    # Ensure priority label exists with appropriate color
    ensure_label_exists(priority_label, color=LABEL_COLORS.get(priority_label))

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

        # Set issue type via GraphQL if specified
        if issue_type:
            repo_info = get_repo_info()
            if repo_info:
                owner, repo = repo_info
                type_id = get_issue_type_id(owner, repo, issue_type)
                if type_id:
                    issue_node_id = get_issue_node_id(issue_number)
                    if issue_node_id and set_issue_type(issue_node_id, type_id):
                        print(f"Set issue type: {issue_type.capitalize()}")
                    else:
                        print(f"Warning: Could not set issue type", file=sys.stderr)
                else:
                    print(f"Warning: Issue type '{issue_type}' not available in this repo", file=sys.stderr)

        # Add to project board
        if add_to_project:
            add_to_project_board(issue_number, project_status)

        return issue_number
    else:
        print(f"Issue created: {output}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Create GitHub issue with priority labels and project board integration"
    )
    parser.add_argument(
        "title",
        help="Issue title",
    )
    parser.add_argument(
        "--type", "-t",
        choices=["bug", "feature", "task"],
        help="GitHub native issue type",
    )
    parser.add_argument(
        "--priority", "-p",
        choices=["critical", "high", "medium", "low"],
        default="medium",
        help="Priority level (default: medium)",
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
        title=args.title,
        issue_type=args.type,
        priority=args.priority,
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
