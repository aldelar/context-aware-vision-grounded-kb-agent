---
description: 'Merge the open PR for the current branch and switch to main'
mode: 'agent'
---

# Merge Pull Request

Merge the open pull request for the current branch into `main`, then switch local branch to `main` and pull.

## Steps

1. Run `git branch --show-current` to get the current branch name. If on `main`, stop and tell the user.
2. Extract the repository owner/repo from `git remote get-url origin`.
3. Use the GitHub MCP tools to find the open PR for the current branch targeting `main`.
   - If no open PR exists, stop and tell the user.
4. Check the PR is mergeable (no conflicts). If there are conflicts, stop and tell the user to resolve them first.
5. Merge the PR using the GitHub MCP tool with merge method `squash`.
6. Run `git checkout main && git pull` to switch to main and pull the merged changes.
7. Output exactly:

```
PR #<number> merged. Now on main (up to date).
```
