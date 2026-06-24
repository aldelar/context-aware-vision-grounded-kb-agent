---
name: github-issues
description: |
  Create, update, and manage GitHub issues using the GitHub MCP server. Use when:
  - Creating bug reports, feature requests, deferred follow-ups, or task issues
  - Updating existing issues (labels, assignees, state)
  - Searching or filtering issues
  - Managing issue types, sub-issues, or dependencies
---

# GitHub Issues Management

Manage GitHub issues through the repository's GitHub MCP server (`github` in `.vscode/mcp.json`). **Never use `gh`, `gh api`, or raw GitHub REST calls from the shell for issue operations.**

If the GitHub MCP server is unavailable, draft the issue title/body and report that filing or updating is blocked by the missing MCP server. Do not fall back to the GitHub CLI.

## Available MCP Operations

Use the GitHub MCP server for both reads and writes:

| Operation | Purpose |
|-----------|---------|
| Read issue | Read issue details, sub-issues, comments, labels, assignees |
| List issues | List and filter repository issues by state, labels, assignees, date |
| Search issues | Search issues across repositories using GitHub search syntax |
| Create issue | File a new bug, feature request, deferred follow-up, or task |
| Update issue | Change title, body, state, labels, assignees, milestone, or issue type |
| Add comment | Add a comment to an existing issue |
| Manage sub-issues | Add, remove, or reorder sub-issues when supported by the server |

## Workflow

1. **Determine action**: Create, update, or query?
2. **Gather context**: Get repo info, existing labels, issue types, milestones, and related issues if needed.
3. **Structure content**: Use an appropriate template below or `.github/GITHUB_ISSUE_TEMPLATES/`.
4. **Execute through MCP**: Use GitHub MCP server tools for all issue reads/writes.
5. **Confirm**: Report the issue URL to the user or caller.

## Creating Issues

Prefer issue types over labels for categorization when issue types are available. Use labels for routing, priority, or cross-cutting tags.

### Optional Fields

- Issue type: Bug, Feature, Task, Epic, or the repository-supported equivalent
- Labels: `bug`, `enhancement`, `documentation`, `high-priority`, or repository-specific labels
- Assignees
- Milestone
- Parent / sub-issue relationship, when supported

### Title Guidelines

- Be specific and actionable
- Keep under 72 characters
- Do not add redundant prefixes like `[Bug]` when issue type is set
- Use the Archivist's `[Epic <NN>]` or `[<area>]` title format for deferred follow-ups from an Agents Workbench

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

Fetch the current issue before updating it so unchanged fields are preserved. Only mutate the requested fields: title, body, state, labels, assignees, milestone, issue type, comments, or sub-issues.

## Commit-Pinned References

When filing durable follow-ups, especially from the Archivist, cite source references so they survive later tree changes:

1. Capture the current commit with `git rev-parse HEAD`.
2. Prefer a GitHub permalink with the commit SHA and line range.
3. Pair the permalink with a copy-pasteable search command when the code may move.
4. Avoid bare local line numbers without a commit-pinned link.

## Tips

- Always confirm the repository context before creating issues.
- Ask for missing critical information rather than guessing.
- Link related issues: `Related to #123`.
- If MCP permissions are missing, return the exact title/body that would have been filed and identify the blocked operation.
