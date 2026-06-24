---
name: performance-review
description: 'Reviews code for performance issues across Azure AI Search, Cosmos DB, blob storage, async I/O, and LLM/agent token usage. Use when reviewing data-heavy, latency-sensitive, or cost-sensitive code.'
---

# Performance Review

Review changes for performance and cost issues in this project's Azure-backed services. Rate each finding **CRITICAL** / **HIGH** / **MEDIUM** / **LOW**.

## Azure AI Search

- [ ] Queries request only the fields needed (`select`) instead of returning whole documents
- [ ] `top` / pagination used for result sets — no unbounded result retrieval
- [ ] Filters use indexed fields; OData filter values are validated/escaped (no injection, no full scans)
- [ ] Vector / hybrid search parameters (k, reranker) are sized deliberately, not maxed by default
- [ ] Repeated identical searches within a request are deduplicated or cached, not re-issued per item

## Cosmos DB

- [ ] Queries are partition-scoped (include the partition key) — no cross-partition fan-out on hot paths
- [ ] Point reads (`read_item` by id + partition key) used instead of queries when the key is known
- [ ] No N+1 access pattern — bulk-read related items rather than one round trip per id
- [ ] Indexing policy fits the access pattern; large unused properties excluded from indexing
- [ ] RU cost of new queries considered; pagination (continuation tokens) used for large reads
- [ ] Writes are idempotent and batched where the SDK allows

## Blob / Storage

- [ ] Images and large blobs streamed, not fully buffered in memory when avoidable
- [ ] Blob/container clients reused, not recreated per call
- [ ] Blob names and paths sanitized (no traversal) and access scoped via managed identity
- [ ] No per-item blob existence checks in a loop when a single listing would do

## Async I/O

- [ ] No blocking calls on the event loop (sync SDK clients, `time.sleep()`, CPU-heavy work in an async path)
- [ ] Independent I/O operations run concurrently with `asyncio.gather()`, not awaited serially in a loop
- [ ] `await` used on every async operation — no fire-and-forget without `create_task()` and error handling
- [ ] Async Azure SDK clients used in async code; sync clients confined to sync contexts (or `asyncio.to_thread`)
- [ ] HTTP/SDK client sessions reused across calls, not constructed per request

## LLM & Agent Efficiency

- [ ] Prompts and context windows are bounded — no unbounded history or document dumping into the model
- [ ] Retrieved search context is trimmed to what the answer needs (token cost is real cost)
- [ ] Tool/function calls are necessary and not redundantly re-invoked within a turn
- [ ] Streaming used for user-facing agent responses where latency matters
- [ ] Model selection is config-driven and appropriate to the task (don't use the largest model for trivial steps)
- [ ] Repeated, deterministic lookups are cached rather than re-asked of the model

## API / Response

- [ ] Response payloads are minimal — no over-fetching (return ids/refs when full objects aren't needed)
- [ ] List endpoints support pagination
- [ ] Image references returned as URLs through the known `/api/images/...` pattern, not inlined wholesale
- [ ] Rarely-changing data has appropriate caching / `Cache-Control` where applicable

## Output Format

Rate each finding:
- **CRITICAL** — Will cause outages, severe latency, or runaway cost under load
- **HIGH** — Significant performance/cost issue, fix before release
- **MEDIUM** — Optimization opportunity, address when possible
- **LOW** — Minor improvement suggestion
