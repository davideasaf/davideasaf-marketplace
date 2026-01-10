# David's Marketplace - Development Guidelines

## Versioning (SEMVER)

**Every change to a plugin MUST include a version bump** in the plugin's `.claude-plugin/plugin.json`.

### Version Format: MAJOR.MINOR.PATCH

| Bump | When to Use | Examples |
|------|-------------|----------|
| **PATCH** (1.4.0 → 1.4.1) | Bug fixes, typo corrections, minor doc updates, small utility additions | Fix script bug, correct SKILL.md typo, add helper script |
| **MINOR** (1.4.0 → 1.5.0) | New features, new skills, new scripts, backwards-compatible enhancements | Add new skill, add new mode to existing skill, add new script |
| **MAJOR** (1.4.0 → 2.0.0) | Breaking changes, renamed skills, removed features, restructured APIs | Rename skill, change script CLI interface, remove deprecated feature |

### Decision Flow

```
Is this a breaking change that could affect existing users?
├── YES → MAJOR bump
└── NO → Does this add new functionality?
    ├── YES → MINOR bump
    └── NO → PATCH bump
```

### Examples

```bash
# Added new create-gh-issue skill to github-dev-flow plugin
# This is new functionality → MINOR bump
"version": "1.0.0" → "version": "1.1.0"

# Fixed a bug in an existing script
# This is a fix → PATCH bump
"version": "1.1.0" → "version": "1.1.1"

# Renamed github-dev-flow skill to issue-workflow
# This breaks existing references → MAJOR bump
"version": "1.1.1" → "version": "2.0.0"
```

### Commit Message Format

Include the version bump in commit messages:

```
feat(plugin-name): description of change

- Bullet points of what changed
- Version bump: 1.4.0 → 1.5.0

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

---

## Contributing Guidelines

### Keep It Generic and Reusable

**All contributions to this repository should be generic and reusable when possible.**

### No User-Specific Content

Do NOT include:
- Personal email addresses or usernames
- Hardcoded file paths specific to your machine (e.g., `/Users/yourname/...`)
- Personal API keys, tokens, or credentials
- References to specific individuals by name
- Personal preferences or workflows that aren't universally applicable

### Use Environment Variables

Always use environment variables for configurable values:

```bash
# ✅ Correct - uses environment variable
export GITHUB_TOKEN="${GITHUB_TOKEN}"
export UNSPLASH_ACCESS_KEY="${UNSPLASH_ACCESS_KEY}"

# ❌ Wrong - hardcoded personal value
export GITHUB_TOKEN="ghp_abc123xyz"
```

### Path References

```bash
# ✅ Correct - relative or variable-based paths
reference/guide.md
${OUTPUT_DIR}/results.json
scripts/upload_media.py

# ❌ Wrong - absolute user-specific paths
/Users/dasaf/projects/output/results.json
~/.claude/skills/my-skill/script.py
```

Within plugins, use:
- **Relative paths** for intra-plugin references
- **`${CLAUDE_PLUGIN_ROOT}`** for hooks and MCP server paths
- **`Path(__file__).parent.resolve()`** for Python script-relative paths

### Before Committing

Run through this checklist:

- [ ] Version bumped in `.claude-plugin/plugin.json`
- [ ] No personal email addresses
- [ ] No hardcoded usernames
- [ ] No absolute paths to personal directories
- [ ] No API keys or tokens (use environment variables)
- [ ] No references to specific individuals by name
- [ ] Documentation is written for any user, not just yourself
- [ ] Commit message includes version bump info

### Why This Matters

This repository may be shared or published. User-specific values:
- Break for other users
- May expose sensitive information
- Make maintenance harder
- Reduce reusability

---

## Plugin Structure

Each plugin lives in its own directory with:
- `.claude-plugin/plugin.json` - Manifest file (includes version)
- `skills/` - Individual skill definitions (each with SKILL.md)
- `commands/` - Custom slash commands (optional)
- `local-mcp/` - MCP servers (optional)
- `hooks/` - Hook configurations (optional)

---

## Development Workflow

1. **Make changes** to plugin
2. **Test thoroughly** with multiple conversation styles
3. **Bump version** in `.claude-plugin/plugin.json`
4. **Update documentation** as needed
5. **Commit with proper message** including version bump
6. **Push to remote**

---

## Quality Standards

- ✅ **Progressive Disclosure** - Keep main docs concise, link to detailed references
- ✅ **Clear Descriptions** - Tell Claude WHEN to use your plugin/skill
- ✅ **Examples First** - Show usage before explaining internals
- ✅ **Test Thoroughly** - Try multiple conversation styles
- ✅ **Document Everything** - Future you will thank present you!

---

## Philosophy

This marketplace is built on three principles:

1. **🗣️ Natural Language First** - Talk to Claude like a human, not a CLI
2. **⚡ Speed Matters** - Caching, optimization, and smart defaults
3. **📖 Documentation as Love** - Clear guides make everyone's life better
