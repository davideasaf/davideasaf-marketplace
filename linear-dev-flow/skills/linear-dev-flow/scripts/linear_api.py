#!/usr/bin/env python3
"""
Linear GraphQL API client.

Provides functions for interacting with Linear's API for issue management,
workflow state transitions, and team operations.

Environment Variables (in priority order):
    Authentication (one required):
        LINEAR_OAUTH_ACCESS_TOKEN: Pre-generated OAuth token (lin_oauth_*)
        LINEAR_OAUTH_CLIENT_ID + LINEAR_OAUTH_CLIENT_SECRET: Client Credentials flow
        LINEAR_API_KEY: Personal API key (lin_api_*) from Linear Settings → API

    Optional:
        LINEAR_TEAM_KEY: Team key like "ASA", defaults to first team

Authentication Methods:
    1. Pre-generated token: Set LINEAR_OAUTH_ACCESS_TOKEN directly
    2. Client Credentials: Set LINEAR_OAUTH_CLIENT_ID and LINEAR_OAUTH_CLIENT_SECRET
       - Automatically exchanges credentials for a 30-day app token
       - Posts as the OAuth application, not a personal user
    3. Personal API key: Set LINEAR_API_KEY (posts as your user)
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Optional


LINEAR_API_URL = "https://api.linear.app/graphql"
LINEAR_TOKEN_URL = "https://api.linear.app/oauth/token"

# Module-level cache for client credentials token
_cached_token: Optional[str] = None


def _exchange_client_credentials() -> str:
    """
    Exchange OAuth client credentials for an access token.

    Uses the Client Credentials grant type to obtain a 30-day app token.

    Returns:
        Access token string.

    Raises:
        SystemExit on failure.
    """
    client_id = os.environ.get("LINEAR_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("LINEAR_OAUTH_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Error: Both LINEAR_OAUTH_CLIENT_ID and LINEAR_OAUTH_CLIENT_SECRET required", file=sys.stderr)
        sys.exit(1)

    # Request body for client credentials grant
    # Using broad scopes - Linear will limit to what the app has access to
    payload = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "read,write,issues:create,comments:create",
    }).encode("utf-8")

    req = urllib.request.Request(
        LINEAR_TOKEN_URL,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        print(f"OAuth token exchange failed (HTTP {e.code}): {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network Error during token exchange: {e.reason}", file=sys.stderr)
        sys.exit(1)

    if "access_token" not in result:
        print(f"OAuth response missing access_token: {result}", file=sys.stderr)
        sys.exit(1)

    return result["access_token"]


def get_auth_token() -> str:
    """
    Get Linear authentication token from environment.

    Priority:
        1. LINEAR_OAUTH_ACCESS_TOKEN - Pre-generated OAuth token
        2. LINEAR_OAUTH_CLIENT_ID + LINEAR_OAUTH_CLIENT_SECRET - Client Credentials flow
        3. LINEAR_API_KEY - Personal API key (for user auth)

    Returns:
        Authentication token to use in Authorization header.
    """
    global _cached_token

    # Check for pre-generated OAuth token first
    oauth_token = os.environ.get("LINEAR_OAUTH_ACCESS_TOKEN")
    if oauth_token:
        return oauth_token

    # Check for client credentials (exchange for token)
    client_id = os.environ.get("LINEAR_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("LINEAR_OAUTH_CLIENT_SECRET")
    if client_id and client_secret:
        # Use cached token if available
        if _cached_token:
            return _cached_token
        # Exchange credentials for token
        _cached_token = _exchange_client_credentials()
        return _cached_token

    # Fall back to personal API key
    api_key = os.environ.get("LINEAR_API_KEY")
    if api_key:
        return api_key

    # No credentials found
    print("Error: No Linear authentication configured", file=sys.stderr)
    print("Set one of the following:", file=sys.stderr)
    print("  LINEAR_OAUTH_ACCESS_TOKEN - Pre-generated OAuth token", file=sys.stderr)
    print("  LINEAR_OAUTH_CLIENT_ID + LINEAR_OAUTH_CLIENT_SECRET - Client Credentials", file=sys.stderr)
    print("  LINEAR_API_KEY - Personal API key (lin_api_*)", file=sys.stderr)
    print("", file=sys.stderr)
    print("Get credentials from: Linear Settings → API", file=sys.stderr)
    sys.exit(1)


def get_auth_method() -> str:
    """
    Get the authentication method being used.

    Returns:
        "oauth_token" if using LINEAR_OAUTH_ACCESS_TOKEN
        "client_credentials" if using LINEAR_OAUTH_CLIENT_ID + SECRET
        "api_key" if using LINEAR_API_KEY
        "none" if no credentials configured
    """
    if os.environ.get("LINEAR_OAUTH_ACCESS_TOKEN"):
        return "oauth_token"
    if os.environ.get("LINEAR_OAUTH_CLIENT_ID") and os.environ.get("LINEAR_OAUTH_CLIENT_SECRET"):
        return "client_credentials"
    if os.environ.get("LINEAR_API_KEY"):
        return "api_key"
    return "none"


# Backward compatibility alias
def get_api_key() -> str:
    """Deprecated: Use get_auth_token() instead."""
    return get_auth_token()


def graphql(query: str, variables: Optional[dict] = None) -> dict:
    """Execute GraphQL query against Linear API."""
    auth_token = get_auth_token()

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        LINEAR_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": auth_token,
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

    auth_method = get_auth_method()
    print(f"Auth method: {auth_method}")

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
