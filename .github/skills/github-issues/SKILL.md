---
name: github-issues
description: |
  Create, update, and manage GitHub issues using MCP tools. Use when:
  - Creating bug reports, feature requests, or task issues
  - Updating existing issues (labels, assignees, state)
  - Searching or filtering issues
  - Managing issue types, sub-issues, or dependencies
---

# GitHub Issues Management

Manage GitHub issues using MCP tools for reads and `gh api` for writes.

## Available Tools

### MCP Tools (read operations)

| Tool | Purpose |
|------|---------|
| `mcp_github_issue_read` | Read issue details, sub-issues, comments, labels |
| `mcp_github_list_issues` | List and filter repository issues by state, labels, date |
| `mcp_github_search_issues` | Search issues across repos using GitHub search syntax |

### CLI / REST API (write operations)

MCP does not currently support creating or updating issues. Use `gh api`:

| Operation | Command |
|-----------|---------|
| Create issue | `gh api repos/{owner}/{repo}/issues -X POST -f title=... -f body=...` |
| Update issue | `gh api repos/{owner}/{repo}/issues/{number} -X PATCH -f title=...` |
| Add comment | `gh api repos/{owner}/{repo}/issues/{number}/comments -X POST -f body=...` |
| Close issue | `gh api repos/{owner}/{repo}/issues/{number} -X PATCH -f state=closed` |
| Set issue type | Include `-f type=Bug` in the create call (REST API only) |

## Workflow

1. **Determine action**: Create, update, or query?
2. **Gather context**: Get repo info, existing labels, milestones if needed
3. **Structure content**: Use appropriate template below
4. **Execute**: Use MCP tools for reads, `gh api` for writes
5. **Confirm**: Report the issue URL to user

## Creating Issues

```bash
gh api repos/{owner}/{repo}/issues \
  -X POST \
  -f title="Issue title" \
  -f body="Issue body in markdown" \
  -f type="Bug" \
  --jq '{number, html_url}'
```

### Optional Parameters

```bash
-f type="Bug"                    # Issue type (Bug, Feature, Task, Epic)
-f labels[]="bug"                # Labels (repeat for multiple)
-f assignees[]="username"        # Assignees
-f milestone=1                   # Milestone number
```

**Prefer issue types over labels for categorization.** When issue types are available, use the `type` parameter instead of labels like `bug` or `enhancement`.

### Title Guidelines

- Be specific and actionable
- Keep under 72 characters
- Don't add redundant prefixes like `[Bug]` when issue type is set

### Body Templates

**Bug Report:**
```markdown
## Description
[What's broken]

## Steps to Reproduce
1. ...

## Expected Behavior
[What should happen]

## Actual Behavior
[What happens instead]
```

**Feature Request:**
```markdown
## Summary
[What and why]

## Motivation
[Why this matters]

## Proposed Solution
[How to implement]

## Acceptance Criteria
- [ ] ...
```

**Task:**
```markdown
## Description
[What needs to be done]

## Deliverables
- [ ] ...

## Context
[Background information]
```

## Updating Issues

```bash
gh api repos/{owner}/{repo}/issues/{number} \
  -X PATCH \
  -f state=closed \
  --jq '{number, html_url}'
```

Only include fields you want to change: `title`, `body`, `state`, `labels`, `assignees`, `milestone`.

## Common Labels

| Label | Use For |
|-------|---------|
| `bug` | Something isn't working |
| `enhancement` | New feature or improvement |
| `documentation` | Documentation updates |
| `high-priority` | Urgent issues |

## Tips

- Always confirm the repository context before creating issues
- Ask for missing critical information rather than guessing
- Link related issues: `Related to #123`
- For updates, fetch current issue first to preserve unchanged fields
