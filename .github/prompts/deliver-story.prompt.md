---
description: "Implement a story end-to-end — plan, then hand off to @implementer and @reviewer."
agent: "Planner"
---

# Implement Story

Deliver a single story from task breakdown to Done, using the handoff workflow.

## Variables

- `epicFile` — path to the epic file (e.g., `docs/epics/008-per-function-container-split.md`)
- `storyNumber` — the story number to implement (e.g., `3`)

## Step 1 — Setup & Plan

1. **Create a shared scratchpad** — `shared-scratchpads/{epic}-story-{N}.md` (MANDATORY first action)
2. Read the epic file at `${epicFile}` and locate Story `${storyNumber}`
3. Read `docs/specs/architecture.md` and `docs/specs/infrastructure.md` for context
4. Validate preconditions:
   - All prior stories are marked ✅
   - No partially-updated stories exist
5. Produce a task breakdown:
   - Numbered, actionable steps with specific file paths
   - Expected test coverage
   - Definition of Done checklist
6. **Create TODOs** — one per implementation step
7. **Append the plan to the scratchpad**

## Step 2 — Hand off to Implementer

Use the **Start Implementation** handoff button to transfer to @implementer.
The Implementer will:
- Read the shared scratchpad for full context
- Follow the TODOs as a checklist, marking each in-progress → completed
- Implement all deliverables following existing project patterns
- Write tests alongside the code (happy path + edge cases + error paths)
- Handle infrastructure changes (Bicep, azure.yaml, AZD) if the story requires them
- Debug failures in-context using the `debugging` skill
- If a design-level issue is found, hand back to @planner via **Revise Plan**
- Update the epic doc (acceptance criteria, implementation scope, DoD)
- Append progress to the shared scratchpad
- Hand off to @reviewer via **Request Review** when ready

## Step 3 — Review (handled by @reviewer)

The Implementer hands off to @reviewer via the **Request Review** button.
The Reviewer will:
- Check architecture compliance, security, tests, code quality, and epic doc status
- Produce a verdict with a handoff recommendation:
  - **Quick Fix** → hand back to @implementer for localized fixes
  - **Rework** → hand back to @implementer for significant changes
  - **Re-plan** → hand back to @planner for plan revision
  - **Approve** → append `IMPLEMENTATION COMPLETE` to the scratchpad

## Step 4 — Confirm Completion

After Reviewer approval:
- Verify the epic doc has the story marked ✅
- Verify all acceptance criteria are checked off
- Confirm the scratchpad has the `IMPLEMENTATION COMPLETE` marker

## Rules

- **Always create a shared scratchpad first** — before any research or planning
- **Always create TODOs** — the Implementer depends on them
- **Never write code yourself** — that is the Implementer's job
- **Never skip the review step** — the Reviewer catches issues others may miss
- **Scratchpad is the context bridge** — all agents read and append to it across handoffs
