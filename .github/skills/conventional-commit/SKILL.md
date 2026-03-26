---
name: conventional-commit
description: |
  Prompt and workflow for generating conventional commit messages. Use when:
  - Committing changes with standardized messages
  - Following the Conventional Commits specification
  - Generating commit messages from staged changes
---

# Conventional Commit Workflow

## Steps

1. Run `git status` to review changed files
2. Run `git diff` or `git diff --cached` to inspect changes
3. Stage changes with `git add <file>`
4. Construct the commit message using the format below
5. Run `git commit -m "type(scope): description"`

## Message Format

```
type(scope): description

[optional body]

[optional footer]
```

### Types

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

### Scope

Optional but recommended. Use the service or module name:
- `agent`, `functions`, `web-app`, `infra`, `docs`, `scripts`

### Examples

```
feat(agent): add memory compaction for long conversations
fix(functions): handle empty HTML in fn-convert
docs(epics): mark story 3 complete in epic 011
refactor(web-app): extract sidebar component
ci: add pre-commit hook for linting
chore: update uv lockfile
feat!: migrate to Responses API (BREAKING CHANGE: old chat endpoint removed)
```

### Rules

- **Type**: Must be one of the allowed types
- **Description**: Required, imperative mood ("add", not "added")
- **Body**: Optional, additional context
- **Footer**: Use for breaking changes (`BREAKING CHANGE: ...`) or issue references (`Closes #123`)
- Keep description under 72 characters
