# ARD-005: Foundry Hosted Agent Deployment

> **Status:** Accepted (Revised 2026-02-26)
> **Date:** 2026-02-25 (revised 2026-02-26)
> **Decision Makers:** Engineering Team

## Context

The KB Agent is a conversational agent built with Microsoft Agent Framework (`ChatAgent`) that provides vision-grounded, search-augmented answers. It uses a `search_knowledge_base` tool, vision middleware for image injection, and supports SSE streaming.

The agent needs to be deployed to Azure alongside the web app. The question is **how** to deploy the agent — as a standalone Container App, or as a Foundry hosted agent within the Azure AI Foundry project.

## Decision

**Deploy the KB Agent as a Foundry hosted agent** using AZD's `azure.ai.agents` extension **and** the official `from_agent_framework` hosting adapter.

### What This Means

- A single `main.py` entry point is used for both local development and Foundry deployment
- The `from_agent_framework` adapter wraps our `ChatAgent` and provides:
  - The Responses protocol endpoints (`/responses`, `/runs`)
  - SSE streaming with keep-alive heartbeats (`agent.run_stream()` → Server-Sent Events)
  - Health / readiness probes (`/liveness`, `/readiness`)
  - Lazy agent creation (agent built on first request, not at import time)
- The agent container is built in ACR via remote build and deployed to the Foundry project
- Foundry provides a stable HTTPS endpoint with Entra ID authentication, managed identity, and a hosting runtime
- The web app calls the agent via the Foundry endpoint using `DefaultAzureCredential` (Entra token auth)

### Streaming

The `from_agent_framework` adapter **fully supports SSE streaming**. When the client sends `stream: true`, the adapter calls `agent.run_stream()` and converts the async generator output into the standard Responses API SSE event sequence:

```
response.created → response.in_progress → response.output_item.added →
response.output_text.delta (repeated) → response.output_text.done →
response.output_item.done → response.completed
```

Function call arguments, results, and tool outputs are also streamed as separate output items, enabling clients to extract structured data (e.g., citation metadata from search results) without custom protocol extensions.

### Citation Flow

Previously, citations were injected as custom `metadata.citations` in the `response.completed` SSE event by a custom FastAPI server. The adapter doesn't support injecting custom metadata into response events.

Instead, citations flow through the standard protocol:
1. The adapter streams function call output items (`response.output_item.done` with `type: function_call_output`)
2. The `search_knowledge_base` function result JSON includes `chunk_index` and `image_urls` fields
3. The web app extracts citation data from these function call output events

This is cleaner — citation data travels through the standard Responses API protocol rather than a custom metadata sideband.

### Configuration

The AZD agent service uses:
- `host: azure.ai.agent` — Foundry hosted agent deployment target
- `language: docker` with `remoteBuild: true` — container built in ACR
- `config.container` — CPU/memory/scale settings for the hosted container
- `config.deployments` — model deployment declarations (gpt-4.1)

The agent manifest (`agent.yaml`) uses the `ContainerAgent` schema:
- `kind: hosted` — indicates a hosted container agent
- `protocols: [{protocol: responses, version: v1}]` — the agent implements the Responses API
- `environment_variables` — config values injected into the container at runtime

## Alternatives Considered

### Alternative 1: Deploy Agent as Standalone Container App (Rejected)

Deploy the agent as a second Container App alongside the web app, using the existing Container Apps Environment.

- **Pros:** Simpler — no Foundry-specific configuration, reuses existing Container App patterns. Full control over networking and scaling.
- **Cons:** No Foundry integration — no managed agent identity, no Foundry tracing, no agent lifecycle management. The web app would need a different auth pattern (service-to-service within Container Apps Environment). Does not leverage the Foundry project we already provision. Misaligned with the platform direction for agent hosting.

### Alternative 2: Custom FastAPI Server Without Adapter (Rejected — Revised)

> **Original decision (2026-02-25):** Use a custom FastAPI server instead of the adapter, claiming the adapter didn't support streaming and custom citation metadata.
>
> **Revised (2026-02-26):** Investigation of the adapter source code revealed this was incorrect. The adapter fully supports SSE streaming via `agent.run_stream()`. The citation metadata limitation is real but solvable — function call output events carry the search results, and the web app can extract citations from those. The custom server approach was rejected in favor of the adapter because:
> - It duplicates protocol logic the adapter already handles correctly
> - It requires maintaining a second entry point (`main_local.py`) for local dev
> - It's not guaranteed to match Foundry's container lifecycle expectations (health probes, startup protocol)
> - The adapter works identically for local and deployed scenarios

### Alternative 3: Deploy via `az cognitiveservices account agent publish` Only (Deferred)

Use the publish CLI command without AZD integration.

- **Pros:** Direct control over the publish step. Already partially scripted in `scripts/publish-agent.sh`.
- **Cons:** Bypasses AZD's service lifecycle (build → push → deploy). The publish command expects the agent container to already be deployed. Unclear how it interacts with the AZD extension's deployment flow. May be needed as a post-deploy step for RBAC assignment regardless.

## Consequences

1. **`main.py`** uses `from_agent_framework(_create_agent).run()` — single entry point for local + deployed
2. **`main_local.py`** deleted — no longer needed
3. **`infra/azure/azure.yaml`** agent service set to `host: azure.ai.agent` with proper `config` block
4. **`agent.yaml`** uses `ContainerAgent` schema format
5. **`pyproject.toml`** includes `azure-ai-agentserver-agentframework>=1.0.0b7` and `starlette<1.0` (adapter dependency compatibility)
6. **Web app** extracts citations from `response.output_item.done` (function call output) instead of `response.completed.metadata`
7. **Web app `AGENT_ENDPOINT`** set to `http://localhost:8088` for local (no `/v1` prefix — adapter serves at root)
8. **RBAC** — published agent identity needs roles on AI Services, AI Search, and Serving Storage

## References

- [Research 006: Foundry Hosted Agent Deployment](../research/006-foundry-hosted-agent-deployment.md)
- [AZD AI Agent Extension](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/extensions/azure-ai-foundry-extension)
- [Hosted Agents Concept](https://learn.microsoft.com/en-us/azure/ai-services/agents/concepts/hosted-agents)
