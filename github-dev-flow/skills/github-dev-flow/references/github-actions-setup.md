# GitHub Actions Setup for @claude Integration

## Overview

This guide explains how to set up GitHub Actions to respond to @claude mentions in issues and pull requests. When triggered, Claude can use the github-dev-flow skill to manage the development workflow autonomously.

## Setup Steps

### 1. Copy the Workflow Template

Copy the workflow template to your repository:

```bash
mkdir -p .github/workflows
cp ~/.claude/skills/github-dev-flow/assets/github-actions/claude-dev-flow.yml .github/workflows/
```

### 2. Add Required Secrets

Go to your repository's **Settings > Secrets and variables > Actions** and add:

| Secret | Description |
|--------|-------------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Your Claude Code OAuth token |

To get your OAuth token:
1. Run `claude auth status` to check your current authentication
2. Or generate a new token at https://console.anthropic.com/

### 3. Grant Project Access

The GitHub CLI needs project access for board operations:

```bash
gh auth refresh -s project
```

This adds the `project` scope to your authentication.

### 4. Configure Repository Settings

Ensure your repository has:
- **Issues enabled**: Settings > General > Features > Issues
- **Projects enabled**: Settings > General > Features > Projects
- **Actions enabled**: Settings > Actions > General > Allow all actions

## Workflow Triggers

The workflow responds to @claude mentions in:

| Event | Trigger |
|-------|---------|
| Issue comment | `@claude` in comment body |
| Issue creation | `@claude` in issue body or title |
| PR review comment | `@claude` in review comment |
| PR review | `@claude` in review body |
| Issue assignment | When issue is assigned (optional) |

## Permissions Required

The workflow needs these permissions:

```yaml
permissions:
  contents: write      # Create branches, commit code
  pull-requests: write # Create/update PRs
  issues: write        # Comment on issues, update project board
  id-token: write      # OIDC authentication
  actions: read        # Read CI results
```

## Example Usage

### In an Issue Comment

```markdown
@claude Please pick up this issue and create an implementation plan.
```

### In a PR Review

```markdown
@claude Please address the feedback in this review.
```

### Assigning Work

```markdown
@claude Tackle the highest priority issue in milestone "v1.0"
```

## Customization

### Restricting Who Can Invoke Claude

Add a condition to limit who can trigger the workflow:

```yaml
if: |
  github.event.comment.author_association == 'OWNER' ||
  github.event.comment.author_association == 'MEMBER' ||
  github.event.comment.author_association == 'COLLABORATOR'
```

### Adding Custom Environment Variables

```yaml
env:
  MY_API_KEY: ${{ secrets.MY_API_KEY }}
```

### Limiting Allowed Tools

Restrict which tools Claude can use:

```yaml
with:
  claude_args: '--allowed-tools Bash(git:*,gh:*) Edit Write Read Glob Grep'
```

## Troubleshooting

### "Permission denied" Errors

Ensure the workflow has correct permissions and secrets are set.

### "Project scope required" Errors

Run `gh auth refresh -s project` to add project scope.

### Workflow Not Triggering

- Check that the workflow file is in `.github/workflows/`
- Verify the trigger conditions in the YAML
- Check repository Actions settings are enabled

### Claude Not Responding

- Verify `CLAUDE_CODE_OAUTH_TOKEN` secret is set
- Check Actions logs for error messages
- Ensure @claude mention is exactly `@claude` (case-sensitive)

## Security Considerations

1. **Limit triggering users**: Restrict who can invoke @claude
2. **Review generated code**: Always review PRs before merging
3. **Protect main branch**: Require PR reviews before merge
4. **Monitor usage**: Watch Actions minutes and API usage

## Cost Management

- GitHub Actions minutes: ~2-5 minutes per invocation
- Claude API calls: Depends on complexity of task
- Consider setting up spending alerts in GitHub and Anthropic console
