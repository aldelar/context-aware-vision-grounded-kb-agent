---
description: "Implement a story end-to-end — delegate to @coder, @tester, and @reviewer for each phase."
mode: "agent"
agent: "planner"
---

# Implement Story

Deliver a single story from task breakdown to Done, delegating to the right agent at each phase.

## Variables

- `epicFile` — path to the epic file (e.g., `docs/epics/008-per-function-container-split.md`)
- `storyNumber` — the story number to implement (e.g., `3`)

## Delegation Mechanism

You are the **orchestrator**. You do NOT implement code, write tests, or review code yourself.

For every step that names an agent (@coder, @tester, @reviewer, @deployer, @debugger), delegate by calling `runSubagent` with:
- `agentName` — the agent name (e.g., `"coder"`, `"tester"`, `"reviewer"`)
- `prompt` — a self-contained task description with all context the agent needs

Each prompt must be **self-contained** — the subagent has no access to this conversation. Include:
- The story title, acceptance criteria, and Definition of Done
- Specific file paths to read and modify
- Any relevant output from prior agents (e.g., coder's summary for the tester)
- The instruction: "Return a structured summary with: Status (success/partial/failed), Files created, Files modified, Tests run (pass/fail count), Issues found, Notes for next agent"

## Step 1 — Setup

1. Read the epic file at `${epicFile}` and locate Story `${storyNumber}`
2. Read `docs/specs/architecture.md` and `docs/specs/infrastructure.md` for context
3. Validate preconditions:
   - All prior stories are marked ✅
   - No partially-updated stories exist
4. Run `make test` to confirm the baseline passes

## Step 2 — Implement (@coder)

Delegate to @coder via `runSubagent(agentName="coder")` with the task breakdown for this story.
- Implement all deliverables following existing project patterns
- Write basic happy-path tests to validate the implementation works
- If the story involves infrastructure changes (Bicep modules, `azure.yaml`), hand those tasks to @deployer instead
- @coder should run `make test` after each significant change and debug failures in-context using the debugging skill
- Do not proceed until implementation is complete and coder reports success

## Step 3 — Test (@tester)

Delegate to @tester via `runSubagent(agentName="tester")` to write comprehensive tests.
Include the coder's summary in the prompt so the tester knows what changed.
- Build on @coder's happy-path tests — add edge cases, error paths, boundary conditions, and parametrised variants
- Run the full test suite: `make test`
- @tester debugs any failures in-context using the debugging skill
- Do not proceed until all tests pass

### Step 3.1 — Escalate Persistent Failures (@debugger)

If @coder or @tester cannot resolve a failure after one debugging pass:
- Delegate to @debugger via `runSubagent(agentName="debugger")` with: the error traceback, what was investigated, the hypothesis, and what was tried
- @debugger handles complex multi-system issues (cross-service errors, config/RBAC problems, deployment failures)
- Delegate back to @coder with the debugger's diagnosis to apply the fix
- Re-run `make test` to confirm
- Repeat until all tests pass, then resume the normal flow

## Step 4 — Review (@reviewer)

Delegate to @reviewer via `runSubagent(agentName="reviewer")` for quality gate.
Include both the coder's and tester's summaries in the prompt.
- Review all changed files against the review checklist (security, correctness, tests, style, docs)
- Produce a GO / NO-GO verdict
- If NO-GO: route blockers back to @coder (or @deployer for infra), then repeat Step 4
- If GO: proceed to mark story complete

## Step 5 — Deploy Validation (@deployer)

If the story introduced or modified infrastructure:
- Delegate to @deployer via `runSubagent(agentName="deployer")` to validate:
  - `az bicep build --file infra/main.bicep` succeeds
  - `azure.yaml` service definitions match project structure
- If no infrastructure changes, skip to Step 6

## Step 6 — Update Epic

Update the epic doc directly:
- Check off all acceptance criteria (`- [x]`)
- Update implementation scope table rows with ✅
- Check off Definition of Done items
- Add ✅ to the story title if all criteria are met
- If all stories are done, set the epic `Status:` to `Done`

## Rules

- **Never skip the test step** — even if the coder wrote tests inline, @tester validates independently
- **Never skip the review step** — @reviewer catches issues the coder and tester may miss
- **Do not proceed past a failing step** — fix issues before moving forward
- **Report after each agent call** — summarize what the agent returned and what happens next
