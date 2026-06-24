---
name: conventional-commit
description: |
  Workflow for generating conventional commit messages, committing, and pushing local changes. Use when:
  - Committing changes with standardized messages
  - Following the Conventional Commits specification
  - Generating commit messages from staged changes
  - Staging, committing, or pushing the current branch
---

# Conventional Commit And Push Workflow

## Steps

1. Run `git status --short` to list modified, added, and deleted files. If the working tree is clean, stop and report there is nothing to commit.
2. Run `git diff --stat` and `git diff --cached --stat` to understand the scope of unstaged and staged changes.
3. Run `git diff` and `git diff --cached` to inspect the actual diffs. For large diffs, inspect per file.
4. Determine the conventional commit type and optional scope from the changed files.
5. Stage all intended changes with `git add -A`, unless the assignment explicitly asks for a partial commit.
6. Commit with `git commit -m "type(scope): description"` (add a second `-m` body for non-trivial changes).
7. Push with `git push`. If no upstream is set, run `git push -u origin $(git branch --show-current)`.
8. Return exactly:

```text
Committed and pushed: <short-sha> - <subject line>
```

## Ownership

- **Implementer** owns committing and pushing branch changes for an assigned slice when asked.
- **TechLead** owns creating and merging pull requests for a lane through the `github-pull-requests` skill.
- Do not use GitHub MCP for local commits; use local `git` commands.

## Message Format

```text
type(scope): description

[optional body]

[optional footer]
```

## Types

| Type | Use For |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no code change |
| `refactor` | Code change that neither fixes nor adds |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `build` | Build system or dependencies |
| `ci` | CI configuration |
| `chore` | Maintenance tasks |
| `revert` | Reverting a previous commit |

## Scope

Optional but recommended. Use the service or module name:
- `agent`, `functions`, `convert`, `index`, `web-app`, `mcp`, `infra`, `docs`, `scripts`, `ci`

## Examples

```text
feat(agent): add memory compaction for long conversations
fix(functions): handle empty HTML in fn-convert
docs(epics): mark story 3 complete in epic 011
refactor(web-app): extract sidebar component
ci: add pre-commit hook for linting
chore: update uv lockfile
feat!: migrate to Responses API
```

## Rules

- **Type**: Must be one of the allowed types.
- **Description**: Required, imperative mood ("add", not "added").
- **Body**: Optional, additional context.
- **Footer**: Use for breaking changes (`BREAKING CHANGE: ...`) or issue references (`Closes #123`).
- Keep description under 72 characters.
- Do not include secrets, local-only paths outside the repo, or `.agents-workbench/` scratch content in commit messages.
