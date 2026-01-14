# Linear Dev Flow - Workflow States

## State Machine Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          LINEAR DEV FLOW WORKFLOW                             │
└──────────────────────────────────────────────────────────────────────────────┘

                    HUMAN MANAGED                   AGENT ASSISTED
                ─────────────────────           ─────────────────────

┌──────────┐                ┌──────────┐
│ Backlog  │ ──────────────►│   Todo   │
│          │   Human adds   │          │
│  HUMAN   │   issue        │HUMAN→AGENT│
└──────────┘                └────┬─────┘
                                 │
                                 │ Agent creates plan,
                                 │ posts as comment
                                 │
                                 ▼
                           ┌──────────┐
                           │   Todo   │ (with plan comment)
                           │          │
                           │  HUMAN   │ ◄─── Human reviews plan
                           └────┬─────┘
                                │
                                │ Human approves,
                                │ moves to Dev Ready
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ AGENT PICKUP ZONE                                                            │
│                                                                              │
│  ┌───────────┐                                                               │
│  │ Dev Ready │◄─────────────────────────────────────────────┐               │
│  │           │                                               │               │
│  │   AGENT   │                                               │               │
│  └─────┬─────┘                                               │               │
│        │                                                     │               │
│        │ Agent picks up (manual trigger),                    │               │
│        │ moves to In Progress                                │               │
│        │                                                     │               │
│        ▼                                                     │               │
│  ┌─────────────┐                                             │               │
│  │ In Progress │                                             │               │
│  │             │                                             │               │
│  │   AGENT    │                                             │               │
│  └──────┬──────┘                                             │               │
│         │                                                    │               │
│         │ Agent implements,                                  │               │
│         │ runs validation,                                   │               │
│         │ moves to In Review                                 │               │
│         │                                                    │               │
└─────────┼────────────────────────────────────────────────────┼───────────────┘
          │                                                    │
          ▼                                                    │
    ┌───────────┐                                              │
    │ In Review │──────────────────────────────────────────────┘
    │           │   Human rejects
    │   HUMAN   │   (comments + move back to Dev Ready)
    └─────┬─────┘
          │
          │ Human approves,
          │ moves to Done
          │
          ▼
    ┌──────────┐
    │   Done   │
    │          │
    │ ARCHIVE  │
    └──────────┘
```

## State Details

### Backlog (Human Managed)
- **Owner:** Human
- **Agent Action:** None
- **Purpose:** Long-term storage for ideas and future work
- **Exit Criteria:** Human moves to Todo when ready for planning

### Todo (Human → Agent)
- **Owner:** Human initiates, Agent creates plan
- **Agent Action:** Analyze issue, create implementation plan, post as comment
- **Purpose:** Issues ready for planning
- **Entry:** Human moves from Backlog
- **Exit:** Human reviews plan, moves to Dev Ready (approve) or provides feedback (stay in Todo)

### Dev Ready (Agent Pickup)
- **Owner:** Agent
- **Agent Action:** Pick up (manual trigger), create worktree, implement
- **Purpose:** Approved plans ready for implementation
- **Entry:** Human approves plan and moves here, OR human returns from In Review with feedback
- **Exit:** Agent moves to In Progress when starting work

### In Progress (Agent Working)
- **Owner:** Agent
- **Agent Action:** Active implementation following approved plan
- **Purpose:** Transient state during implementation
- **Entry:** Agent moves from Dev Ready
- **Exit:** Agent moves to In Review when implementation complete

### In Review (Human Validation)
- **Owner:** Human
- **Agent Action:** STOP - Wait for human validation
- **Purpose:** Human reviews completed work
- **Entry:** Agent moves from In Progress after completing implementation
- **Exit:** Human approves → Done, OR Human rejects → Dev Ready (with feedback)

### Done (Archive)
- **Owner:** Archive
- **Agent Action:** Cleanup worktree (optional)
- **Purpose:** Completed work
- **Entry:** Human approves from In Review
- **Exit:** None (final state)

## Valid State Transitions

| From | To | Who | Trigger |
|------|-----|-----|---------|
| Backlog | Todo | Human | Issue ready for planning |
| Todo | Dev Ready | Human | Plan approved |
| Dev Ready | In Progress | Agent | Implementation started |
| In Progress | In Review | Agent | Implementation complete |
| In Review | Done | Human | Work approved |
| In Review | Dev Ready | Human | Feedback provided |
| Dev Ready | Todo | Human | Need more planning |

## Priority Ordering

When picking up issues, Linear's priority field determines order:

| Priority | Linear Value | Sort Order |
|----------|--------------|------------|
| Urgent | 1 | 1 (highest) |
| High | 2 | 2 |
| Medium | 3 | 3 |
| Low | 4 | 4 |
| No Priority | 0 | 5 (lowest) |

Tie-breaker: Issue creation date (oldest first)
