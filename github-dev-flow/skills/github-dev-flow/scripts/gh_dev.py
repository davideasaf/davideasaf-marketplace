#!/usr/bin/env python3
"""
GitHub development workflow CLI for github-dev-flow skill.

Core operations for issue management, comment posting, image extraction,
and auto-pickup logic.

Usage:
    # List issues by project board status
    gh_dev.py list --status todo
    gh_dev.py list --status "dev ready" --milestone "Phase 1"

    # Find next issue to work on (auto-selects by priority)
    gh_dev.py pickup
    gh_dev.py pickup --milestone "Phase 1"

    # Show issue with full details
    gh_dev.py show 42

    # Post comment (from file or inline)
    gh_dev.py comment 42 --file plan.md
    gh_dev.py comment 42 --body "Implementation started"

    # Post completion comment and create PR
    gh_dev.py complete 42 --summary "Added feature X" --confidence 85 --test-results "42/42 passing"

    # Download issue images
    gh_dev.py images 42 --output ./issue-images/

    # Get status report
    gh_dev.py report
    gh_dev.py report --milestone "Phase 1"

Environment:
    Requires `gh` CLI authenticated with repo and project scopes.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional


# Priority labels in order (highest to lowest)
PRIORITY_ORDER = ["P: Critical", "P: HIGH", "P: Medium", "P: low"]

# Columns where agent can pickup work
PICKUP_COLUMNS = ["todo", "dev ready"]


def run_gh(*args: str, capture: bool = True, check: bool = True) -> str:
    """Run gh CLI command."""
    cmd = ["gh"] + list(args)
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip() if capture else ""


def get_repo() -> str:
    """Get current repo in owner/repo format."""
    return run_gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner")


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to URL-friendly slug."""
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug[:max_length]


def get_issue(number: int) -> dict:
    """Get full issue details as JSON."""
    result = run_gh(
        "issue", "view", str(number),
        "--json", "number,title,body,state,labels,assignees,milestone,comments,projectItems,createdAt"
    )
    return json.loads(result)


def get_project_status(issue: dict) -> Optional[str]:
    """Extract project board status from issue."""
    for item in issue.get("projectItems", []):
        status = item.get("status", {})
        if status:
            return status.get("name", "").lower()
    return None


def get_priority_rank(issue: dict) -> int:
    """Get priority rank (lower = higher priority)."""
    labels = [l["name"].lower() for l in issue.get("labels", [])]
    for i, priority in enumerate(PRIORITY_ORDER):
        if priority.lower() in labels:
            return i
    return len(PRIORITY_ORDER)  # No priority label = lowest


def list_issues(
    status: Optional[str] = None,
    milestone: Optional[str] = None,
    format_type: str = "table"
) -> list:
    """List issues, optionally filtered by project status or milestone."""
    args = ["issue", "list", "--state", "open", "--json",
            "number,title,state,labels,milestone,projectItems,createdAt"]

    if milestone:
        args.extend(["--milestone", milestone])

    result = run_gh(*args)
    issues = json.loads(result)

    if status:
        status_lower = status.lower().replace("-", " ").replace("_", " ")
        filtered = []
        for issue in issues:
            issue_status = get_project_status(issue)
            if issue_status == status_lower:
                filtered.append(issue)
        issues = filtered

    return issues


def pickup_issue(milestone: Optional[str] = None) -> Optional[dict]:
    """Find the next issue to work on based on priority."""
    # Get all issues in pickup columns
    all_issues = []

    for column in PICKUP_COLUMNS:
        issues = list_issues(status=column, milestone=milestone)
        for issue in issues:
            issue["_pickup_column"] = column
            all_issues.append(issue)

    if not all_issues:
        return None

    # Sort by priority (lower rank = higher priority), then by creation date
    all_issues.sort(key=lambda i: (get_priority_rank(i), i.get("createdAt", "")))

    return all_issues[0]


def show_issue(number: int) -> None:
    """Display issue details."""
    issue = get_issue(number)

    print(f"Issue #{issue['number']}: {issue['title']}")
    print(f"State: {issue['state']}")

    if issue.get('labels'):
        labels = ", ".join(l['name'] for l in issue['labels'])
        print(f"Labels: {labels}")

    if issue.get('milestone'):
        print(f"Milestone: {issue['milestone']['title']}")

    status = get_project_status(issue)
    if status:
        print(f"Project Status: {status}")

    if issue.get('assignees'):
        assignees = ", ".join(a['login'] for a in issue['assignees'])
        print(f"Assignees: {assignees}")

    print("\n--- Body ---")
    print(issue.get('body', '(no body)'))

    if issue.get('comments'):
        print(f"\n--- Comments ({len(issue['comments'])}) ---")
        for i, comment in enumerate(issue['comments'], 1):
            author = comment.get('author', {}).get('login', 'unknown')
            print(f"\n[{i}] {author}:")
            print(comment.get('body', ''))


def post_comment(number: int, body: str) -> None:
    """Post a comment to an issue."""
    run_gh("issue", "comment", str(number), "--body", body, capture=False)
    print(f"Comment posted to issue #{number}")


def create_pr(number: int, title: str, body: str) -> str:
    """Create a pull request for the issue."""
    result = run_gh(
        "pr", "create",
        "--title", title,
        "--body", body,
        check=False
    )
    return result


def post_completion(number: int, summary: str, confidence: int, test_results: str) -> None:
    """Post a structured completion comment and create PR."""
    issue = get_issue(number)
    branch = f"issue/{number}-{slugify(issue['title'])}"

    # Create PR first
    pr_title = f"#{number}: {issue['title']}"
    pr_body = f"""## Summary
{summary}

## Test Results
```
{test_results}
```

## Confidence Score: {confidence}/100

Closes #{number}
"""

    pr_result = create_pr(number, pr_title, pr_body)
    pr_url = pr_result.strip() if pr_result else "(PR creation failed)"

    # Post completion comment
    comment_body = f"""## Implementation Complete for #{number}

### Summary
{summary}

### Test Results
```
{test_results}
```

### Confidence Score: {confidence}/100

### Ready for Review
- Branch: `{branch}`
- PR: {pr_url}
"""
    post_comment(number, comment_body)

    # Move to review
    try:
        from project_board import move_issue
        move_issue(number, "review")
    except ImportError:
        print("Note: Run project_board.py move to move issue to Review column")


def extract_images(number: int, output_dir: str) -> list[str]:
    """Extract and download images from issue body and comments."""
    issue = get_issue(number)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Collect all text content
    all_text = issue.get('body', '') or ''
    for comment in issue.get('comments', []):
        all_text += '\n' + (comment.get('body', '') or '')

    # Find GitHub-hosted images
    patterns = [
        r'!\[.*?\]\((https://(?:user-images\.githubusercontent\.com|github\.com/user-attachments)[^\)]+)\)',
        r'<img[^>]+src=["\']?(https://(?:user-images\.githubusercontent\.com|github\.com/user-attachments)[^"\'\s>]+)',
    ]

    urls = []
    for pattern in patterns:
        urls.extend(re.findall(pattern, all_text))

    if not urls:
        print(f"No images found in issue #{number}")
        return []

    print(f"Found {len(urls)} image(s) in issue #{number}")
    downloaded = []

    for i, url in enumerate(urls, 1):
        # Determine extension from URL
        url_path = url.split('?')[0]
        if '.' in url_path.split('/')[-1]:
            ext = '.' + url_path.split('.')[-1]
        else:
            ext = '.png'

        filename = f"issue-{number}-image-{i}{ext}"
        filepath = output_path / filename

        # Use gh api to download (handles auth)
        result = subprocess.run(
            ["gh", "api", "-H", "Accept: application/octet-stream", url],
            capture_output=True
        )

        if result.returncode == 0:
            filepath.write_bytes(result.stdout)
            print(f"  Downloaded: {filepath}")
            downloaded.append(str(filepath))
        else:
            # Fallback to curl
            result = subprocess.run(
                ["curl", "-sL", "-o", str(filepath), url],
                capture_output=True
            )
            if result.returncode == 0:
                print(f"  Downloaded: {filepath}")
                downloaded.append(str(filepath))
            else:
                print(f"  Failed to download: {url}", file=sys.stderr)

    return downloaded


def generate_report(milestone: Optional[str] = None) -> None:
    """Generate a status report of issues."""
    args = ["issue", "list", "--state", "all", "--json",
            "number,title,state,labels,milestone,projectItems,createdAt"]

    if milestone:
        args.extend(["--milestone", milestone])

    result = run_gh(*args)
    issues = json.loads(result)

    # Group by status
    by_status = defaultdict(list)
    by_label = defaultdict(list)

    for issue in issues:
        status = get_project_status(issue) or "no status"
        by_status[status].append(issue)

        for label in issue.get("labels", []):
            by_label[label["name"]].append(issue)

    # Print report
    if milestone:
        print(f"## Status Report: {milestone}\n")
    else:
        print("## Status Report: All Issues\n")

    print(f"**Total Issues:** {len(issues)}\n")

    print("### By Status")
    status_order = ["todo", "planning", "dev ready", "in progress", "review", "done", "no status"]
    for status in status_order:
        if status in by_status:
            print(f"\n**{status.title()}** ({len(by_status[status])})")
            for issue in by_status[status][:5]:  # Show first 5
                labels = ", ".join(l["name"] for l in issue.get("labels", []))
                label_str = f" [{labels}]" if labels else ""
                print(f"  - #{issue['number']}: {issue['title']}{label_str}")
            if len(by_status[status]) > 5:
                print(f"  ... and {len(by_status[status]) - 5} more")

    # Show priority distribution
    print("\n### By Priority")
    for priority in PRIORITY_ORDER:
        if priority in by_label:
            print(f"- **{priority}**: {len(by_label[priority])} issues")


def main():
    parser = argparse.ArgumentParser(description="GitHub dev workflow CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    list_p = subparsers.add_parser("list", help="List issues")
    list_p.add_argument("--status", help="Filter by project board status")
    list_p.add_argument("--milestone", help="Filter by milestone")
    list_p.add_argument("--format", choices=["table", "json"], default="table")

    # pickup
    pickup_p = subparsers.add_parser("pickup", help="Find next issue to work on")
    pickup_p.add_argument("--milestone", help="Filter by milestone")

    # show
    show_p = subparsers.add_parser("show", help="Show issue details")
    show_p.add_argument("number", type=int, help="Issue number")

    # comment
    comment_p = subparsers.add_parser("comment", help="Post comment to issue")
    comment_p.add_argument("number", type=int, help="Issue number")
    comment_g = comment_p.add_mutually_exclusive_group(required=True)
    comment_g.add_argument("--body", help="Comment body text")
    comment_g.add_argument("--file", help="Read comment from file")

    # complete
    complete_p = subparsers.add_parser("complete", help="Post completion comment and create PR")
    complete_p.add_argument("number", type=int, help="Issue number")
    complete_p.add_argument("--summary", required=True, help="Summary of changes")
    complete_p.add_argument("--confidence", type=int, required=True, help="Confidence score 0-100")
    complete_p.add_argument("--test-results", required=True, help="Test results summary")

    # images
    images_p = subparsers.add_parser("images", help="Download issue images")
    images_p.add_argument("number", type=int, help="Issue number")
    images_p.add_argument("--output", "-o", default="./issue-images", help="Output directory")

    # report
    report_p = subparsers.add_parser("report", help="Generate status report")
    report_p.add_argument("--milestone", help="Filter by milestone")

    args = parser.parse_args()

    if args.command == "list":
        issues = list_issues(args.status, args.milestone)
        if args.format == "json":
            print(json.dumps(issues, indent=2))
        else:
            if not issues:
                print("No issues found")
            else:
                for issue in issues:
                    labels = ", ".join(l['name'] for l in issue.get('labels', []))
                    label_str = f" [{labels}]" if labels else ""
                    status = get_project_status(issue) or "no status"
                    print(f"#{issue['number']}: {issue['title']}{label_str} ({status})")

    elif args.command == "pickup":
        issue = pickup_issue(args.milestone)
        if issue:
            labels = ", ".join(l['name'] for l in issue.get('labels', []))
            label_str = f" [{labels}]" if labels else ""
            column = issue.get("_pickup_column", "unknown")
            print(f"Next issue to work on:")
            print(f"  #{issue['number']}: {issue['title']}{label_str}")
            print(f"  Column: {column}")
            print(f"  Branch: issue/{issue['number']}-{slugify(issue['title'])}")
        else:
            print("No issues ready for pickup")

    elif args.command == "show":
        show_issue(args.number)

    elif args.command == "comment":
        if args.file:
            body = Path(args.file).read_text()
        else:
            body = args.body
        post_comment(args.number, body)

    elif args.command == "complete":
        post_completion(args.number, args.summary, args.confidence, args.test_results)

    elif args.command == "images":
        extract_images(args.number, args.output)

    elif args.command == "report":
        generate_report(args.milestone)


if __name__ == "__main__":
    main()
