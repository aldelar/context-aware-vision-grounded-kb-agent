---
description: 'Stage, commit, and push changes with an auto-generated conventional commit message'
agent: 'Implementer'
---

# Commit & Push

Analyse the current working-tree changes, compose a conventional-commit message, commit, and push to the remote.

## Steps

1. Run `git status --short` to list modified, added, and deleted files. If the working tree is clean, stop and tell the user there is nothing to commit.
2. Run `git diff --stat` (unstaged) and `git diff --cached --stat` (staged) to understand the scope of changes.
3. Run `git diff` and `git diff --cached` to read the actual diffs. For large diffs, use `git diff -- <file>` per file to stay within context limits.
4. Determine the conventional commit **type** from the changes:
   - `feat` — new feature or user-facing behavior
   - `fix` — bug fix
   - `refactor` — code restructuring with no behavior change
   - `docs` — documentation only
   - `test` — adding or updating tests
   - `chore` — build, CI, tooling, dependency updates
   - `style` — formatting, linting, whitespace
   - `perf` — performance improvement
5. Determine an optional **scope** from the primary area of change. Prefer one of this project's areas: `agent`, `functions`, `convert`, `index`, `web-app`, `mcp`, `infra`, `docs`, `scripts`, `ci`.
6. Write a concise **subject line** (imperative mood, lowercase, no trailing period, ≤72 chars).
7. If the change is non-trivial, write a short **body** explaining *what* and *why* (wrap at 72 chars).
8. Stage all changes: `git add -A`.
9. Commit with the approved message: `git commit -m "<message>"` (use `-m` for subject + `-m` for body if a body exists).
10. Push to the current branch's upstream: `git push`. If no upstream is set, run `git push -u origin $(git branch --show-current)`.
11. Output exactly:

```
Committed and pushed: <short-sha> — <subject line>
```
