---
description: "Deliver an epic end-to-end — plan all remaining stories and delegate to @coder, @tester, @reviewer for each."
mode: "agent"
agent: "planner"
---

# Deliver Epic

Complete an entire epic from current state to Done, story by story, delegating to the right agent at each phase.

## Variables

- `epicFile` — path to the epic file (e.g., `docs/epics/007-markitdown-for-convert.md`)

## Phase 1: Assess Current State

1. Read the epic file at `${epicFile}`
2. Read `docs/specs/architecture.md` and `docs/specs/infrastructure.md` for context
3. Run `make test` to confirm the baseline passes
4. Identify all stories and their current status:
   - Which stories are already ✅?
   - Is any story partially complete (some acceptance criteria checked)?
   - Which stories remain?
5. Validate preconditions:
   - All prior ✅ stories are genuinely complete (acceptance criteria match code)
   - No broken or partially-updated stories
   - Flag any issues to the user before proceeding

## Phase 2: Build the Master Plan

1. For each remaining story (in epic order), produce:
   - A numbered task breakdown with specific file paths
   - Expected test coverage
   - Definition of Done checklist
2. Identify cross-story dependencies or shared changes
3. Estimate if any story is too large and should be split
4. Present the full plan and confirm with the user before proceeding

## Phase 3: Deliver Each Story

For each remaining story, execute this cycle in strict order:

### Step A — Implement (@coder)

Hand off to @coder with the task breakdown for this story.
- Implement all tasks following existing project patterns
- If the story involves infrastructure changes (Bicep modules, `azure.yaml`, deployment config), hand those tasks to @deployer instead
- Run `make test` after each significant change
- Do not proceed to testing until implementation is complete

### Step B — Test (@tester)

Hand off to @tester to validate the implementation.
- Write tests covering acceptance criteria, edge cases, and error paths
- Run the full test suite: `make test`
- Do not proceed until all tests pass

### Step B.1 — Diagnose Failures (@debugger)

If any tests fail or runtime errors occur during Step A or Step B:
- Hand off to @debugger with the full error traceback and context
- @debugger traces the root cause through code, config, and dependencies
- @debugger proposes the minimal fix and hands back to @coder to apply it
- Re-run `make test` to confirm the fix resolves the issue
- Repeat until all tests pass, then resume the normal flow

### Step C — Review (@reviewer)

Hand off to @reviewer for quality gate.
- Review all changed files against the review checklist (security, correctness, tests, style, docs)
- Produce a GO / NO-GO verdict
- If NO-GO: route blockers back to @coder (or @deployer for infra issues), then repeat Step C
- If GO: proceed to mark story complete

### Step D — Deploy Infrastructure (@deployer)

If the story introduced or modified infrastructure:
- Hand off to @deployer to validate changes:
  - Verify Bicep compiles: `az bicep build --file infra/main.bicep`
  - Cross-reference `infra/modules/` against `docs/specs/infrastructure.md`
  - Validate `azure.yaml` service definitions match project structure
- If no infrastructure changes in this story, skip to Step E

### Step E — Update Epic (@planner)

Update the epic doc for this story:
- Check off all acceptance criteria (`- [x]`)
- Update implementation scope table rows with ✅
- Check off Definition of Done items
- Mark the story title with ✅

**Do not start the next story until Step E is complete.**

## Phase 4: Finalize the Epic

1. Run `make test` one final time to confirm full suite passes
2. Verify every story in the epic is marked ✅
3. Update the epic header: set Status to **Done** and update the date
4. Hand off to @deployer for final deployment validation:
   - Run `/deploy-check` to verify full deployment readiness
   - Validate all infrastructure changes compile and are consistent
   - If the epic introduced new services or endpoints, confirm `azure.yaml` and Bicep are updated
   - If deployment is required, @deployer executes `make azure-up` and `make azure-test`
5. If any deployment issues arise, hand off to @debugger for diagnosis
6. Summarize what was delivered:
   - Stories completed in this session
   - Files created or modified
   - Test coverage added
   - Infrastructure changes (if any)
   - Deployment status (deployed / ready to deploy / not applicable)
   - Any known follow-ups or tech debt

## Rules

- **Strict story ordering** — never start story N+1 until story N is fully ✅
- **No skipped validation** — every story must pass @tester and @reviewer before marking done
- **Epic doc is the source of truth** — update it at every step; it drives visibility
- **Stop on blockers** — if @reviewer gives NO-GO twice on the same issue, escalate to the user
- **Minimal changes** — implement exactly what each story requires, nothing more
- **No secrets in code** — use `DefaultAzureCredential` and environment variables everywhere
