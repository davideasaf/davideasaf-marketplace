#!/usr/bin/env python3
"""
GitHub Projects V2 board operations.

Move issues between project board columns by updating the Status field.

Usage:
    # Move issue to column
    project_board.py move 42 --to planning
    project_board.py move 42 --to "ready for dev"

    # List project columns/statuses
    project_board.py columns

Environment:
    Requires `gh` CLI with project scope: `gh auth refresh -s project`
"""

import argparse
import json
import subprocess
import sys
from typing import Optional


def run_gh(*args: str, check: bool = True) -> str:
    """Run gh CLI command."""
    cmd = ["gh"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def graphql(query: str, **variables) -> dict:
    """Execute GraphQL query via gh api."""
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        args.extend(["-f", f"{key}={value}"])

    result = run_gh(*args)
    data = json.loads(result)

    if "errors" in data:
        print(f"GraphQL Error: {data['errors']}", file=sys.stderr)
        sys.exit(1)

    return data


def get_repo_info() -> tuple[str, str]:
    """Get repository owner and name."""
    result = run_gh("repo", "view", "--json", "owner,name")
    data = json.loads(result)
    return data["owner"]["login"], data["name"]


def find_project_for_issue(number: int) -> Optional[dict]:
    """Find the project containing this issue and return project/item info."""
    result = run_gh(
        "issue", "view", str(number),
        "--json", "projectItems"
    )
    data = json.loads(result)

    items = data.get("projectItems", [])
    if not items:
        return None

    # Return first project item with full info
    return items[0]


def get_project_id_from_repo() -> Optional[str]:
    """Get first project linked to the repository."""
    owner, repo = get_repo_info()

    query = """
    query($owner: String!, $repo: String!) {
      repository(owner: $owner, name: $repo) {
        projectsV2(first: 1) {
          nodes {
            id
            title
          }
        }
      }
    }
    """
    result = graphql(query, owner=owner, repo=repo)
    projects = result["data"]["repository"]["projectsV2"]["nodes"]

    if not projects:
        return None

    return projects[0]["id"]


def get_project_fields(project_id: str) -> list[dict]:
    """Get project fields including Status options."""
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          fields(first: 20) {
            nodes {
              ... on ProjectV2Field {
                id
                name
              }
              ... on ProjectV2SingleSelectField {
                id
                name
                options {
                  id
                  name
                }
              }
            }
          }
        }
      }
    }
    """
    result = graphql(query, projectId=project_id)
    return result["data"]["node"]["fields"]["nodes"]


def get_status_field(project_id: str) -> tuple[str, list[dict]]:
    """Get the Status field ID and its options."""
    fields = get_project_fields(project_id)

    for field in fields:
        if field.get("name", "").lower() == "status":
            return field["id"], field.get("options", [])

    raise ValueError("Status field not found in project")


def add_issue_to_project(project_id: str, issue_number: int) -> str:
    """Add issue to project and return the item ID."""
    owner, repo = get_repo_info()

    # Get issue node ID
    result = run_gh("issue", "view", str(issue_number), "--json", "id")
    issue_data = json.loads(result)
    issue_id = issue_data["id"]

    # Add to project
    mutation = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {
        projectId: $projectId
        contentId: $contentId
      }) {
        item {
          id
        }
      }
    }
    """
    result = graphql(mutation, projectId=project_id, contentId=issue_id)
    return result["data"]["addProjectV2ItemById"]["item"]["id"]


def move_issue(number: int, target_status: str) -> None:
    """Move issue to a different project board column."""
    # Find project item
    item = find_project_for_issue(number)

    if not item:
        # Issue not in any project, try to add it
        project_id = get_project_id_from_repo()
        if not project_id:
            print(f"Issue #{number} is not in any project and no project found for repo", file=sys.stderr)
            sys.exit(1)

        print(f"Adding issue #{number} to project...")
        item_id = add_issue_to_project(project_id, number)
    else:
        project_id = item.get("project", {}).get("id")
        item_id = item.get("id")

    if not project_id or not item_id:
        print(f"Could not find project or item ID for issue #{number}", file=sys.stderr)
        sys.exit(1)

    # Get status field and options
    field_id, options = get_status_field(project_id)

    # Find matching option (case-insensitive, normalize spaces)
    target_lower = target_status.lower().replace("-", " ").replace("_", " ")
    option_id = None

    for opt in options:
        opt_name = opt["name"].lower().replace("-", " ").replace("_", " ")
        if opt_name == target_lower:
            option_id = opt["id"]
            break

    if not option_id:
        available = ", ".join(f'"{opt["name"]}"' for opt in options)
        print(f"Status '{target_status}' not found. Available: {available}", file=sys.stderr)
        sys.exit(1)

    # Update the item
    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
      updateProjectV2ItemFieldValue(
        input: {
          projectId: $projectId
          itemId: $itemId
          fieldId: $fieldId
          value: { singleSelectOptionId: $optionId }
        }
      ) {
        projectV2Item {
          id
        }
      }
    }
    """

    graphql(
        mutation,
        projectId=project_id,
        itemId=item_id,
        fieldId=field_id,
        optionId=option_id
    )

    print(f"Moved issue #{number} to '{target_status}'")


def list_columns() -> None:
    """List available project columns from first project found."""
    project_id = get_project_id_from_repo()

    if not project_id:
        print("No projects found for this repository")
        return

    # Get project title
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          title
        }
      }
    }
    """
    result = graphql(query, projectId=project_id)
    title = result["data"]["node"]["title"]
    print(f"Project: {title}")

    field_id, options = get_status_field(project_id)
    print("\nStatus columns:")
    for opt in options:
        print(f"  - {opt['name']}")


def main():
    parser = argparse.ArgumentParser(description="GitHub Projects V2 board operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # move
    move_p = subparsers.add_parser("move", help="Move issue to column")
    move_p.add_argument("number", type=int, help="Issue number")
    move_p.add_argument("--to", required=True, help="Target status/column")

    # columns
    subparsers.add_parser("columns", help="List available columns")

    args = parser.parse_args()

    if args.command == "move":
        move_issue(args.number, args.to)

    elif args.command == "columns":
        list_columns()


if __name__ == "__main__":
    main()
