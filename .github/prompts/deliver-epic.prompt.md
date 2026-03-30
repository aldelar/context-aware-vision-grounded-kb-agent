---
description: "Deliver an epic end-to-end — plan all remaining stories, then hand off to @implementer and @reviewer for each."
agent: "Planner"
---

# Deliver Epic

Complete an entire epic from current state to Done, story by story, using the handoff workflow.

## Variables

- `epicFile` — path to the epic file (e.g., `docs/epics/007-markitdown-for-convert.md`)

## Phase 1: Assess Current State

1. **Create a shared scratchpad** — `shared-scratchpads/{epic}-delivery.md` (MANDATORY first action)
2. Read the epic file at `${epicFile}`
3. Read `docs/specs/architecture.md` and `docs/specs/infrastructure.md` for context
4. Identify all stories and their current status:
   - Which stories are already ✅?
   - Is any story partially complete (some acceptance criteria checked)?
   - Which stories remain?
5. Validate preconditions:
   - All prior ✅ stories are genuinely complete (acceptance criteria match code)
   - No broken or partially-updated stories
   - Flag any issues to the user before proceeding
6. **Append findings to the scratchpad**

## Phase 2: Build the Master Plan

1. For each remaining story (in epic order), produce:
   - A numbered task breakdown with specific file paths
   - Expected test coverage
   - Definition of Done checklist
2. Identify cross-story dependencies or shared changes
3. Estimate if any story is too large and should be split
4. **Create TODOs** — one per implementation step across all stories
5. **Append the plan summary to the scratchpad**
6. Present the full plan and confirm with the user before proceeding

## Phase 3: Deliver Each Story

For each remaining story, execute this cycle:

### Step A — Hand off to Implementer

Use the **Start Implementation** handoff button to transfer to @implementer with the story plan.
The Implementer will:
- Read the shared scratchpad for full context
- Implement all tasks following existing project patterns
- Write tests alongside the code (unit + edge cases + error paths)
- Handle infrastructure changes (Bicep, azure.yaml) if the story requires them
- Debug failures in-context using the `debugging` skill
- Update the epic doc with acceptance criteria, implementation scope, and DoD
- Append progress to the shared scratchpad
- Hand off to @reviewer when ready

### Step B — Review (handled by @reviewer)

The Implementer hands off to @reviewer via the **Request Review** button.
The Reviewer will:
- Check architecture compliance, security, tests, code quality, and epic doc status
- Produce a verdict: ✅ Approve / ⚠️ Approve with comments / ❌ Request changes
- If issues found: hand back to @implementer via **Quick Fix** or **Rework** button
- If fundamental issues: hand back to @planner via **Re-plan** button
- On final approval: append `IMPLEMENTATION COMPLETE` to the scratchpad

### Step C — Next Story

After Reviewer approval, the flow returns to Planner (you) to:
- Confirm the story is marked ✅ in the epic doc
- Move to the next story and repeat from Step A
- When all stories are done, update the epic status to `Done`

## Rules

- **Always create a shared scratchpad first** — before any research or planning
- **Always create TODOs** — the Implementer depends on them as a checklist
- **Never write code yourself** — that is the Implementer's job
- **Scratchpad is the context bridge** — all agents read and append to it across handoffs
