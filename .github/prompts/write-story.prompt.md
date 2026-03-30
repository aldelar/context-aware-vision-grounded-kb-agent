---
description: "Write a new story for an existing epic — clarify scope, define deliverables, and produce a testable Definition of Done."
agent: "planner"
---

# Write Story

Collaboratively author a new story and append it to an existing epic file. Prioritise **asking questions and presenting options** to narrow scope before writing deliverables.

## Variables

- `epicFile` — path to the epic file (e.g., `docs/epics/008-per-function-container-split.md`)
- `topic` — free-form description of the desired change or capability

## Phase 1: Understand the Epic & Clarify

Before writing anything, understand the epic context and scope the story precisely:

1. **Read the epic file** at `${epicFile}` — understand the objective, existing stories, their status, and what has already been delivered.
2. **Read supporting context** — `docs/specs/architecture.md`, `docs/specs/infrastructure.md`, and any ARDs or research docs referenced by the epic.
3. **Determine story number** — the next sequential number after the last story in the epic.
4. **Identify dependencies** — which existing stories (if any) does this new story depend on? Are they already ✅?
5. **Ask clarifying questions** — present these to the user and WAIT for answers before continuing:
   - What is the **concrete outcome** when this story is done? (What can the developer or user do that they couldn't before?)
   - Does this story **fit the epic's objective**, or is it really a new epic?
   - Which **files and areas** of the codebase does this touch? (Narrow it down: specific packages, modules, infra files)
   - Are there **open design choices**? If so, list 2–3 options with trade-offs and a recommendation.
   - Is there **uncertainty** that warrants a spike first, or is the approach clear?
   - Does this story depend on any **unfinished stories** in the epic?
6. **Present options where ambiguity exists** — for each open question, offer concrete alternatives with trade-offs. Let the user decide.
7. **Confirm scope boundary** — explicitly state what this story WILL and WILL NOT do. Get the user to agree before proceeding.

Do NOT proceed to Phase 2 until the user has confirmed the scope.

## Phase 2: Draft the Story

Write the story following the exact structure used in epics 007 and 008:

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
Reference existing code patterns in the repo.}

#### Definition of Done

- [ ] {Testable assertion — e.g., "`make dev-test` passes with zero regressions"}
- [ ] {Testable assertion — e.g., "`python -m fn_foo <args>` works for all sample articles"}
- [ ] {Testable assertion — e.g., "No new linter warnings in `az bicep build`"}
```

### Story Design Rules

1. **Independently completable** — clear start, clear end, project left in a working state (tests pass).
2. **Small enough for one session** — if it has more than ~8 deliverables or touches more than 3–4 areas of the codebase, suggest splitting into multiple stories.
3. **Tests included** — the story either includes test deliverables or you recommend a companion test story. Never defer testing.
4. **Docs if needed** — if the story changes architecture, infra, or user-facing behavior, include doc update deliverables (or recommend a separate doc story).

### Definition of Done Guidelines

Every DoD item must answer: **How does someone verify this is done?** Prefer:
- `make ...` commands with expected output (test count, zero errors, specific behavior)
- CLI invocations with expected results
- File existence / absence checks
- `az bicep build`, `azd -C infra/azure deploy`, or similar infrastructure validation commands
- Specific metrics or comparisons (e.g., "output within ±5% of baseline")

Avoid vague DoD items like "code is clean", "works correctly", or "properly tested".

## Phase 3: Review & Refine

Present the draft story to the user and ask:

1. **Scope** — is this the right size? Too large? Should it be split?
2. **Deliverables** — are they specific enough? Missing anything? Are file paths correct?
3. **Dependencies** — are the declared dependencies accurate?
4. **Definition of Done** — is every item concretely verifiable? If not, rewrite it.
5. **Impact on epic** — does this story change the epic's Success Criteria? Should any be added or updated?

Iterate until the user approves.

## Phase 4: Append to Epic

1. Append the finalized story to the end of the Stories section in `${epicFile}`, preceded by a `---` horizontal rule separator (matching existing story formatting).
2. If the epic's `Status:` is `Done`, change it to `In Progress` — adding a new story means the epic is no longer complete.
3. If the story impacts the epic's Success Criteria, update them accordingly (add new criteria, uncheck any that the new story affects).
4. Update the `Updated:` date to today's date.
5. If the new story changes the epic's scope significantly, update the Background section.
6. Present the updated epic sections to the user for final confirmation before writing.

## Rules

- **Never skip Phase 1** — clarification prevents wasted effort. A story with the wrong scope is worse than no story.
- **Always present options** — when multiple approaches exist, lay them out with trade-offs instead of picking silently.
- **Be concrete** — file paths, module names, make targets, test counts. Abstract stories lead to confusion during implementation.
- **Match existing style** — the new story must look like it belongs alongside the existing stories in the epic (same formatting, same level of detail).
- **Respect the epic boundary** — if the requested work doesn't fit the epic's objective, say so and suggest creating a new epic instead.
- **You do not write code** — you plan. Implementation is handled by @implementer via `deliver-story` or `deliver-epic` prompts.
