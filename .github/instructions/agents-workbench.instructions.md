---
name: 'Agents Workbench'
description: 'Persistent cross-agent coordination protocol for .agents-workbench/. Use when creating, joining, reviewing, reworking, closing, or reopening an Agents Workbench task, lane, review, promotion, or archive candidate.'
applyTo: '.agents-workbench/**'
---

# Agents Workbench Protocol

The Agents Workbench is the **persistent, gitignored workspace** for multi-agent work. One workbench per task slug carries the current state each agent needs to act, plus a durable plan ledger that records how the work unfolded. Nothing in it is ever deleted: lanes retire as `closed` and freeze, the program retires as `complete` and stays on disk, and the user can reopen a workbench later to add new work. Durable product truth still lives in tracked source, tests, specs, ARDs, epics, and GitHub issues — the workbench records coordination and lineage, not product truth.

Treat every workbench file as a **live message, not a log**. Update it in place to reflect current state; do not append a changelog inside a file. The one ledger that legitimately grows is `plan.md`, which records lane lifecycle (see below). If a fact already lives in git or an issue, link it — don't copy it.

## Results Travel As Messages

A spawned subagent returns its result to its parent as its **final message** — that is the primary hand-off channel, and it keeps each subagent's context clean. A parent writes that result into the workbench **only when it must outlive the hand-off** (a sibling lane needs it, or it informs closure). A pure reviewer never writes files at all: it returns its verdict, and the parent records it only if it must be kept.

This is why most work needs no files: the parent integrates the returned message and moves on. Reach for a file only when state must persist *between* agents.

## When The Workbench Exists

The message-first rule governs *what gets written*, not *whether the workbench exists*. The task owner creates the workbench the moment work is split into **one or more** delegated lanes. Three creation rules:

- **`plan.md`** — the always-on ledger. Created with the workbench and owned by the task owner; it records program status and the lane registry (see *Plan Ledger & Lane Lifecycle* below).
- **`lanes/<lane>/assignment.md`** — created for **every** delegated lane, single or multi. It is the lane owner's entry point.
- **`shared/brief.md`** — created **only when there are ≥2 lanes**, to hold the cross-lane contract those lanes must agree on. A single-lane task has no `shared/` directory; its `assignment.md` is self-contained.

"Most work needs no files" applies *below* the lane boundary — the leaf hand-offs (Implementer, Reviewer) that return as messages. Only a task the owner completes alone, without delegating a lane, needs no workbench.

## Never Nest The Workbench

The workbench is always at the repository root: `.agents-workbench/<task>/...`. Never create or write a nested workbench such as `src/.agents-workbench/` or `infra/.agents-workbench/`. If your working directory would make a relative path resolve elsewhere, use the repo-root absolute path. If you find a nested workbench, reconcile anything useful back to the root workbench and remove the nested artifact.

## Directory Shape

Create a file only when it carries state another agent needs. `plan.md` and each lane's `assignment.md` are the exceptions — they always exist once work is delegated.

```text
.agents-workbench/
  <task-slug>/
    plan.md                  # always-on ledger: program status + lane registry (task owner)
    shared/
      brief.md               # cross-lane contract — only when ≥2 lanes
    lanes/
      <lane-slug>/
        assignment.md        # lane charter — the lane owner's entry point
        result.md            # lane outcome for the owner, updated in place
        scratch.md           # optional private working notes
        promote/<topic>.md   # optional upward message (status: open → integrated)
        reviews/<lens>.md    # optional persisted reviewer verdict
    archive-candidates.md    # optional closure input for the Archivist
```

A single-lane workbench omits `shared/`; the lane's `assignment.md` is the entry point. No versioning, no transcripts, no copied source, no per-subagent directories.

## File Contracts

| File | Is | Is not |
|---|---|---|
| `plan.md` | The task owner's durable ledger: program status (`active`/`complete`), the lane registry (number, mode, status, outcome/lineage), open questions still churning, and closure intent | A transcript, or a place lanes read their charter |
| `shared/brief.md` | The cross-lane contract (≥2 lanes): goal, non-goals, lane list, and **accepted** cross-lane decisions every lane can depend on | Open questions, a plan history, or a generic readme |
| `lanes/<lane>/assignment.md` | The charter the lane owner receives: goal, mode (discovery/delivery/convergence), exact paths to read, what to deliver, the boundary. Self-contained — it inlines the context the lane needs and its read-paths point only at tracked source, `shared/brief.md`, or a frozen lane's `result.md`/`reviews/*` | Findings, notes, the result, or a read-path to `plan.md` or another lane's working files |
| `lanes/<lane>/result.md` | The lane's current outcome for the owner: status, what was delivered, residual risk, recommendation — updated in place, frozen when the lane closes | A running log or a findings dump |
| `lanes/<lane>/scratch.md` | The lane owner's throwaway working notes | Anything another agent is expected to rely on |
| `lanes/<lane>/promote/<topic>.md` | One upward fact or decision the task owner needs, with a recommended action and a `status: open → integrated` marker | A log, or a second copy of the result |
| `lanes/<lane>/reviews/<lens>.md` | A reviewer verdict the lane owner persisted because it must outlive the hand-off, named for the lens reviewed (`security`, `architecture`, `security-post-rework`) | New work, or edits to the thing reviewed |
| `archive-candidates.md` | Durable follow-ups the task owner queues for the Archivist to propose as issues, each with a source reference | Applied edits to specs, epics, or docs |

## Slugs

Task slug, when epic context exists:

```text
<epic-NN>-<suffix>
```

Examples: `017-handoff-rework`, `010-memory-layer-cosmos`, `008-per-function-split`. The `epic-NN` segment ties the workbench to its epic in `docs/epics/`. If that context is missing and likely knowable, the task owner asks for it before creating the workbench. Otherwise use an ask-derived slug such as `cache-timeout-fix` or `flaky-agent-startup`.

Lane slugs use lower-kebab-case, with a two-digit prefix because order and lineage matter (`01-agent-tool`, `02-index-function`). Numbers are **monotonic across the workbench's whole life** — never reused, even after a lane closes or the program is reopened.

## Plan Ledger & Lane Lifecycle

`plan.md` is the task owner's durable index of the whole program. It is the first thing any agent reads to resume, and the contract that keeps a reopened workbench from reusing stale context.

```markdown
## Program status: active | complete

## Lane registry
| Lane | Mode | Status | Outcome / Lineage |
|---|---|---|---|
| 01-agent-tool | delivery | closed | <one-line outcome>. Reviewed ✓ |
| 02-index-function | delivery | active | in flight |
| 03-fix-validation | delivery | active | reworks 01 (reads lanes/01-agent-tool/result.md) |

## Open questions   (owner-held, churning; an accepted one graduates to shared/brief.md)
## Closure intent   (what will become archive-candidates.md)
## Closure log      (issues proposed / user-approved / filed, per closure pass)
```

Rules the task owner follows:

- **A lane is `active` or `closed`.** On close, record its one-line outcome and any lineage. A closed lane is **immutable** — never reopened, never edited.
- **Rework is a new lane, not a reopened one.** When returned work needs more, spawn the next-numbered lane whose `assignment.md` names exactly what to fix and points at the frozen lane's artifacts (`result.md`, `reviews/*`) as read-context — so the new lead inherits context without inheriting churn.
- **The program retires as `complete`, not deleted.** `complete` is a reversible status: reopening flips it back to `active` and appends new monotonic lanes to the same registry.
- **Scope routing.** Open question → `plan.md`; accepted cross-lane decision → `shared/brief.md`; deferred follow-up → `archive-candidates.md`; lane-only decision → that lane's `assignment.md`.

## Write Rules

Read only what you are given. Write only your own workspace. Promote upward when others need to know. Every file in a lane is created and written by **that lane's owner** (the TechLead); leaves (Implementers, Reviewers) return messages and write no files.

| Path | Writer | Readers |
|---|---|---|
| `plan.md` | Task owner only | Task owner |
| `shared/*` | Task owner only | Every lane owner on the task |
| `lanes/<lane>/*` | That lane's owner | That lane's owner and its subagents |
| `lanes/<lane>/promote/*` | That lane's owner | Task owner |
| `lanes/<lane>/reviews/*` | That lane's owner (recording a returned verdict) | That lane's owner, task owner |
| `archive-candidates.md` | Task owner or Archivist | Task owner, Archivist |

Do not edit sibling lanes, `shared/*`, or `plan.md` unless you own them.

## Subagent Manifest

Every spawned subagent gets a tiny manifest naming exactly what to read and the single thing to return or write. Keep read-lists explicit and narrow — never "read the workbench."

**Read-context boundary.** A lane's read-paths point at **nothing from the workbench root** — no `plan.md`, no sibling lane's files. The only workbench paths a lane may be given are its own `lanes/<lane>/*`, `shared/brief.md` when it exists, and a frozen lane's `result.md`/`reviews/*` for rework lineage. Everything else a lane reads must be tracked source, specs, or docs in the codebase. If a lane needs a fact the owner holds in `plan.md`, the owner **inlines that fact into the assignment** — it never hands over the `plan.md` path.

```markdown
Read only:
- .agents-workbench/<task>/lanes/<lane>/assignment.md
- .agents-workbench/<task>/shared/brief.md   # only if it exists (≥2 lanes)

Return your result as your final message.
Do not write files. (If your parent assigned a write target, write only that one path.)

Do not edit: plan.md, shared/*, sibling lanes, tracked docs unless explicitly assigned.
```

## Spec Drift

Treat code as evidence, not desired state — the full rule lives in the repository's root instructions. In a lane: if the correction is minor and in scope, fix it and prove it with a test; if it is major, changes product behavior, crosses ownership, or implies the spec is wrong, promote the decision to the TechnicalPM before implementing. Do not quarantine spec-invalid behavior just because existing code depends on it. The project's **No implicit degraded mode** failure policy applies — never add an unspec'd fallback to make a lane green.

## Review Outputs

A reviewer returns one short verdict as its final message (the lane owner persists it to `reviews/<lens>.md`, named for the lens reviewed, only if it must be kept):

```markdown
## Verdict

- Verdict: Approve | Quick Fix | Rework | Re-plan
- Scope reviewed: ...
- Spec alignment: ...
- Findings: ...
- Required changes: ...
- Residual risk: ...
- Promote to shared context? yes/no
- Archive candidate? yes/no
```

## Keep It Small

- **Current state, not history.** Update files in place; never append a changelog inside a file. `plan.md` is the one ledger that grows — by lane-registry rows, not by transcript.
- **Prefer a message over a file.** Persist only state that must survive a hand-off between agents.
- **Nothing is deleted.** A finished lane is retired `closed` in `plan.md` and frozen; an integrated `promote/` note is flipped `status: integrated`, not removed. Keeping closed artifacts is what makes rework and reopening cheap.
- **Link, don't copy.** Reference git, specs, and issues; do not paste their contents.
- **Completion is a status, not a deletion.** At task end the owner runs the Archivist and marks the program `complete` in `plan.md`. The gitignored workbench stays on disk so the user can reopen it later.

## Closure

Closure is the workbench's final lifecycle phase, owned by the TechnicalPM (the ReleaseManager delegates closure to a TechnicalPM rather than owning a workbench). It consumes `archive-candidates.md` plus the closed lanes' artifacts and ends with the program marked `complete` in `plan.md`. The workbench-side facts:

- **A user gate sits in the middle.** Durable follow-ups are *proposed* first, the user approves/edits/drops/rejects, and only the approved set is acted on. Nothing is filed without that gate.
- **The TechnicalPM gates; the Archivist files.** The TechnicalPM invokes the Archivist for closure and runs the user gate, but never files issues itself — the Archivist is the only agent that files issues, through the GitHub MCP server tools. How the Archivist behaves across its propose/file invocations lives in `archivist.agent.md`.
- **The outcome is recorded, not discarded.** The TechnicalPM logs the filed issues in the `plan.md` closure log and marks the program `complete`. The gitignored workbench stays on disk so the user can reopen it later to add work; the slug is the stable handle for that reopening.
