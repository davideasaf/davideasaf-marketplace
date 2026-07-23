---
name: fable-advisor
description: Use when Codex faces a costly-to-reverse decision, conflicting evidence, repeated failed attempts, no dominant approach, a complex final review, or an explicit request to consult Fable or an advisor.
---

# Fable Advisor

Cursor-hosted Fable 5 is an on-demand strategic advisor; Codex remains the executor and final decision-maker.

## Mandatory Invocation Contract

If this skill applies, read this contract before responding. Never claim to use the skill while improvising its command.

Use this command exactly; the only permitted conditional additions are `--with-mcps` and `--resume <explicit-session-id>` as defined below.

```bash
${CLAUDE_PLUGIN_ROOT}/skills/fable-advisor/scripts/advise.py --workspace <active-workspace-or-worktree> -
```

Every stdin brief uses these exact headings in this exact order:

```text
Objective
Hard constraints
Evidence gathered
Current hypothesis or plan
Known uncertainty
Decision requested
```

Do not substitute `fable`, `ask-fable`, `ask-cursor`, bare `agent`, other flags, or renamed headings.

## When to Consult

After enough read-only orientation to assemble evidence, consult before committing to a consequential approach when both apply:

1. The decision is costly to reverse, carries material architecture, migration, security, or data risk, or needs complex final independent review.
2. Genuine uncertainty remains: conflicting evidence, two failed attempts, no dominant option, or a contemplated change of approach.

Always consult when explicitly asked to ask Fable or an advisor. Do not consult for simple lookups, arithmetic, deterministic trivial edits, routine commands, obvious next actions, or uncertainty resolvable by one direct measurement.

Use at most three calls per task. Repeat only with new evidence or a materially changed question. Resume an explicit session only for a same-problem follow-up; start unrelated topics fresh.

## Brief and Call Policy

Keep the brief ideally 150–400 words. Prefer exact errors, paths, commands, and source observations over conclusions. Request a verdict, overlooked risks, next actions, and evidence that would change the recommendation.

Always resolve and pass the active workspace or worktree actually in use. Add `--with-mcps` only when analysis needs trusted configured connectors: the flag auto-approves configured MCP tools. Read-only behavior is a prompt contract, not a tool-level guarantee, so never enable untrusted or irrelevant connectors. Add `--resume <explicit-session-id>` only for a same-problem follow-up.

## Evaluate and Report

If evidence conflicts with advice, do not silently switch. Make at most one reconciliation call presenting the conflict, then decide from evidence. On timeout, missing model, invalid output, missing or blank session ID, or other failure, continue with Codex’s best judgment and disclose the failed consultation; it never blocks work. A successful consultation always returns a nonblank session ID in metadata.

Give advice serious weight, but reproducible primary-source evidence and empirical failures outrank it. When the consultation matters to the user, attribute it as **Fable 5 1M Thinking (via Cursor)** and present the advice, Codex’s evaluation, and concise metadata (workspace, model, required session ID on success, MCP use, and outcome).

## Quick Reference

| Situation | Action |
| --- | --- |
| Consequential uncertainty remains after orientation | Send the six-section brief before committing. |
| Explicit request for Fable | Consult, even if the risk threshold is otherwise unclear. |
| Same problem, new evidence or changed question | A follow-up may resume its explicit session ID. |
| Advisor contradicts reproducible evidence | Reconcile once if useful; primary evidence decides. |
| Trivial or directly measurable work | Proceed without consultation. |
| Advisor failure | Continue, disclose failure, and do not retry blindly. |

## Common Mistakes

- Calling before collecting read-only evidence, then asking a vague question.
- Treating advice as authority over a deterministic trace or empirical failure.
- Repeating the same prompt without new evidence, or using a prior session for an unrelated topic.
- Enabling MCPs for untrusted or irrelevant connectors, or mistaking the prompt’s read-only contract for tool-level enforcement.
- Omitting the exact six brief sections or failing to disclose a material consultation.
