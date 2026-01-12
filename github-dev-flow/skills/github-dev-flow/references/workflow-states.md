# Workflow States Reference

## State Machine

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     GitHub Dev Flow State Machine                        │
└─────────────────────────────────────────────────────────────────────────┘

    ┌──────────┐     Agent      ┌───────────┐     Human     ┌─────────────┐
    │   Todo   │ ────────────→  │ Planning  │ ────────────→ │ Dev Ready   │
    └──────────┘   (plan)       └───────────┘   (approve)   └─────────────┘
         ↑                            │                           │  ↑
         │                            │ (feedback)                │  │
         │                            ↓                           │  │
    New issues              Agent updates plan,                   │  │ Human
    from backlog            stays in Planning                     │  │ (feedback)
                                                                  │  │
                                                                  │  │ Agent
                                                                  │  │ (implement)
                                                                  ↓  │
    ┌──────────┐     Human      ┌───────────┐     Agent     ┌─────────────┐
    │   Done   │ ←───────────── │  Review   │ ←──────────── │ In Progress │
    └──────────┘   (merge)      └───────────┘  (complete)   └─────────────┘
                                      │                           ↑
                                      │                           │
                                      └───────────────────────────┘
                                            Human moves back
                                            (request changes)
```

## Column Definitions

### Todo
- **Owner**: Backlog / Product
- **Entry**: New issues, backlog grooming
- **Exit**: Agent picks up and creates plan
- **Agent Action**: Analyze issue, build plan, post comment, move to Planning

### Planning
- **Owner**: Human review
- **Entry**: Agent submits plan as comment
- **Exit**: Human approves or provides feedback
- **Agent Action**: **STOP** - Wait for human feedback
- **Human Action**:
  - Review plan for completeness
  - Provide feedback via comment if changes needed
  - Move to "Dev Ready" when plan is approved

### Dev Ready
- **Owner**: Agent pickup queue
- **Entry**: Human approved plan OR human requested changes on PR
- **Exit**: Agent begins implementation
- **Agent Action**:
  - Check if returning issue (existing branch/PR) → read feedback first
  - Pick up, create worktree, implement, create/update PR

### In Progress
- **Owner**: Agent (active work)
- **Entry**: Agent begins implementation
- **Exit**: Implementation complete
- **Agent Action**:
  - Execute plan step by step
  - Make atomic commits
  - Run tests continuously
  - No human intervention expected

### Review
- **Owner**: Human review
- **Entry**: Agent submits PR with completion comment
- **Exit**: Human merges OR moves back to Dev Ready for changes
- **Agent Action**: **STOP** - Wait for human review
- **Human Action**:
  - Review code changes
  - Run CI/CD pipeline
  - If changes needed: Comment feedback, move to "Dev Ready"
  - If approved: Merge PR to main

### Done
- **Owner**: Archive
- **Entry**: PR merged to main
- **Exit**: N/A
- **Cleanup**: Remove worktree if exists, close issue

## Agent Stop Points

The agent **MUST** stop and wait at these points:

1. **After moving to Planning**
   - Plan has been posted as comment
   - Human must review and approve
   - Agent cannot proceed until issue is moved to "Dev Ready"

2. **After moving to Review**
   - Implementation complete
   - PR created and linked to issue
   - Human must review code and merge
   - Agent cannot proceed until human action

## Human Intervention Points

| State | Human Action Required |
|-------|----------------------|
| Planning → Dev Ready | Review plan, approve or provide feedback |
| Review → Done | Review PR, run tests, merge to main |
| Review → Dev Ready | Request changes: comment feedback, move back to Dev Ready |

## Priority Labels

Issues are picked up in priority order:

1. `P: Critical` - Production emergencies, blocking issues
2. `P: HIGH` - Important features, significant bugs
3. `P: Medium` - Normal priority work (default)
4. `P: low` - Nice-to-have, can wait

If no priority label exists, issues are sorted by creation date (oldest first).

## Issue Types

GitHub native issue types are used to classify issues:

- **Bug** - An unexpected problem or behavior
- **Feature** - A request, idea, or new functionality
- **Task** - A specific piece of work

## Confidence Scores

When completing work, agents provide a confidence score (0-100):

| Score Range | Meaning |
|-------------|---------|
| 90-100 | High confidence - All tests pass, well-tested code |
| 70-89 | Good confidence - Tests pass, minor edge cases possible |
| 50-69 | Moderate confidence - Core functionality works, needs review |
| 30-49 | Low confidence - Partial implementation, known issues |
| 0-29 | Very low - Significant issues, may need rework |

Confidence score helps humans prioritize review effort.
