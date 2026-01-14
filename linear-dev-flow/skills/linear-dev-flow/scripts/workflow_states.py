#!/usr/bin/env python3
"""
Workflow state management for Linear Dev Flow.

Defines the expected workflow states, valid transitions, and priority ordering
for the agent-driven development workflow.

Expected States:
    Backlog → Todo → Dev Ready → In Progress → In Review → Done

Agent Pickup Columns:
    - Todo (for planning)
    - Dev Ready (for implementation)
"""

from dataclasses import dataclass
from typing import Optional


# Expected workflow states in order
WORKFLOW_STATES = [
    "Backlog",
    "Todo",
    "Dev Ready",
    "In Progress",
    "In Review",
    "Done",
]

# Alternative names for states (for matching)
STATE_ALIASES = {
    "backlog": "Backlog",
    "todo": "Todo",
    "to do": "Todo",
    "to-do": "Todo",
    "dev ready": "Dev Ready",
    "devready": "Dev Ready",
    "ready": "Dev Ready",
    "ready for dev": "Dev Ready",
    "in progress": "In Progress",
    "inprogress": "In Progress",
    "in-progress": "In Progress",
    "wip": "In Progress",
    "in review": "In Review",
    "inreview": "In Review",
    "in-review": "In Review",
    "review": "In Review",
    "done": "Done",
    "completed": "Done",
    "complete": "Done",
    "closed": "Done",
}

# States where agent can pick up work
AGENT_PICKUP_STATES = ["Todo", "Dev Ready"]

# States where agent is actively working
AGENT_WORK_STATES = ["In Progress"]

# States requiring human action
HUMAN_STATES = ["Backlog", "In Review", "Done"]

# Linear priority values (0 = No priority, 1 = Urgent, 2 = High, 3 = Medium, 4 = Low)
PRIORITY_ORDER = {
    0: 5,  # No priority - lowest
    1: 1,  # Urgent - highest
    2: 2,  # High
    3: 3,  # Medium
    4: 4,  # Low
}


@dataclass
class WorkflowState:
    """Represents a workflow state with metadata."""
    name: str
    owner: str  # "agent" or "human"
    description: str


STATES_METADATA = {
    "Backlog": WorkflowState(
        name="Backlog",
        owner="human",
        description="Human-managed backlog. Agent does not interact."
    ),
    "Todo": WorkflowState(
        name="Todo",
        owner="human→agent",
        description="Human adds issues. Agent creates implementation plan and posts as comment."
    ),
    "Dev Ready": WorkflowState(
        name="Dev Ready",
        owner="agent",
        description="Plan approved. Agent picks up (manual trigger), implements."
    ),
    "In Progress": WorkflowState(
        name="In Progress",
        owner="agent",
        description="Agent actively implementing. Moves to In Review when complete."
    ),
    "In Review": WorkflowState(
        name="In Review",
        owner="human",
        description="Human validates. Approves to Done or returns to Dev Ready."
    ),
    "Done": WorkflowState(
        name="Done",
        owner="archive",
        description="Complete. Cleanup and archive."
    ),
}


def normalize_state_name(name: str) -> Optional[str]:
    """
    Normalize a state name to its canonical form.

    Args:
        name: State name to normalize (case-insensitive)

    Returns:
        Canonical state name or None if not recognized
    """
    normalized = name.lower().strip()

    # Check aliases
    if normalized in STATE_ALIASES:
        return STATE_ALIASES[normalized]

    # Check direct match (case-insensitive)
    for state in WORKFLOW_STATES:
        if state.lower() == normalized:
            return state

    return None


def is_valid_transition(from_state: str, to_state: str) -> bool:
    """
    Check if a state transition is valid in the workflow.

    Returns True for most transitions since the workflow is flexible.
    Main restriction: Cannot skip backwards arbitrarily.
    """
    from_norm = normalize_state_name(from_state)
    to_norm = normalize_state_name(to_state)

    if not from_norm or not to_norm:
        return False

    # All forward transitions are valid
    from_idx = WORKFLOW_STATES.index(from_norm)
    to_idx = WORKFLOW_STATES.index(to_norm)

    if to_idx >= from_idx:
        return True

    # Valid backward transitions
    valid_backwards = [
        ("In Review", "Dev Ready"),  # Human rejects
        ("In Progress", "Dev Ready"),  # Agent hit blocker
        ("Dev Ready", "Todo"),  # Need more planning
    ]

    return (from_norm, to_norm) in valid_backwards


def get_priority_rank(priority: int) -> int:
    """
    Get sort rank for Linear priority.

    Lower rank = higher priority for sorting.
    """
    return PRIORITY_ORDER.get(priority, 5)


def sort_issues_by_priority(issues: list[dict]) -> list[dict]:
    """
    Sort issues by priority (highest first), then by creation date.

    Args:
        issues: List of issue dicts with 'priority' and 'createdAt' fields

    Returns:
        Sorted list of issues
    """
    def sort_key(issue):
        priority = issue.get("priority", 0)
        created = issue.get("createdAt", "")
        return (get_priority_rank(priority), created)

    return sorted(issues, key=sort_key)


def get_next_pickup_issue(issues: list[dict], from_state: str = "Dev Ready") -> Optional[dict]:
    """
    Get the next issue to pick up from a given state.

    Args:
        issues: List of issues to consider
        from_state: State to pick up from (default: "Dev Ready")

    Returns:
        Highest priority issue in the specified state, or None
    """
    state_norm = normalize_state_name(from_state)
    if not state_norm:
        return None

    # Filter to issues in target state
    candidates = [
        issue for issue in issues
        if normalize_state_name(issue.get("state", {}).get("name", "")) == state_norm
    ]

    if not candidates:
        return None

    # Sort by priority and return first
    sorted_issues = sort_issues_by_priority(candidates)
    return sorted_issues[0] if sorted_issues else None


def validate_workflow_states(available_states: list[str]) -> dict:
    """
    Validate that all required workflow states exist.

    Args:
        available_states: List of state names from Linear

    Returns:
        Dict with 'valid' bool, 'missing' list, and 'extra' list
    """
    normalized_available = set()
    for state in available_states:
        norm = normalize_state_name(state)
        if norm:
            normalized_available.add(norm)
        else:
            normalized_available.add(state)  # Keep original if not recognized

    required = set(WORKFLOW_STATES)
    missing = required - normalized_available
    extra = normalized_available - required

    return {
        "valid": len(missing) == 0,
        "missing": list(missing),
        "extra": list(extra),
        "found": list(normalized_available & required),
    }


if __name__ == "__main__":
    # Print workflow documentation
    print("Linear Dev Flow Workflow States")
    print("=" * 50)
    print()

    for state_name in WORKFLOW_STATES:
        meta = STATES_METADATA[state_name]
        print(f"[{state_name}]")
        print(f"  Owner: {meta.owner}")
        print(f"  {meta.description}")
        print()

    print("Agent Pickup States:", ", ".join(AGENT_PICKUP_STATES))
    print("Human Review States:", ", ".join(HUMAN_STATES))
