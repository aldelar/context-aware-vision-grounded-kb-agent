# Epic 017 — Multi-Agent Handoff Orchestration

> **Status:** In Progress
> **Created:** April 7, 2026
> **Updated:** April 7, 2026

## Objective

Transform the single-agent KB Agent into a **multi-agent system with handoff orchestration**, using the Microsoft Agent Framework's `HandoffBuilder`. A triage orchestrator routes questions to specialist agents based on topic, while the AG-UI protocol surfaces handoff transitions natively in the CopilotKit UI.

After this epic:

- **Orchestrator agent (triage)** — a top-level agent that receives all user questions, determines scope, and hands off to the appropriate specialist. Scoped to Azure topics only — politely declines out-of-scope questions (e.g., sports, general knowledge)
- **Internal-search-agent** — the existing `KBSearchAgent` renamed and scoped to "Azure AI Search & Azure Content Understanding" topics. Uses `search_knowledge_base` against the AI Search index. Retains security filter, vision, and grounding middleware
- **Web-search-agent** — a new agent that performs web searches against a configurable whitelist of sites (initially `learn.microsoft.com` only). Uses an MCP web search tool backed by environment-specific implementations (fetch/scrape for dev, Bing Grounding API for prod). Results are compacted and referenceable from the UI, similar to how internal search chunks work
- **Handoff visible in UI** — the AG-UI protocol's built-in agent handoff events are rendered natively by CopilotKit — no custom UI components needed
- **Shared session across handoffs** — the orchestrator maintains a single conversation history; follow-up questions have full context regardless of which specialist answered previous turns
- **Single container** — all agents run inside the existing agent Docker container on port 8088. No new Container Apps for the agents themselves

### Dependencies

- **`agent-framework-orchestrations>=1.0.0b260402`** — required for `HandoffBuilder`. Pre-release package, add to `pyproject.toml` with `prerelease = "allow"`.

### Framework Compatibility (verified)

- `from_agent_framework()` natively accepts `WorkflowBuilder` — no adapter needed for `/responses`
- `Workflow.as_agent()` returns `WorkflowAgent` which satisfies `SupportsAgentRun` (`run`, `create_session`, `get_session`) — works with `AgentFrameworkAgent` for AG-UI
- `_PersistedSessionAgent` wrapper accepts any `SupportsAgentRun` — `WorkflowAgent` qualifies
- The existing `/responses` and `/ag-ui` endpoints both work with a Workflow-backed agent without architectural changes to `main.py`

## Success Criteria

- [ ] `HandoffBuilder` wires orchestrator → internal-search-agent + web-search-agent
- [ ] Orchestrator correctly routes: Azure AI Search / Content Understanding → internal-search, other Azure topics → web-search, non-Azure → polite decline
- [ ] Internal-search-agent scoped to AI Search + Content Understanding domain via system prompt
- [ ] Web-search-agent queries whitelisted sites only, configured via `src/mcp-web-search/config/whitelist.yaml`
- [ ] MCP web search server: dev implementation (fetch/scrape) deployed as a Container App
- [ ] MCP web search server: prod implementation (Bing Grounding API) deployed as a Container App
- [ ] Both MCP implementations expose the same tool API contract
- [ ] Bing Search resource provisioned via Bicep for prod
- [ ] MCP server behind APIM in prod — same AI Gateway pattern as the agent (JWT auth, rate limiting, telemetry)
- [ ] Agent handoff events (`STEP_STARTED`/`STEP_FINISHED`, `ACTIVITY_SNAPSHOT`) present in AG-UI SSE stream; `author_name` set on specialist agent messages for future CopilotKit native rendering
- [ ] Multi-turn conversations maintain context across agent handoffs (shared session)
- [ ] SecurityFilterMiddleware applies to internal-search-agent only
- [ ] VisionImageMiddleware applies to both agents
- [ ] GroundingMiddleware applies to internal-search-agent only (tied to `search_knowledge_base` result format)
- [ ] CompactionProvider and InMemoryHistoryProvider on the orchestrator only — specialist agents are stateless per invocation
- [ ] Orchestrator politely declines out-of-scope questions (e.g., "Tell me about the LA Olympics")
- [ ] When internal-search-agent has insufficient data, orchestrator can escalate to web-search-agent for supplementary information
- [ ] `/ag-ui` endpoint streams handoff events correctly
- [ ] `/responses` endpoint remains functional (backward compatibility)
- [ ] Web app welcome screen updated with new scope messaging
- [ ] `make dev-test` passes with zero regressions
- [ ] Agent tests cover orchestrator routing, handoff, and decline scenarios
- [ ] Web search results are compacted and referenceable (source URL + paragraph anchor stored as reference ID)
- [ ] Web-app has a proxy API to reload referenced web content segments, similar to the chunk citation pattern
- [ ] Architecture spec updated to reflect multi-agent topology
- [ ] README updated with Pattern 9 (MCP Server as Tool Backend) and Pattern 10 (Multi-Agent Handoff Orchestration)

---

## Background

### Current State

The agent is a **single `Agent`** instance that handles all user questions with one tool:

| Aspect | Current Implementation |
|--------|------------------------|
| Architecture | Single `Agent` with `search_knowledge_base` tool |
| Scope | Any question — answers from AI Search index or says "I don't know" |
| Routing | None — all questions go to the same agent |
| Web search | Not available |
| Session | Per-agent session via `agent-sessions` Cosmos container |
| UI visibility | Tool calls visible; no agent identity shown |

### Target State

The agent becomes a **multi-agent system** with handoff orchestration:

| Aspect | Target Implementation |
|--------|----------------------|
| Architecture | `HandoffBuilder` orchestrator → 2 specialist agents |
| Orchestrator | Triage agent: routes by topic, declines out-of-scope |
| Internal-search-agent | Existing KB agent, scoped to AI Search + Content Understanding |
| Web-search-agent | New agent with MCP web search tool, whitelisted sites |
| Session | Shared across handoffs via `HandoffBuilder` session propagation |
| UI visibility | AG-UI handoff events show which agent is responding |
| Scope | Azure topics only — polite decline for non-Azure questions |

---

## Architecture

### Agent Topology

```
┌─────────────────────────────────────────────────────────┐
│  Agent Container (port 8088)                            │
│                                                         │
│  ┌─────────────────────┐                                │
│  │  Orchestrator Agent  │ ← Triage / handoff            │
│  │  (HandoffBuilder)    │                                │
│  └──────┬───────┬───────┘                                │
│         │       │                                        │
│    ┌────▼────┐  ┌────▼─────────┐                         │
│    │Internal │  │  Web Search  │                         │
│    │ Search  │  │    Agent     │                         │
│    │ Agent   │  │              │                         │
│    └────┬────┘  └──────┬───────┘                         │
│         │              │                                 │
│    AI Search      MCP Web Search                         │
│     Index         Server (Container                      │
│                   App, behind APIM                        │
│                   in prod)                                │
└─────────────────────────────────────────────────────────┘
```

### MCP Web Search Server

Two implementations sharing the same MCP tool contract, deployed as **separate Container Apps**.

In **prod**, the MCP server sits behind **APIM (AI Gateway)** — same Entra app registration / audience as the agent APIM endpoint. The agent's managed identity acquires a token for the same audience to call the MCP APIM endpoint. APIM provides JWT auth, rate limiting, and telemetry.

**MCP transport:** SSE over HTTP (not stdio) — required for cross-container communication. The `agent-framework` MCP client connects to the remote MCP server endpoint via HTTP.

| Environment | Implementation | Networking | Notes |
|-------------|---------------|------------|-------|
| **Dev** | Fetch + scrape | Direct (Docker Compose) | No Azure costs. Runs as a Container App in the dev compose stack |
| **Prod** | Bing Grounding API | **Via APIM AI Gateway** | Same Entra app/audience as agent. Deployed as a Container App in the prod CAE |

**Tool contract** (exposed via MCP):
- `web_search(query: str) -> str` — searches whitelisted sites, returns JSON with structured results

**Return schema** (both dev and prod implementations must produce this format):
```json
{
  "results": [
    {
      "ref_number": 1,
      "title": "Page title",
      "snippet": "Relevant text excerpt from the page...",
      "source_url": "https://learn.microsoft.com/en-us/azure/...",
      "anchor": "section-heading-id"
    }
  ],
  "summary": "2 results from learn.microsoft.com"
}
```

The `anchor` field identifies the paragraph/section on the source page for UI reference reloading. The `ref_number` field enables citation rendering (e.g., `[Web Ref #1]`).

### Agent Scope Configuration

```yaml
# src/agent/config/internal-search-agent.yaml
name: InternalSearchAgent
description: >
  Searches the internal knowledge base for articles about
  Azure AI Search and Azure Content Understanding.
topics:
  - Azure AI Search
  - Azure Content Understanding
example_questions:
  - "What is agentic retrieval in Azure AI Search?"
  - "How does Azure Content Understanding analyze images?"
```

The system prompt is a **template** that interpolates scope from this file — changing topics or description requires only a YAML edit. The orchestrator also references this config to build its triage logic.

### Whitelist Configuration

```yaml
# src/mcp-web-search/config/whitelist.yaml
allowed_sites:
  - learn.microsoft.com
```

The whitelist lives in the **MCP server's** service directory — the agent doesn't need to know the whitelist details. The MCP server enforces filtering at the search level. The web-search-agent's system prompt simply states it searches approved Microsoft documentation sites.

### Handoff Flow

1. User asks a question
2. **Orchestrator** evaluates the topic:
   - Azure AI Search / Content Understanding → handoff to **internal-search-agent**
   - Other Azure topic → handoff to **web-search-agent**
   - Non-Azure → polite decline (no handoff)
3. Specialist agent executes its tool, streams response
4. If internal-search-agent's results are insufficient, the orchestrator may escalate to web-search-agent for supplementary data
5. AG-UI events include `STEP_STARTED`/`STEP_FINISHED` and `ACTIVITY_SNAPSHOT` for executor transitions; `author_name` is set on specialist agent messages for future CopilotKit native rendering

---

## Stories

### Story 1 — Refactor Single Agent into Internal-Search-Agent

> **Status:** ✅ Done
> **Depends on:** —

Rename and scope the existing `KBSearchAgent` to become `internal-search-agent`.

#### Deliverables

- [ ] Rename agent `name` to `InternalSearchAgent` and `id` to `internal-search-agent`
- [ ] Create `src/agent/config/internal-search-agent.yaml` defining the agent's scope (topics it covers, description, example questions). The system prompt template references this config so scope changes require only a YAML edit, not a code change
- [ ] Scope system prompt to the topics defined in the config file (initially: Azure AI Search & Azure Content Understanding)
- [ ] Move system prompt to `prompts/internal_search_agent/` directory — system prompt is a template that interpolates scope from the config
- [ ] Loader function for the agent scope config (validates required fields, logs scope at startup)
- [ ] Retain `search_knowledge_base` tool, `SecurityFilterMiddleware`, `VisionImageMiddleware`, `GroundingMiddleware`
- [ ] Retain `CompactionProvider` and `InMemoryHistoryProvider` (will move to orchestrator level in Story 6)
- [ ] `create_agent()` still works standalone (backward compat during development)
- [ ] All existing agent tests pass with the renamed agent
- [ ] Unit tests for scope config loading and validation

#### Definition of Done

- [ ] Agent name/id updated in `kb_agent.py`
- [ ] `src/agent/config/internal-search-agent.yaml` exists with scope definition
- [ ] System prompt scoped — agent declines questions outside configured topics
- [ ] Changing scope requires only editing the YAML file (no code changes)
- [ ] `cd src/agent && uv run pytest tests/ -o addopts= -m "not uitest"` passes

---

### Story 2 — Create Web-Search-Agent with MCP Tool

> **Status:** ✅ Done
> **Depends on:** Story 3

Create the `web-search-agent` that uses an MCP web search tool.

#### Deliverables

- [ ] New `web_search_agent.py` module with `create_web_search_agent()` factory
- [ ] System prompt: scoped to Azure topics, states it searches approved Microsoft documentation sites (does not need to know the specific whitelist — that's enforced by the MCP server)
- [ ] System prompt file at `prompts/web_search_agent/system_prompt.md`
- [ ] Agent connects to the MCP web search server via `agent-framework` MCP client integration (SSE transport over HTTP)
- [ ] MCP server endpoint configurable via environment variable (`WEB_SEARCH_MCP_ENDPOINT`)
- [ ] `VisionImageMiddleware` attached (web results may reference images)
- [ ] No `SecurityFilterMiddleware` (web search results are public docs)
- [ ] No `GroundingMiddleware` (grounding is specific to internal search result format)
- [ ] Web search results structured per the return schema defined in the Architecture section (source URL + paragraph anchor for UI citation/reload)
- [ ] No compaction providers on this agent — compaction is managed at the orchestrator level (Story 6)
- [ ] Unit tests for the web-search-agent factory construction

#### Definition of Done

- [ ] `create_web_search_agent()` returns a configured `Agent` instance
- [ ] Agent has MCP web search tool connected (SSE transport)
- [ ] Web search results include source URL and paragraph reference ID
- [ ] Tests verify agent construction, middleware, and tool wiring

---

### Story 3 — Create Whitelist Configuration

> **Status:** ✅ Done
> **Depends on:** —

Create the YAML-based site whitelist for the MCP web search server.

#### Deliverables

- [ ] `src/mcp-web-search/config/whitelist.yaml` with initial entry: `learn.microsoft.com`
- [ ] Loader function in the MCP server code
- [ ] Validation: reject empty whitelist, log loaded sites at startup
- [ ] Unit tests for whitelist loading and validation

#### Definition of Done

- [ ] Whitelist loads correctly from YAML
- [ ] Adding/removing sites requires only a YAML edit (no code changes)
- [ ] Tests cover loading, empty-file error, and malformed YAML handling

---

### Story 4 — MCP Web Search Server: Dev Implementation (Fetch/Scrape)

> **Status:** ✅ Done
> **Depends on:** Story 3

Build the dev-mode MCP server that fetches and scrapes whitelisted sites.

#### Deliverables

- [ ] New service directory: `src/mcp-web-search/` with its own `pyproject.toml`
- [ ] MCP server exposing `web_search(query: str) -> str` tool via **SSE transport** (HTTP endpoint, not stdio)
- [ ] Implementation: HTTP fetch of search results from whitelisted domains, extract text content
- [ ] Results structured with: page title, relevant text snippet, source URL, and paragraph anchor (for UI reference/reload)
- [ ] Whitelist enforcement: only fetch from allowed domains (loaded from `config/whitelist.yaml`)
- [ ] Dockerfile for the MCP server Container App
- [ ] Unit tests for the fetch/scrape logic and whitelist filtering

#### Definition of Done

- [ ] MCP server starts standalone: `cd src/mcp-web-search && uv run python -m mcp_web_search` (for dev testing before Docker Compose wiring in Story 8)
- [ ] Agent can connect to the dev MCP server and execute `web_search` tool calls
- [ ] Results match the return schema defined in the Architecture section
- [ ] Non-whitelisted domains are rejected

---

### Story 5 — MCP Web Search Server: Prod Implementation (Bing Grounding)

> **Status:** ✅ Done
> **Depends on:** Story 3

Build the prod-mode MCP server that uses Azure Bing Grounding API.

#### Deliverables

- [ ] Same `src/mcp-web-search/` service with environment-driven implementation switch
- [ ] Prod implementation: calls Bing Web Search API via Azure AI Services
- [ ] Filters Bing results to whitelisted domains using the `site:` operator
- [ ] Uses `DefaultAzureCredential` for Bing API access
- [ ] Shared Dockerfile with dev (single image, behavior selected by `ENVIRONMENT` variable)
- [ ] Bicep module for Bing Search resource (or Cognitive Services multi-service with Bing capability)
- [ ] RBAC role assignment for the MCP server Container App's managed identity

#### Definition of Done

- [ ] Bing Search resource provisioned via `azd provision`
- [ ] MCP server returns Bing-grounded results filtered to whitelisted domains
- [ ] Same `web_search` tool contract as dev implementation
- [ ] Integration test against live Bing API (marked `@pytest.mark.integration`)

---

### Story 6 — Orchestrator Agent with HandoffBuilder

> **Status:** ✅ Done
> **Depends on:** Stories 1, 2

Wire the orchestrator using `HandoffBuilder` with handoff tools to both specialist agents.

#### Deliverables

- [ ] New `orchestrator.py` module with `create_orchestrator()` factory
- [ ] `HandoffBuilder` workflow: orchestrator → internal-search-agent + web-search-agent
- [ ] `agent-framework-orchestrations>=1.0.0b260402` added to `pyproject.toml`
- [ ] Orchestrator system prompt: triage logic, scope boundaries, escalation rules — references internal-search-agent scope config for routing
- [ ] System prompt file at `prompts/orchestrator/system_prompt.md`
- [ ] Handoff tools: `handoff_to_internal_search`, `handoff_to_web_search`
- [ ] Escalation logic: if internal-search-agent's results are insufficient, orchestrator can also invoke web-search-agent
- [ ] Out-of-scope detection: non-Azure questions → polite decline (no handoff)
- [ ] Session continuity: shared session across handoffs via `propagate_session=True`
- [ ] `CompactionProvider` and `InMemoryHistoryProvider` on the orchestrator only — specialist agents are stateless per invocation
- [ ] `ToolResultCompactionStrategy` on the orchestrator compacts tool results from both agents (internal search and web search) while preserving reference IDs
- [ ] Update `main.py`: pass the `HandoffBuilder` directly to `from_agent_framework()` (it natively accepts `WorkflowBuilder`); use `workflow.as_agent()` → `WorkflowAgent` for AG-UI endpoint via `AgentFrameworkAgent`
- [ ] AG-UI endpoint emits handoff events for the CopilotKit UI
- [ ] `/responses` endpoint backward compatibility

#### Definition of Done

- [ ] `create_orchestrator()` returns a `Workflow` wired with both agents via `HandoffBuilder`
- [ ] `main.py` passes `HandoffBuilder` directly to `from_agent_framework()` and uses `workflow.as_agent()` → `WorkflowAgent` for `AgentFrameworkAgent`
- [ ] "What is Content Understanding?" → internal-search-agent handles
- [ ] "How do I use Cosmos DB?" → web-search-agent handles
- [ ] "Tell me about the LA Olympics" → polite decline
- [ ] Handoff events visible in AG-UI SSE stream
- [ ] `/responses` still works for non-AG-UI clients
- [ ] Tests cover routing, handoff, decline, and escalation scenarios

---

### Story 7 — AG-UI Handoff Events in CopilotKit UI

> **Status:** ✅ Done
> **Depends on:** Story 6

Verify and enable AG-UI handoff event rendering in the CopilotKit frontend.

#### Deliverables

- [ ] Verify handoff works end-to-end: specialist agent responses stream correctly through the orchestrator to the CopilotKit UI
- [ ] Verify `author_name` is set on assistant messages from specialist agents (available for future CopilotKit rendering when native support is added)
- [ ] Verify `STEP_STARTED`/`STEP_FINISHED` and `ACTIVITY_SNAPSHOT` events flow in the AG-UI SSE stream (confirmed: these are the events the AG-UI adapter emits for executor transitions — there is no `AGENT_HANDOFF` event type in the current AG-UI protocol)
- [ ] No custom handoff UI rendering in this epic — CopilotKit will surface handoff labels natively when it adds `author_name` rendering in a future version
- [ ] Update welcome screen messaging to reflect the new scope: "Ask me anything about Azure — I can search our internal knowledge base and the web"
- [ ] Conversation starters updated to showcase both agents (e.g., one Content Understanding question, one general Azure question)
- [ ] Web-app tests updated for new welcome text and starters

#### Definition of Done

- [ ] Specialist agent answers arrive correctly in the chat UI (text streams, citations work)
- [ ] `author_name` field is present on assistant messages (verifiable via debug logging)
- [ ] Welcome screen reflects new agent scope
- [ ] `npm test` passes with updated assertions

---

### Story 8 — Infrastructure: MCP Server Container Apps + Bing Search Resource

> **Status:** ✅ Done
> **Depends on:** Story 5

Add infrastructure-as-code for the MCP web search server Container Apps and Bing Search resource.

#### Deliverables

- [ ] Bicep module for MCP web search server Container App (dev + prod configurations)
- [ ] Bicep module for Bing Search resource (prod only)
- [ ] APIM API definition for MCP web search server (prod) — same Entra app registration / audience as the agent APIM endpoint
- [ ] RBAC role assignments for MCP server managed identity (Bing API access)
- [ ] Docker Compose service for dev MCP server (SSE transport endpoint)
- [ ] `azure.yaml` updated with the new MCP server service
- [ ] `MCP_WEB_SEARCH_ENDPOINT` environment variable wired to agent Container App (APIM gateway URL in prod, direct URL in dev)
- [ ] Makefile targets for MCP server logs and deployment

#### Definition of Done

- [ ] `azd provision` creates all resources including Bing Search, MCP Container App, and APIM API
- [ ] `azd deploy --service mcp-web-search` deploys the MCP server
- [ ] Agent Container App connects to MCP server via APIM in prod, directly in dev
- [ ] APIM API proxies MCP requests with JWT validation (same Entra audience as agent)
- [ ] `az bicep build --file infra/azure/infra/main.bicep` succeeds

---

### Story 9 — Web Search Citation References and Proxy API

> **Status:** ✅ Done
> **Depends on:** Stories 2, 4

Enable web search results to be referenced and reloaded from the UI, similar to internal search chunk citations.

#### Deliverables

- [ ] Web search tool results include structured reference IDs: source URL + paragraph/section anchor
- [ ] `search_result_store.py` (or new equivalent) stores web search result references in the session, keyed by tool call ID and ref number
- [ ] `ToolResultCompactionStrategy` compacts web search results to summaries while preserving reference IDs
- [ ] New Next.js API route (e.g., `/api/web-references/[...params]`) that fetches and returns the referenced page section from the source URL
- [ ] References rendered in the UI as clickable citations (e.g., `[Web Ref #1]`) that open a detail view or reload the referenced content
- [ ] Web-app tests for the proxy API and citation rendering

#### Definition of Done

- [ ] Web search results have `ref_number` and `source_url` + `anchor` fields
- [ ] Compacted results retain reference IDs
- [ ] Proxy API fetches and returns the referenced section from the source page
- [ ] Citations in UI are clickable and show the original content
- [ ] Tests cover reference storage, compaction preservation, and proxy API

---

### Story 10 — End-to-End Validation and Documentation

> **Status:** ✅ Done
> **Depends on:** Stories 6, 7, 8, 9

Full system validation and documentation updates.

#### Deliverables

- [ ] Manual E2E validation: all three routing scenarios verified in the CopilotKit UI
- [ ] Architecture spec updated with multi-agent topology diagram
- [ ] ARD-017 documenting the decision to adopt multi-agent handoff
- [ ] Epic 017 deliverables and DoD marked complete
- [ ] `make dev-test` passes cleanly
- [ ] Rename Makefile targets from `agents` (plural) to `agent` (singular) — the agent container is a single virtual agent: `dev-services-agents-up` → `dev-services-agent-up`, `prod-services-agents-up` → `prod-services-agent-up`, and all references (help text, `prod-services-up` dependency list)

#### Definition of Done

- [ ] Content Understanding question → internal-search-agent → answer with citations
- [ ] Cosmos DB question → web-search-agent → answer with web sources and referenceable citations
- [ ] LA Olympics question → polite decline
- [ ] Handoff events visible in CopilotKit UI
- [ ] Multi-turn conversation maintains context across agent handoffs
- [ ] Web search citations reloadable from the UI via proxy API
- [ ] All tests pass (agent + web-app + functions)
- [ ] Docs updated
- [ ] No `*-agents-*` Makefile targets remain — all renamed to `*-agent-*`

---

### Story 11 — README: MCP Server and Multi-Agent Orchestration Patterns

> **Status:** ✅ Done
> **Depends on:** Stories 6, 8

Document two new Core Patterns in the README.

#### Deliverables

- [ ] **Pattern 9: MCP Server as a Tool Backend** — document the pattern of deploying MCP servers as separate Container Apps behind APIM, with environment-specific implementations (dev: fetch/scrape, prod: Bing Grounding) sharing the same tool contract. Highlight APIM in front for auth, rate limiting, and telemetry. Include mermaid diagram showing the agent → APIM → MCP server → Bing/web flow.
- [ ] **Pattern 10: Multi-Agent Handoff Orchestration** — document the `HandoffBuilder` orchestration pattern with triage routing, specialist agents, and shared session continuity. Explain how AG-UI protocol surfaces handoff transitions transparently to the CopilotKit UI without custom rendering. Include mermaid diagram showing orchestrator → specialist agent → tool flow with AG-UI event stream.
- [ ] Update the README intro paragraph to mention multi-agent and web search capabilities
- [ ] Update the Architecture mermaid diagram to show the orchestrator, both agents, and the MCP server

#### Definition of Done

- [ ] Patterns 9 and 10 follow the existing README pattern format (Problem → Pattern → diagram → link to detailed docs)
- [ ] Architecture diagram reflects multi-agent topology
- [ ] README intro mentions multi-agent orchestration and web search
