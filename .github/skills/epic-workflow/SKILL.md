---
name: epic-workflow
description: 'Manages epic and story lifecycle for the KB Agent project. Reads epic files, verifies acceptance criteria, updates story status, and checks Definition of Done. Use when completing stories, starting new work, or auditing epic status.'
---

# Epic Workflow

Manage the KB Agent epic/story tracking workflow. Epic docs in `docs/epics/` are the source of truth for all story status.

## Epic File Conventions

Epics follow this structure:

```markdown
# Epic NNN — <Title> [✅ when all stories done]

> **Status:** Draft | In Progress | Done

## Stories

### Story N — <Title> [✅ when done]

> **Status:** Not Started | In Progress | Done

#### Deliverables
- [x] Completed deliverable
- [ ] Incomplete deliverable

#### Implementation Scope

| File | Action | Description | Status |
|------|--------|-------------|--------|
| `path/to/file.py` | Create | Description | ✅ |

#### Definition of Done
- [x] Code complete
- [x] Unit tests passing
- [ ] Integration tests passing
```

## When Starting a Story

1. **Verify the epic reflects reality** — check that previous stories are accurately marked
2. **Run baseline checks:**
   ```bash
   make dev-test    # current repo-wide test suite passes
   ```
3. **Read the story's acceptance criteria** — understand exactly what "done" means
4. **Check for dependencies** — are prerequisite stories completed?

## When Completing a Story

1. **Run tiered quality checks:**
   ```bash
   make dev-test          # current repo-wide test suite
   cd src/agent && uv run pytest tests -o addopts= -m "not uitest"
   cd src/web-app && uv run pytest tests -o addopts= -m "not uitest"
   cd src/functions && uv run pytest tests -o addopts= -m "not uitest"
   ```
   For Azure integration:
   ```bash
   make dev-test          # run against the deployed environment once env vars are configured
   ```
2. **Update the epic doc immediately:**
   - Check off all acceptance criteria / deliverables: `- [ ]` → `- [x]`
   - Add ✅ to the story title
   - Mark implementation scope rows: add `✅` to the Status column
   - Check off all Definition of Done items
3. **Update epic status** if all stories are now complete:
   - Change `Status: In Progress` → `Status: Done`
   - Add ✅ to the epic title

## Rules

- **Never leave an epic partially updated** — code done = doc must match
- **Never start a story if the epic doesn't reflect reality** — audit first
- Story completion is atomic: code + tests + epic update = one commit
