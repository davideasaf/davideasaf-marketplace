# Workflow States Reference

## State Machine

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     GitHub Dev Flow State Machine                        │
└─────────────────────────────────────────────────────────────────────────┘

    ┌──────────┐     Agent      ┌───────────┐     Human     ┌─────────────┐
    │   Todo   │ ────────────→  │ Planning  │ ────────────→ │Dev Ready│
    └──────────┘   (plan)       └───────────┘   (approve)   └─────────────┘
         ↑                            │                           │
         │                            │ (feedback)                │
         │                            ↓                           │
    New issues              Agent updates plan,                   │
    from backlog            stays in Planning                     │
                                                                  │
                                                                  │ Agent
                                                                  │ (implement)
                                                                  ↓
    ┌──────────┐     Human      ┌───────────┐     Agent     ┌─────────────┐
    │   Done   │ ←───────────── │  Review   │ ←──────────── │ In Progress │
    └──────────┘   (merge)      └───────────┘  (complete)   └─────────────┘
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
- **Entry**: Human approved plan
- **Exit**: Agent begins implementation
- **Agent Action**: Pick up, create worktree, implement, create PR

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
- **Exit**: Human merges or requests changes
- **Agent Action**: **STOP** - Wait for human review
- **Human Action**:
  - Review code changes
  - Run CI/CD pipeline
  - Request changes if needed
  - Merge PR to main

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

## Priority Labels

Issues are picked up in priority order:

1. `priority:critical` - Blocking issues, production bugs
2. `priority:high` - Important features, significant bugs
3. `priority:medium` - Normal priority work
4. `priority:low` - Nice-to-have, can wait

If no priority label exists, issues are sorted by creation date (oldest first).

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
