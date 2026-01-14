#!/usr/bin/env python3
"""
Linear GraphQL API client.

Provides functions for interacting with Linear's API for issue management,
workflow state transitions, and team operations.

Environment:
    LINEAR_API_KEY: Personal API key from Linear Settings → API
    LINEAR_TEAM_KEY: (Optional) Team key like "ASA", defaults to first team
"""

import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any, Optional


LINEAR_API_URL = "https://api.linear.app/graphql"


def get_api_key() -> str:
    """Get Linear API key from environment."""
    key = os.environ.get("LINEAR_API_KEY")
    if not key:
        print("Error: LINEAR_API_KEY environment variable not set", file=sys.stderr)
        print("Get your API key from: Linear Settings → API → Personal API Keys", file=sys.stderr)
        sys.exit(1)
    return key


def graphql(query: str, variables: Optional[dict] = None) -> dict:
    """Execute GraphQL query against Linear API."""
    api_key = get_api_key()

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        LINEAR_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": api_key,
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        print(f"HTTP Error {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network Error: {e.reason}", file=sys.stderr)
        sys.exit(1)

    if "errors" in result:
        for err in result["errors"]:
            print(f"GraphQL Error: {err.get('message', err)}", file=sys.stderr)
        sys.exit(1)

    return result


def get_viewer() -> dict:
    """Get current authenticated user info."""
    query = """
    query {
      viewer {
        id
        name
        email
      }
    }
    """
    result = graphql(query)
    return result["data"]["viewer"]


def get_teams() -> list[dict]:
    """Get all teams the user has access to."""
    query = """
    query {
      teams {
        nodes {
          id
          key
          name
        }
      }
    }
    """
    result = graphql(query)
    return result["data"]["teams"]["nodes"]


def get_team(team_key: Optional[str] = None) -> dict:
    """Get team by key, or first team if not specified."""
    team_key = team_key or os.environ.get("LINEAR_TEAM_KEY")
    teams = get_teams()

    if not teams:
        print("Error: No teams found", file=sys.stderr)
        sys.exit(1)

    if team_key:
        for team in teams:
            if team["key"].upper() == team_key.upper():
                return team
        available = ", ".join(t["key"] for t in teams)
        print(f"Error: Team '{team_key}' not found. Available: {available}", file=sys.stderr)
        sys.exit(1)

    # Return first team
    return teams[0]


def get_workflow_states(team_id: str) -> list[dict]:
    """Get all workflow states for a team."""
    query = """
    query($teamId: String!) {
      workflowStates(filter: { team: { id: { eq: $teamId } } }) {
        nodes {
          id
          name
          type
          position
        }
      }
    }
    """
    result = graphql(query, {"teamId": team_id})
    states = result["data"]["workflowStates"]["nodes"]
    # Sort by position
    return sorted(states, key=lambda s: s["position"])


def get_issue(issue_identifier: str) -> dict:
    """
    Get issue by identifier (e.g., "ASA-42").

    Returns full issue details including comments.
    """
    query = """
    query($identifier: String!) {
      issue(id: $identifier) {
        id
        identifier
        title
        description
        priority
        priorityLabel
        state {
          id
          name
          type
        }
        assignee {
          id
          name
        }
        labels {
          nodes {
            id
            name
            color
          }
        }
        comments {
          nodes {
            id
            body
            createdAt
            user {
              name
            }
          }
        }
        createdAt
        updatedAt
        url
      }
    }
    """
    result = graphql(query, {"identifier": issue_identifier})
    return result["data"]["issue"]


def list_issues(
    team_id: str,
    state_name: Optional[str] = None,
    limit: int = 50
) -> list[dict]:
    """
    List issues for a team, optionally filtered by workflow state.

    Returns issues sorted by priority (highest first), then by creation date.
    """
    # Build filter
    filter_parts = [f'team: {{ id: {{ eq: "{team_id}" }} }}']

    if state_name:
        filter_parts.append(f'state: {{ name: {{ eqIgnoreCase: "{state_name}" }} }}')

    filter_str = ", ".join(filter_parts)

    query = f"""
    query {{
      issues(
        filter: {{ {filter_str} }}
        first: {limit}
        sort: [
          {{ priority: {{ order: Ascending, noPriorityFirst: false }} }},
          {{ createdAt: {{ order: Ascending }} }}
        ]
      ) {{
        nodes {{
          id
          identifier
          title
          priority
          priorityLabel
          state {{
            id
            name
            type
          }}
          assignee {{
            name
          }}
          createdAt
          url
        }}
      }}
    }}
    """
    result = graphql(query)
    return result["data"]["issues"]["nodes"]


def create_comment(issue_id: str, body: str) -> dict:
    """Create a comment on an issue."""
    mutation = """
    mutation($issueId: String!, $body: String!) {
      commentCreate(input: {
        issueId: $issueId
        body: $body
      }) {
        success
        comment {
          id
          body
          createdAt
        }
      }
    }
    """
    result = graphql(mutation, {"issueId": issue_id, "body": body})
    return result["data"]["commentCreate"]


def update_issue_state(issue_id: str, state_id: str) -> dict:
    """Update an issue's workflow state."""
    mutation = """
    mutation($issueId: String!, $stateId: String!) {
      issueUpdate(id: $issueId, input: {
        stateId: $stateId
      }) {
        success
        issue {
          id
          identifier
          state {
            name
          }
        }
      }
    }
    """
    result = graphql(mutation, {"issueId": issue_id, "stateId": state_id})
    return result["data"]["issueUpdate"]


def move_issue_to_state(issue_identifier: str, target_state_name: str) -> dict:
    """
    Move an issue to a different workflow state by name.

    Args:
        issue_identifier: Issue identifier like "ASA-42"
        target_state_name: Target state name like "In Progress"
    """
    # Get issue to find team
    issue = get_issue(issue_identifier)
    if not issue:
        print(f"Error: Issue {issue_identifier} not found", file=sys.stderr)
        sys.exit(1)

    # Extract team key from identifier (e.g., "ASA" from "ASA-42")
    team_key = issue_identifier.split("-")[0]
    team = get_team(team_key)

    # Get workflow states for team
    states = get_workflow_states(team["id"])

    # Find target state (case-insensitive)
    target_lower = target_state_name.lower().strip()
    target_state = None

    for state in states:
        if state["name"].lower() == target_lower:
            target_state = state
            break

    if not target_state:
        available = ", ".join(f'"{s["name"]}"' for s in states)
        print(f"Error: State '{target_state_name}' not found. Available: {available}", file=sys.stderr)
        sys.exit(1)

    # Update issue state
    result = update_issue_state(issue["id"], target_state["id"])

    if result["success"]:
        print(f"Moved {issue_identifier} to '{target_state['name']}'")

    return result


def test_connection() -> bool:
    """Test API connection and return True if successful."""
    try:
        viewer = get_viewer()
        return viewer is not None
    except SystemExit:
        return False


if __name__ == "__main__":
    # Quick test
    print("Testing Linear API connection...")

    viewer = get_viewer()
    print(f"Authenticated as: {viewer['name']} ({viewer['email']})")

    teams = get_teams()
    print(f"\nTeams ({len(teams)}):")
    for team in teams:
        print(f"  - {team['key']}: {team['name']}")

    if teams:
        team = teams[0]
        print(f"\nWorkflow states for {team['key']}:")
        states = get_workflow_states(team["id"])
        for state in states:
            print(f"  - {state['name']} ({state['type']})")
