---
description: "Pre-commit quality check — review changes, run tests, validate docs."
agent: "reviewer"
---

# Pre-Commit Check

Validate all changes before committing.

## Steps

1. Identify changed files (ask the user or use git status)
2. Run `make test` — all unit/endpoint tests must pass
3. Review each changed file:
   - **Security:** No hardcoded secrets, proper auth, input validation
   - **Correctness:** Code does what it should, error handling at boundaries
   - **Tests:** New logic has tests, existing tests still pass
   - **Style:** Follows project patterns, proper imports, no print statements
   - **Docs:** Epic doc updated if story-related, infrastructure doc if resources changed
4. Check for untracked issues:
   - `# TODO` or `# HACK` comments without tracking
   - Missing `.env.sample` updates for new variables
   - Broken Makefile targets for modified paths
5. Produce a report:
   - 🔴 **Blockers** (must fix)
   - 🟡 **Warnings** (should fix)
   - 🟢 **Notes** (observations)
   - **Verdict: GO / NO-GO**
