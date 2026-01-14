#!/usr/bin/env python3
"""
Linear development workflow CLI for linear-dev-flow skill.

Core operations for issue management, planning, comment posting,
state transitions, and auto-pickup logic.

Usage:
    # List issues by workflow state
    linear_dev.py list --status "Dev Ready"
    linear_dev.py list --status todo

    # Find next issue to work on (auto-selects by priority)
    linear_dev.py pickup
    linear_dev.py pickup --status "Dev Ready"

    # Show issue with full details
    linear_dev.py show ASA-42

    # Post comment to issue
    linear_dev.py comment ASA-42 --body "Starting implementation"
    linear_dev.py comment ASA-42 --file plan.md

    # Move issue to workflow state
    linear_dev.py move ASA-42 --to "In Progress"

    # Post completion comment and move to In Review
    linear_dev.py complete ASA-42 --summary "Added feature X" --confidence 85

Environment:
    LINEAR_API_KEY: Personal API key from Linear Settings → API
    LINEAR_TEAM_KEY: (Optional) Team key, defaults to first team
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

from linear_api import (
    get_team,
    get_issue,
    get_workflow_states,
    list_issues as api_list_issues,
    create_comment,
    move_issue_to_state,
)
from workflow_states import (
    normalize_state_name,
    sort_issues_by_priority,
    AGENT_PICKUP_STATES,
)


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to URL-friendly slug."""
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug[:max_length]


def list_issues(status: Optional[str] = None, format_type: str = "table") -> list:
    """List issues, optionally filtered by workflow state."""
    team = get_team()

    # Normalize status name if provided
    if status:
        normalized = normalize_state_name(status)
        if normalized:
            status = normalized

    issues = api_list_issues(team["id"], state_name=status)

    # Sort by priority
    issues = sort_issues_by_priority(issues)

    return issues


def pickup_issue(status: Optional[str] = None) -> Optional[dict]:
    """Find the next issue to work on based on priority."""
    team = get_team()

    # If no status specified, check agent pickup states
    statuses_to_check = [status] if status else AGENT_PICKUP_STATES

    all_issues = []
    for state in statuses_to_check:
        normalized = normalize_state_name(state)
        if not normalized:
            continue

        issues = api_list_issues(team["id"], state_name=normalized)
        for issue in issues:
            issue["_pickup_state"] = normalized
            all_issues.append(issue)

    if not all_issues:
        return None

    # Sort by priority and return first
    sorted_issues = sort_issues_by_priority(all_issues)
    return sorted_issues[0] if sorted_issues else None


def show_issue(identifier: str) -> None:
    """Display issue details."""
    issue = get_issue(identifier)

    if not issue:
        print(f"Issue {identifier} not found", file=sys.stderr)
        sys.exit(1)

    print(f"Issue {issue['identifier']}: {issue['title']}")
    print(f"URL: {issue['url']}")
    print(f"State: {issue['state']['name']}")
    print(f"Priority: {issue.get('priorityLabel', 'No priority')}")

    if issue.get('assignee'):
        print(f"Assignee: {issue['assignee']['name']}")

    labels = issue.get('labels', {}).get('nodes', [])
    if labels:
        label_names = ", ".join(l['name'] for l in labels)
        print(f"Labels: {label_names}")

    print("\n--- Description ---")
    print(issue.get('description', '(no description)') or '(no description)')

    comments = issue.get('comments', {}).get('nodes', [])
    if comments:
        print(f"\n--- Comments ({len(comments)}) ---")
        for i, comment in enumerate(comments, 1):
            author = comment.get('user', {}).get('name', 'unknown')
            created = comment.get('createdAt', '')[:10]
            print(f"\n[{i}] {author} ({created}):")
            print(comment.get('body', ''))


def post_comment(identifier: str, body: str) -> None:
    """Post a comment to an issue."""
    issue = get_issue(identifier)
    if not issue:
        print(f"Issue {identifier} not found", file=sys.stderr)
        sys.exit(1)

    result = create_comment(issue['id'], body)
    if result.get('success'):
        print(f"Comment posted to {identifier}")
    else:
        print(f"Failed to post comment to {identifier}", file=sys.stderr)
        sys.exit(1)


def move_issue(identifier: str, target_state: str) -> None:
    """Move issue to a workflow state."""
    move_issue_to_state(identifier, target_state)


def post_completion(identifier: str, summary: str, confidence: int) -> None:
    """Post a structured completion comment and move to In Review."""
    issue = get_issue(identifier)
    if not issue:
        print(f"Issue {identifier} not found", file=sys.stderr)
        sys.exit(1)

    branch = f"issue/{identifier.lower()}-{slugify(issue['title'])}"

    # Post completion comment
    comment_body = f"""## Implementation Complete for {identifier}

### Summary
{summary}

### Confidence Score: {confidence}/100

### Ready for Review
- Branch: `{branch}`
- Issue: {issue['url']}

---
*Awaiting human review. Move to Done if acceptable, or back to Dev Ready with feedback.*
"""
    result = create_comment(issue['id'], comment_body)
    if result.get('success'):
        print(f"Completion comment posted to {identifier}")
    else:
        print(f"Failed to post completion comment", file=sys.stderr)
        sys.exit(1)

    # Move to In Review
    move_issue_to_state(identifier, "In Review")


def list_states() -> None:
    """List available workflow states for the team."""
    team = get_team()
    print(f"Team: {team['key']} ({team['name']})")

    states = get_workflow_states(team['id'])
    print("\nWorkflow States:")
    for state in states:
        state_type = state.get('type', 'unknown')
        print(f"  - {state['name']} ({state_type})")


def main():
    parser = argparse.ArgumentParser(description="Linear dev workflow CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    list_p = subparsers.add_parser("list", help="List issues")
    list_p.add_argument("--status", help="Filter by workflow state")
    list_p.add_argument("--format", choices=["table", "json"], default="table")

    # pickup
    pickup_p = subparsers.add_parser("pickup", help="Find next issue to work on")
    pickup_p.add_argument("--status", help="Filter by workflow state (default: Todo, Dev Ready)")

    # show
    show_p = subparsers.add_parser("show", help="Show issue details")
    show_p.add_argument("identifier", help="Issue identifier (e.g., ASA-42)")

    # comment
    comment_p = subparsers.add_parser("comment", help="Post comment to issue")
    comment_p.add_argument("identifier", help="Issue identifier (e.g., ASA-42)")
    comment_g = comment_p.add_mutually_exclusive_group(required=True)
    comment_g.add_argument("--body", help="Comment body text")
    comment_g.add_argument("--file", help="Read comment from file")

    # move
    move_p = subparsers.add_parser("move", help="Move issue to workflow state")
    move_p.add_argument("identifier", help="Issue identifier (e.g., ASA-42)")
    move_p.add_argument("--to", required=True, help="Target workflow state")

    # complete
    complete_p = subparsers.add_parser("complete", help="Post completion and move to In Review")
    complete_p.add_argument("identifier", help="Issue identifier (e.g., ASA-42)")
    complete_p.add_argument("--summary", required=True, help="Summary of changes")
    complete_p.add_argument("--confidence", type=int, required=True, help="Confidence score 0-100")

    # states
    subparsers.add_parser("states", help="List workflow states")

    args = parser.parse_args()

    if args.command == "list":
        issues = list_issues(args.status)
        if args.format == "json":
            print(json.dumps(issues, indent=2))
        else:
            if not issues:
                print("No issues found")
            else:
                for issue in issues:
                    state = issue.get('state', {}).get('name', 'unknown')
                    priority = issue.get('priorityLabel', '')
                    priority_str = f" [{priority}]" if priority else ""
                    print(f"{issue['identifier']}: {issue['title']}{priority_str} ({state})")

    elif args.command == "pickup":
        issue = pickup_issue(args.status)
        if issue:
            priority = issue.get('priorityLabel', 'No priority')
            state = issue.get('_pickup_state', issue.get('state', {}).get('name', 'unknown'))
            print(f"Next issue to work on:")
            print(f"  {issue['identifier']}: {issue['title']}")
            print(f"  State: {state}")
            print(f"  Priority: {priority}")
            print(f"  Branch: issue/{issue['identifier'].lower()}-{slugify(issue['title'])}")
            print(f"  URL: {issue['url']}")
        else:
            print("No issues ready for pickup")

    elif args.command == "show":
        show_issue(args.identifier)

    elif args.command == "comment":
        if args.file:
            body = Path(args.file).read_text()
        else:
            body = args.body
        post_comment(args.identifier, body)

    elif args.command == "move":
        move_issue(args.identifier, args.to)

    elif args.command == "complete":
        post_completion(args.identifier, args.summary, args.confidence)

    elif args.command == "states":
        list_states()


if __name__ == "__main__":
    main()
