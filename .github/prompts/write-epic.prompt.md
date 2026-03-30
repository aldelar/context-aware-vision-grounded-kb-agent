---
description: "Write a new epic — iteratively scope, clarify, and break down into well-defined stories with testable Definitions of Done."
agent: "planner"
---

# Write Epic

Collaboratively author a new epic file in `docs/epics/`. Prioritise **asking questions and presenting options** to narrow scope before writing story details.

## Variables

- `epicNumber` — the next epic number (e.g., `009`)
- `epicSlug` — short kebab-case label (e.g., `agent-memory-layer`)
- `topic` — free-form description of the desired capability or change

## Phase 1: Understand & Clarify

Before writing anything, gather enough context to scope the epic precisely:

1. **Read existing context** — `docs/specs/architecture.md`, `docs/specs/infrastructure.md`, and any related ARDs, research docs, or prior epics that touch the same area.
2. **Ask clarifying questions** — present these to the user and WAIT for answers before continuing:
   - What is the **end-user or developer outcome** when this epic is done?
   - Are there **specific constraints** (no new Azure resources, must work offline, backward-compatible, etc.)?
   - Which parts of the codebase does this touch (`src/functions/`, `src/agent/`, `src/web-app/`, `infra/`, etc.)?
   - Is there an existing spike, research doc, or ARD that informs the approach? If not, should a spike be the first story?
   - Are there **open design choices** (e.g., "option A vs option B")? List them and ask the user to pick or ask for a comparison.
3. **Present options where ambiguity exists** — for each open question, offer 2–3 concrete options with trade-offs and a recommendation. Let the user decide.
4. **Confirm scope boundary** — explicitly state what is IN scope and what is OUT of scope, and get the user to agree before proceeding.

Do NOT proceed to Phase 2 until the user has confirmed the scope.

## Phase 2: Draft the Epic Header

Write the top section of the epic following this structure (matches epics 007/008):

```markdown
# Epic {epicNumber} — {Title}

> **Status:** Draft
> **Created:** {today's date}
> **Updated:** {today's date}

## Objective

{1–2 paragraph description of what this epic achieves and why it matters.
Include concrete, measurable outcomes — not vague aspirations.}

## Success Criteria

- [ ] {Observable, testable criterion — what a reviewer can verify}
- [ ] {Another criterion — prefer `make ...` commands, test counts, or deploy checks}
- [ ] ...

## Background

{Context section with comparison tables, current-vs-proposed state,
or architecture details — whatever helps the reader understand the "why" and "how".
Use tables generously for structured comparisons.}
```

Present the draft to the user and ask:
- Does the Objective capture the right goal?
- Are the Success Criteria complete and testable? Can each one be verified by running a command or inspecting a file?
- Is the Background section sufficient or does it need more detail?

Revise until the user approves.

## Phase 3: Break Down Into Stories

Design stories following these principles (derived from epics 007 and 008):

### Story Design Rules

1. **Each story is independently completable** — it has a clear start, clear end, and leaves the project in a working state (tests pass).
2. **Spike first** — if the approach is uncertain, make Story 1 a spike/research story that produces a go/no-go recommendation before implementation begins.
3. **Explicit dependencies** — every story states `> **Depends on:** Story N ✅` or `> **Depends on:** None`. Flag stories that can run in parallel.
4. **Small enough for one session** — if a story has more than ~8 deliverables or touches more than 3–4 areas of the codebase, split it.
5. **Tests are per-story** — each story either includes its own test deliverables or has a dedicated test story immediately after. Never defer all testing to the end.
6. **Docs & cleanup are explicit** — documentation updates and artifact cleanup are their own story (usually the last one), not an afterthought.

### Story Template

Each story must follow this structure:

```markdown
### Story N — {Descriptive Title}

> **Status:** Not Started
> **Depends on:** {Story M ✅ | None}

{1–2 sentence description of what this story achieves.}

#### Deliverables

- [ ] {Specific, actionable task with file paths where applicable}
- [ ] {Another task — include module names, function signatures, or config keys}
- [ ] ...

#### Implementation Notes

{Optional section — design hints, patterns to follow, gotchas to avoid.
Reference existing code patterns (e.g., "follow the same pattern as `fn_convert_mistral/describe_images.py`").}

#### Definition of Done

- [ ] {Testable assertion — e.g., "`make dev-test` passes with zero regressions"}
- [ ] {Testable assertion — e.g., "`python -m fn_foo <args>` works for all sample articles"}
- [ ] {Testable assertion — e.g., "No new linter warnings in `az bicep build`"}
```

### Definition of Done Guidelines

Every DoD item must answer: **How does someone verify this is done?** Prefer:
- `make ...` commands with expected output (test count, zero errors, specific behavior)
- CLI invocations with expected results
- File existence / absence checks
- `az bicep build`, `azd -C infra/azure deploy`, or similar infrastructure validation commands
- Specific metrics or comparisons (e.g., "output within ±5% of baseline")

Avoid vague DoD items like "code is clean", "works correctly", or "properly tested".

## Phase 4: Review & Refine Stories

Present the full story list to the user and ask:

1. **Ordering** — are the dependencies correct? Can any stories be parallelised?
2. **Granularity** — is any story too large? Too small? Should any be merged or split?
3. **Coverage** — are there gaps? Missing test stories, missing doc updates, missing cleanup?
4. **Risk** — which story carries the most uncertainty? Should it be preceded by a spike?
5. **Definition of Done** — for each story, is every DoD item something you can concretely verify? If not, rewrite it.

Iterate until the user approves the full story breakdown.

## Phase 5: Write the Epic File

1. Assemble the final epic into `docs/epics/{epicNumber}-{epicSlug}.md`
2. Include all sections: Objective, Success Criteria, Background, and all Stories with Deliverables, Implementation Notes, and Definition of Done
3. Set `Status: Draft` at the top (it becomes `In Progress` when Story 1 starts)
4. Present the complete file to the user for final approval before writing

## Rules

- **Never skip Phase 1** — the clarification phase is the most important part. An epic with the wrong scope wastes more time than no epic at all.
- **Always present options** — when there are multiple valid approaches, lay them out with trade-offs instead of picking one silently.
- **Be concrete** — file paths, module names, make targets, test counts. Abstract epics lead to confusion during implementation.
- **Match existing style** — follow the formatting patterns in epics 007 and 008 (tables, blockquote status lines, checkbox lists, horizontal rules between stories).
- **You do not write code** — you plan. Implementation is handled by @implementer via `deliver-epic` or `deliver-story` prompts.
