---
name: Deferred Follow-up
about: A durable follow-up surfaced during multi-agent work that was intentionally left out of an in-flight epic
labels: follow-up
---

## Problem statement
<!-- State the concrete problem or gap as a standalone issue. A reader who never saw the originating
     work should understand exactly what is wrong or missing. Do not reference "the workbench" here. -->

## Why it matters
<!-- Impact if this is never done: correctness, user trust, data integrity, performance, security,
     maintainability, or blocked downstream work. Be specific about what degrades or breaks. -->

## Why it was deferred
<!-- Which epic surfaced this and why it could not be done there: in-flight protection, a recorded
     decision, sequencing/dependency, or scope. Name the decision (e.g. "workbench decision D7") if one applies. -->

## Proposed solution / options
<!-- Concrete approaches if known. "None yet — needs investigation" is a valid answer. When the fix touches
     records that must be preserved (e.g. checked DoD items capturing point-in-time verification), say so and
     distinguish them from forward-looking changes that can be safely rewritten. -->

## Code & document references
<!-- Pin every reference so it stays valid as the tree moves. Prefer, in this order:
     1. Commit-pinned permalink with a line range
     2. A short fenced code/doc snippet
     3. A copy-pasteable search command
     NEVER cite bare line numbers without a commit-pinned anchor — they drift. -->

- Permalink: `https://github.com/<org>/<repo>/blob/<commit-sha>/<path>#L<start>-L<end>`
- Search: `rg "<unique string>" <path>`
- Snippet:
  ```text
  <paste the relevant lines here>
  ```

## Source trace
<!-- Just enough provenance that the temporary workbench can be deleted without losing the trail. -->

- Epic: `Epic <NN>` (`docs/epics/<NN>-<slug>.md`)
- Agents Workbench: `.agents-workbench/<task-slug>`
- Lane / subagent: `<lane-slug>` / `<subagent-slug>` (or n/a)
- Recommended next decision: ignore | fold into existing epic | create story | create epic | investigate later
- Suggested owner / reviewer: `<role or n/a>`

<sub>Filed by Archivist from a closed Agents Workbench.</sub>
