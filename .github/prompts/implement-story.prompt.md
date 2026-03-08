---
description: "Implement a story end-to-end — code, tests, and epic doc updates."
mode: "agent"
agent: "coder"
---

# Implement Story

Implement the current story based on a task breakdown (from @planner or user-provided).

## Steps

1. Review the task breakdown and acceptance criteria
2. For each task:
   a. Read existing code in the target area
   b. Implement the change following project patterns
   c. Write or update tests for new logic
   d. Run `make test` to confirm no regressions
3. After all tasks are complete:
   a. Run the full test suite: `make test`
   b. Update the epic doc:
      - Check off acceptance criteria (`- [x]`)
      - Mark implementation scope table rows with ✅
      - Check off Definition of Done items
      - Add ✅ to the story title if all criteria are met
4. Summarize what was done and what was tested
