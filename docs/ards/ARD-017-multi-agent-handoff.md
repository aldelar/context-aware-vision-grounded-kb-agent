# ARD-017 — Multi-Agent Handoff Orchestration

> **Status:** Accepted
> **Date:** April 7, 2026

## Context

The KB Agent was a single-agent system answering all questions from one AI Search index. Users wanted answers about Azure topics beyond the indexed content (e.g., Cosmos DB, App Service), but the agent could only say "I don't know."

## Decision

Adopt `HandoffBuilder` from `agent-framework-orchestrations` to create a multi-agent system:

1. **Orchestrator** — triage agent that routes questions by topic
2. **InternalSearchAgent** — existing KB search, scoped to Azure AI Search + Content Understanding
3. **WebSearchAgent** — new agent using MCP web search tool against Microsoft Learn documentation

All agents run in a single container. An MCP web search server runs as a separate Container App.

## Rationale

- `HandoffBuilder` provides native handoff orchestration with session propagation — no custom routing logic needed
- Single container avoids operational overhead of deploying each agent separately
- MCP server as a separate service maintains clean architecture boundaries
- SSE transport (not stdio) enables cross-container communication
- Scope externalized to YAML config — topic changes don't require code changes

## Alternatives Considered

- **Separate Container Apps per agent** — rejected; adds complexity for no benefit since agents share the same LLM client
- **Custom routing logic** — rejected; `HandoffBuilder` handles this natively
- **Direct web-search API calls from the agent** — rejected; the MCP server pattern keeps retrieval behind a stable tool contract and lets the same service run unchanged in dev and prod

## Consequences

- Agent container now depends on MCP web search server in Docker Compose
- `agent-framework-orchestrations` is a pre-release dependency
- Makefile targets renamed: `*-agents-*` → `*-agent-*` (single virtual agent container)
