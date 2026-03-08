---
description: "Start a new story from an epic — validates preconditions and produces a task breakdown."
mode: "agent"
agent: "planner"
---

# New Story

Pick up the next story from an epic file.

## Variables

- `epicFile` — path to the epic file (e.g., `docs/epics/006-foundry-agent-evaluations.md`)

## Steps

1. Read the epic file at `${epicFile}`
2. Identify the next story that is **not** marked with ✅
3. Validate preconditions:
   - All prior stories are ✅ with acceptance criteria checked off
   - No partially-updated stories exist
   - Ask the user to run `make test` to confirm baseline passes
4. Produce a task breakdown:
   - Numbered steps with specific file paths
   - Expected test coverage for each step
   - Definition of Done checklist
5. Confirm the plan with the user before handing off to @coder
