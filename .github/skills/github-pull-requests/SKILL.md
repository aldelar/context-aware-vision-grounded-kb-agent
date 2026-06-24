---
name: github-pull-requests
description: |
  Create, update, review, and merge GitHub pull requests using the GitHub MCP server. Use when:
  - Creating a PR for the current branch or lane branch
  - Finding the open PR for a branch
  - Updating, merging, or checking PR status
  - Driving PR lifecycle from a TechLead lane
---

# GitHub Pull Request Lifecycle

Drive pull request lifecycle through the repository's GitHub MCP server (`github` in `.vscode/mcp.json`). Use local `git` only to inspect or update the working copy: branch name, status, logs, diffs, checkout, pull, and push. **Never use `gh` or `gh api` for PR operations.**

If the GitHub MCP server is unavailable, prepare the PR title/body or merge report and stop with a clear blocker. Do not fall back to the GitHub CLI.

## Ownership Model

- **TechnicalPM** is the usual user-facing entry point. When asked to create, update, or merge a PR, it should delegate a small closure lane to a **TechLead**.
- **TechLead** owns PR lifecycle for its lane after Implementers have returned verified work and Reviewers have returned the needed verdicts.
- **Implementer** may commit and push branch changes when assigned, but does not own opening or merging PRs unless explicitly directed for a small solo task.
- **Archivist** files durable follow-up issues, not PRs.

## Create PR Workflow

1. Run `git branch --show-current`. If on `main`, stop and report that a feature branch is required.
2. Run `git status --porcelain=v1`. If there are uncommitted changes, stop and report that the branch must be committed first.
3. Run `git log <base>..HEAD --oneline`. If there are no commits ahead of the base, stop and report that there is nothing to PR.
4. Run `git diff <base>..HEAD --stat` to summarize changed files.
5. Extract owner/repo from `git remote get-url origin`.
6. Compose a conventional-commit style PR title from the actual commits and diff.
7. Compose a PR body with:
   - **Summary** — what changed and why
   - **Changes** — key modifications
   - **Validation** — checks run by Implementers / this lane
8. Create the PR through the GitHub MCP server targeting the base branch.
9. Return exactly:

```text
PR created: #<number> - <title> (<clickable URL>)
```

## Merge PR Workflow

1. Run `git branch --show-current` to identify the branch.
2. Extract owner/repo from `git remote get-url origin`.
3. Use GitHub MCP tools to find the open PR for the current branch and target base.
4. Confirm the PR is mergeable and required checks/reviews are satisfied. If conflicts or failing required checks exist, stop and report the blocker.
5. Merge through the GitHub MCP server using the repository's requested merge method; default to squash when no method is specified.
6. Run `git checkout <base> && git pull` to update the local working branch after merge.
7. Return exactly:

```text
PR #<number> merged. Now on <base> (up to date).
```

## Base Branch Selection

- Default base is `main` for normal user-invoked PRs.
- In an Agents Workbench, use the branch named in the TechnicalPM assignment or lane charter.
- When worktree-per-lane is enabled, a TechLead should PR/merge its lane branch into the TechnicalPM's current working branch, not blindly into `main`.
- If the base branch is ambiguous, ask the TechnicalPM or user before creating or merging.

## Safety Rules

- Do not create a PR from a dirty working tree.
- Do not merge without explicit user/TechnicalPM approval unless the assignment explicitly grants auto-merge authority.
- Do not bypass failing required checks, unresolved review findings, or merge conflicts.
- Do not use `gh`, `gh api`, or raw GitHub REST calls from the shell when MCP tools are available.
- Do not include secrets, local paths outside the repo, or workbench-only scratch content in a PR body.
