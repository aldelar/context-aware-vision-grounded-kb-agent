---
name: 'Epic & Story Tracking'
description: 'Epic lifecycle, story completion checklist, and doc-code consistency rules'
applyTo: "docs/epics/**"
---

# Epic & Story Tracking

## Structure

- Epic files live in `docs/epics/` — each file is the **source of truth** for its stories
- Naming: `{number}-{slug}.md` (e.g., `001-local-pipeline-e2e.md`)
- Each epic has: objective, stories with acceptance criteria, implementation scope tables, and a Definition of Done

## Story Lifecycle

### Before Starting a Story

1. Read the epic file and verify it reflects reality
2. Confirm all prior stories are marked ✅ (code matches doc)
3. Run `make dev-test` — baseline must pass
4. Verify the next story is ready to pick up without auditing code

### During Implementation

- Work through acceptance criteria one by one
- Track progress against the implementation scope table
- Write tests as you go (not after)

### After Completing a Story

Update the epic file **immediately** — never leave it partially updated:

1. Check off all acceptance criteria: `- [x]`
2. Add ✅ to the story title
3. Mark implementation-scope table rows with ✅ for completed files
4. Check off all Definition of Done items
5. If all stories are done, update the epic's top-level `Status:` field → `Done`

## Rules

- The epic doc must always match the code state — if code is done, the doc must reflect it
- A new session should be able to pick up confidently from the epic doc without re-auditing
- Never start a new story if the previous story's doc is inconsistent with code
- Stories should be small enough to complete in a single session when possible
