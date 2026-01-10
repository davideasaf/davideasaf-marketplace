# Issue Templates

Templates for creating well-documented GitHub issues.

## Bug Report Template

```markdown
## Description

[Clear, concise description of the bug]

## Steps to Reproduce

1. [First step]
2. [Second step]
3. [Third step]
4. [Observe the issue]

## Expected Behavior

[What should happen when following the steps above]

## Actual Behavior

[What actually happens - be specific about error messages, visual issues, etc.]

## Evidence

[Embed screenshots or GIFs captured during reproduction]

![screenshot](url)

## Environment

- **OS:** [e.g., macOS 14.2, Windows 11, Ubuntu 22.04]
- **Browser:** [e.g., Chrome 120, Firefox 121, Safari 17]
- **App Version:** [e.g., v1.2.3, commit abc1234]
- **Device:** [e.g., Desktop, iPhone 15, Pixel 8]

## Reproduction Status

- [ ] ✅ Reproduced by Claude
- [ ] ❌ Could not reproduce
- [ ] ⚠️ Intermittent (reproduced X/Y attempts)

## Additional Context

[Any other information that might be helpful - logs, related issues, recent changes, etc.]
```

## Feature Request Template

```markdown
## Summary

[One-line summary of the feature]

## Description

[Detailed description of the proposed feature. What does it do? How does it work?]

## Use Case

[Why is this feature needed? What problem does it solve? Who benefits?]

**User Story:**
> As a [type of user], I want [goal] so that [benefit].

## Proposed Solution

[How could this feature be implemented? Include UI mockups, API designs, or workflow descriptions if helpful.]

## Fit Assessment

Evaluation of how this feature fits with the existing application:

| Criteria | Assessment | Notes |
|----------|------------|-------|
| **UX Consistency** | 🟢 Good / 🟡 Moderate / 🔴 Concern | [Does it match existing patterns?] |
| **Technical Feasibility** | 🟢 Easy / 🟡 Moderate / 🔴 Complex | [Implementation complexity] |
| **Scope** | 🟢 Contained / 🟡 Medium / 🔴 Large | [Risk of scope creep] |
| **Roadmap Alignment** | 🟢 Aligned / 🟡 Neutral / 🔴 Off-track | [Fits with project direction?] |

## Alternatives Considered

[What other solutions were considered? Why is this approach preferred?]

1. **Alternative A:** [Description] - [Why not chosen]
2. **Alternative B:** [Description] - [Why not chosen]

## Suggestions & Enhancements

[Claude's suggestions to improve or enhance the original request]

- [Suggestion 1]
- [Suggestion 2]

## Dependencies

[Does this feature depend on other work? What needs to happen first?]

- [ ] [Dependency 1]
- [ ] [Dependency 2]
```

## Quick Bug Template (Minimal)

For simple, straightforward bugs:

```markdown
## Bug

[Description of the bug]

## Reproduce

1. [Steps]

## Expected vs Actual

- **Expected:** [what should happen]
- **Actual:** [what happens]

## Evidence

![screenshot](url)
```

## Quick Feature Template (Minimal)

For simple feature requests:

```markdown
## Feature

[Description of the feature]

## Why

[Why this feature is needed]

## Proposed

[How it could work]
```

## Template Selection Guide

| Scenario | Template |
|----------|----------|
| Complex bug with multiple steps | Full Bug Report |
| Simple visual bug | Quick Bug |
| New major feature | Full Feature Request |
| Small enhancement | Quick Feature |
| API/backend bug | Full Bug + logs |
| UI/UX bug | Full Bug + GIF |
