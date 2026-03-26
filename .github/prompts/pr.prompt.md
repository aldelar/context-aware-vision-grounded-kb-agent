---
description: 'Create a pull request from the current branch to main'
mode: 'agent'
---

# Create Pull Request

Create a GitHub pull request from the current branch to `main`.

## Steps

1. Run `git branch --show-current` to get the current branch name. If on `main`, stop and tell the user.
2. Run `git status` to check for uncommitted changes. If there are any, stop and tell the user to commit first.
3. Run `git log main..HEAD --oneline` to get the list of commits. If there are no commits ahead of main, stop and tell the user.
4. Run `git diff main..HEAD --stat` to get the changed files summary.
5. Extract the repository owner/repo from `git remote get-url origin`.
6. Compose a clear PR title using conventional commit format based on the changes.
7. Compose a PR body with:
   - A **Summary** section describing what changed and why
   - A **Changes** section listing the key modifications
8. Create the PR using the GitHub MCP tool targeting `main` as the base branch.
9. Output exactly one line in this format:

```
PR created: #<number> — <title> (<clickable URL>)
```
