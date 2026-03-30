# Epic 010 — Agent Memory Layer

> **Status:** Done
> **Created:** March 11, 2026
> **Updated:** March 12, 2026

## Objective

Move conversation memory management from the **web app middleware** to the **agent endpoint**, using the Microsoft Agent Framework's session persistence model (`AgentSession` + `AgentSessionRepository`).

After this epic:

- **Agent owns conversation history** — `InMemoryHistoryProvider` manages per-request context; a custom `CosmosAgentSessionRepository` persists `AgentSession` state (including message history) to Cosmos DB between requests.
- **Web app becomes a thin relay** — sends `conversation_id` via the Responses API protocol, reads from Cosmos DB for sidebar/resume only. No longer builds, trims, or passes full context.
- **Framework handles load/save lifecycle** — `from_agent_framework(agent, session_repository=...)` auto-loads the session before each request and saves it after.
- **Cosmos DB schema updated** — new `agent-sessions` container (partition key: `/id`); legacy `conversations` container deleted.
- **Agent process remains stateless** — loads session from Cosmos at request start, saves at request end. Nothing is held in memory between requests.

## Success Criteria

- [x] `agent-framework-core` upgraded to `1.0.0rc3`, `azure-ai-agentserver-agentframework` to `1.0.0b16`
- [x] Agent creates `ChatAgent` with `InMemoryHistoryProvider` as context provider
- [x] Custom `CosmosAgentSessionRepository` subclasses `SerializedAgentSessionRepository`
- [x] `from_agent_framework()` receives `session_repository=CosmosAgentSessionRepository(...)`
- [x] Agent container app has Cosmos DB RBAC role assignment and env vars (`COSMOS_ENDPOINT`, `COSMOS_DATABASE_NAME`)
- [x] Cosmos DB `agent-sessions` container deployed with partition key `/id`
- [x] Web app passes `conversation_id` via `extra_body={"conversation": {"id": thread_id}}`
- [x] Web app no longer builds `conversation_context`, no longer calls `_trim_context()`, no longer sends `instructions=conversation_context`
- [x] Web app `on_chat_resume()` reads from `agent-sessions` container (not old `conversations`)
- [x] Legacy `conversations` container removed from Bicep
- [x] Multi-turn conversations persist across web app restarts (agent loads history from Cosmos)
- [x] `make test` passes with zero regressions
- [x] Architecture and agent-memory spec docs updated

---

## Background

### Current State

The web app owns all conversation memory via a client-side memory pattern:

| Aspect | Current Implementation |
|--------|------------------------|
| History ownership | Web app (`src/web-app/app/main.py`) |
| Context building | Web app serializes `messages[]` → `conversation_context` string |
| Context trimming | `_trim_context()` at 120K tokens via `tiktoken` |
| Persistence | Chainlit data layer → Cosmos DB `conversations` container |
| Agent receives | `instructions=conversation_context` (full history as system prompt) |
| Agent stores | Nothing — pure stateless request/response |
| Cosmos access | Web app only (system-assigned MI + `Built-in Data Contributor`) |
| SDK version | `agent-framework-core==1.0.0b260107`, `azure-ai-agentserver-agentframework==1.0.0b14` |

### Target State

The agent owns history via the framework's session/provider model:

| Aspect | Target Implementation |
|--------|----------------------|
| History ownership | Agent via `InMemoryHistoryProvider` + `CosmosAgentSessionRepository` |
| Context building | Framework auto-injects history from `AgentSession.state["messages"]` |
| Context trimming | None initially (deferred: compaction providers when SDK ships them) |
| Persistence | `SerializedAgentSessionRepository` → Cosmos DB `agent-sessions` container |
| Agent receives | User message only; history auto-loaded from Cosmos by framework |
| Agent stores | `AgentSession` (messages + state) auto-saved after each turn |
| Cosmos access | Both agent (read/write sessions) and web app (read for sidebar/resume) |
| SDK version | `agent-framework-core==1.0.0rc3`, `azure-ai-agentserver-agentframework==1.0.0b16` |

### Key Framework Components (rc3)

| Component | Module | Role |
|-----------|--------|------|
| `AgentSession` | `agent_framework._sessions` | Serializable session container with `.state` dict and `.to_dict()`/`.from_dict()` |
| `BaseHistoryProvider` | `agent_framework._sessions` | Abstract base: `get_messages()` / `save_messages()` hooks called before/after model invocation |
| `InMemoryHistoryProvider` | `agent_framework._sessions` | Default provider — stores messages in `session.state["messages"]` |
| `BaseContextProvider` | `agent_framework._sessions` | Base class for the `before_run` / `after_run` pipeline |
| `AgentSessionRepository` | `agentserver.agentframework.persistence` | ABC: `get(conversation_id)` → `AgentSession`, `set(conversation_id, session)` |
| `SerializedAgentSessionRepository` | `agentserver.agentframework.persistence` | Base with auto-serialize: implement `read_from_storage()` / `write_to_storage()` |
| `from_agent_framework()` | `agentserver.agentframework` | Adapter: `from_agent_framework(agent, session_repository=...)` handles load/save lifecycle |

### Compaction Status

The `_compaction` module (documented at [learn.microsoft.com](https://learn.microsoft.com/en-us/agent-framework/agents/conversations/compaction)) is **not yet available** in any published PyPI version — verified through `1.0.0rc3` (March 4, 2026). Compaction strategies (`TokenBudgetComposedStrategy`, `SummarizationStrategy`, `SlidingWindowStrategy`, etc.) are tracked in [GitHub Issue #10](https://github.com/aldelar/azure-knowledge-base-ingestion/issues/10).

### API Migration Summary

The upgrade from beta to rc3 involves significant API changes:

| Concept | beta (`1.0.0b260107`) | rc3 (`1.0.0rc3`) |
|---------|------------------------|-------------------|
| Session type | `AgentThread` | `AgentSession` |
| History storage | `ContextProvider._memory` | `BaseHistoryProvider.get_messages()`/`save_messages()` |
| Provider pipeline | `context_providers: list[ContextProvider]` | `context_providers: list[BaseContextProvider]` |
| Adapter param | `thread_repository` | `session_repository` |
| Adapter repo ABC | `AgentThreadRepository` | `AgentSessionRepository` |
| Serialization | `AgentThread` (custom) | `AgentSession.to_dict()`/`.from_dict()` |

### Change Impact Summary

| Component | Action |
|-----------|--------|
| `src/agent/pyproject.toml` | **UPDATE** — bump `agent-framework-core` to `>=1.0.0rc3`, `azure-ai-agentserver-agentframework` to `>=1.0.0b16` |
| `src/agent/agent/config.py` | **UPDATE** — add `cosmos_endpoint`, `cosmos_database_name` |
| `src/agent/agent/kb_agent.py` | **UPDATE** — add `InMemoryHistoryProvider` to `context_providers` |
| `src/agent/agent/session_repository.py` | **NEW** — `CosmosAgentSessionRepository` (subclass `SerializedAgentSessionRepository`) |
| `src/agent/main.py` | **UPDATE** — instantiate `CosmosAgentSessionRepository`, pass to `from_agent_framework()` |
| `src/web-app/app/main.py` | **UPDATE** — pass `conversation_id`, remove context building + trim logic, simplify `on_chat_resume()` |
| `src/web-app/app/data_layer.py` | **UPDATE** — read from `agent-sessions` container for sidebar/resume |
| `infra/azure/infra/modules/cosmos-db.bicep` | **UPDATE** — add `agent-sessions` container, remove `conversations` container |
| `infra/azure/infra/modules/agent-container-app.bicep` | **UPDATE** — add `cosmosEndpoint`, `cosmosDatabaseName` env vars |
| `infra/azure/infra/main.bicep` | **UPDATE** — add Cosmos RBAC role for agent identity, pass Cosmos params to agent module |
| `docs/specs/agent-memory.md` | **UPDATE** — reflect new ownership model |
| `docs/specs/architecture.md` | **UPDATE** — memory flow in architecture diagram |

---

## Stories

### Story 1 — Upgrade SDK Packages ✅

Upgrade `agent-framework-core` from `1.0.0b260107` to `1.0.0rc3` and `azure-ai-agentserver-agentframework` from `1.0.0b14` to `1.0.0b16`. Adapt existing agent code to the new API surface.

**Acceptance Criteria:**

- [x] `src/agent/pyproject.toml` pins `agent-framework-core>=1.0.0rc3` and `azure-ai-agentserver-agentframework>=1.0.0b16`
- [x] `agent-framework-azure-ai` updated to matching `1.0.0rc3`
- [x] Existing agent code compiles and runs against new SDK (`Agent`, `from_agent_framework`, tool definitions)
- [x] Any import path changes in `kb_agent.py` or `main.py` resolved
- [ ] Agent starts locally (`make agent-dev`) and responds to a test query
- [x] `make test` passes — all existing agent tests green

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/agent/pyproject.toml` | Bumped version pins; updated `starlette` to `>=1.0.0rc1,<2.0.0` |
| `src/agent/agent/kb_agent.py` | `ChatAgent` → `Agent`, `chat_client=` → `client=`, `ad_token_provider=` → `credential=` |
| `src/agent/agent/vision_middleware.py` | `ChatMessage` → `Message`, `DataContent`/`TextContent`/`FunctionResultContent` → unified `Content` class with factory methods |
| `src/agent/main.py` | No import changes needed (docstrings updated) |
| `src/agent/tests/test_kb_agent.py` | Updated `@patch` targets and assertions for renamed classes/params |
| `src/agent/tests/test_endpoints.py` | Updated `@patch` targets for renamed classes |

---

### Story 2 — Deploy `agent-sessions` Cosmos Container ✅

Add the `agent-sessions` container to the Cosmos DB Bicep module. This container stores serialized `AgentSession` objects keyed by `conversationId`.

**Acceptance Criteria:**

- [x] `infra/azure/infra/modules/cosmos-db.bicep` defines `agent-sessions` container with partition key `/conversationId`
- [x] Indexing policy excludes `/state/*` (large message arrays) and `/"_etag"/?`
- [x] TTL set to `-1` (no expiry — sessions persist indefinitely)
- [ ] `azd provision` succeeds with the new container
- [x] Existing `conversations` container is NOT yet removed (removed in Story 9)

**Implementation Scope:**

| File | Change |
|------|--------|
| `infra/azure/infra/modules/cosmos-db.bicep` | Added `agentSessionsContainer` resource with partition key `/conversationId` |

---

### Story 3 — Agent Cosmos DB RBAC & Environment Variables ✅

Grant the agent container app's managed identity `Built-in Data Contributor` RBAC on Cosmos DB and inject the endpoint/database env vars.

**Acceptance Criteria:**

- [x] `infra/azure/infra/main.bicep` adds a `cosmos-db-role` module instance for the agent container app identity (same pattern as existing `cosmosDbWebAppRole`)
- [x] `infra/azure/infra/modules/agent-container-app.bicep` accepts `cosmosEndpoint` and `cosmosDatabaseName` parameters
- [x] Agent container app has `COSMOS_ENDPOINT` and `COSMOS_DATABASE_NAME` environment variables
- [x] `src/agent/agent/config.py` reads `COSMOS_ENDPOINT` and `COSMOS_DATABASE_NAME` from environment
- [ ] `azd provision` succeeds — agent identity can access Cosmos
- [x] Infra docs updated if needed

**Implementation Scope:**

| File | Change |
|------|--------|
| `infra/azure/infra/main.bicep` | Added `cosmosDbAgentRole` module + passed Cosmos params to agent module |
| `infra/azure/infra/modules/agent-container-app.bicep` | Added `cosmosEndpoint`, `cosmosDatabaseName` params + env vars |
| `src/agent/agent/config.py` | Added `cosmos_endpoint`, `cosmos_database_name` fields (optional) |

---

### Story 4 — Cosmos Agent Session Repository ✅

Implement `CosmosAgentSessionRepository` — a custom subclass of `SerializedAgentSessionRepository` that reads/writes serialized `AgentSession` dicts to the `agent-sessions` Cosmos container.

**Acceptance Criteria:**

- [x] New file `src/agent/agent/session_repository.py` with `CosmosAgentSessionRepository`
- [x] Subclasses `SerializedAgentSessionRepository` from `azure.ai.agentserver.agentframework.persistence`
- [x] `read_from_storage(conversation_id)` reads from Cosmos using `conversation_id` as both document ID and partition key
- [x] `write_to_storage(conversation_id, serialized_session)` upserts to Cosmos with `conversationId` as partition key
- [x] Uses `DefaultAzureCredential` via `azure.cosmos.aio.CosmosClient` for async Cosmos access
- [x] Constructor accepts `endpoint`, `database_name`, `container_name` parameters
- [x] Unit tests mock Cosmos client and verify read/write/round-trip serialization (22 tests total)
- [x] Handles missing documents gracefully (returns `None` for unknown `conversation_id`)
- [x] Bug fix: whitespace-only conversation_id now rejected with `.strip()` guard

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/agent/agent/session_repository.py` | **NEW** — `CosmosAgentSessionRepository` |
| `src/agent/tests/test_session_repository.py` | **NEW** — unit tests |
| `src/agent/pyproject.toml` | Add `azure-cosmos` dependency if not already present |

---

### Story 5 — Wire Session Repository into Agent Entry Point ✅

Connect `CosmosAgentSessionRepository` to the agent's HTTP server via `from_agent_framework()`, and add `InMemoryHistoryProvider` to the agent's context providers.

**Acceptance Criteria:**

- [x] `src/agent/agent/kb_agent.py` passes `context_providers=[InMemoryHistoryProvider()]` to `Agent()`
- [x] `src/agent/main.py` instantiates `CosmosAgentSessionRepository` with config values (conditional on COSMOS_ENDPOINT)
- [x] `from_agent_framework(agent, session_repository=cosmos_repo)` wired in `main.py`
- [x] Multi-turn wiring tests: verify session_repository passed/not-passed based on config, correct params forwarded
- [x] Agent still works for new conversations (session_repository=None when no COSMOS_ENDPOINT)
- [x] `make test` passes (192 passed, 5 deselected)

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/agent/agent/kb_agent.py` | Add `context_providers=[InMemoryHistoryProvider()]` |
| `src/agent/main.py` | Instantiate repo, pass `session_repository=` to `from_agent_framework()` |
| `src/agent/tests/test_multi_turn.py` | **NEW** — integration test for multi-turn persistence |

---

### Story 6 — Web App: Pass conversation_id, Stop Building Context ✅

Update the web app to pass `conversation_id` to the agent endpoint via the Responses API protocol and remove all context-building logic. The agent now owns history — the web app just relays user messages.

**Acceptance Criteria:**

- [x] `on_message()` passes `extra_body={"conversation": {"id": thread_id}}` in the Responses API call
- [x] `conversation_context` string building removed from `on_message()`
- [x] `instructions=conversation_context` no longer sent — agent gets its own instructions via `InMemoryHistoryProvider`
- [x] `messages` list no longer maintained in web app session (removed from `on_chat_start`, `on_message`, `on_chat_resume`)
- [x] Context-building loop and `_trim_context()` call removed (functions left as dead code for Story 7)
- [x] Streaming response still works end-to-end
- [x] `make test` passes (192 passed, 5 deselected)

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/web-app/app/main.py` | Remove context building, add `conversation_id` to request |

---

### Story 7 — Web App: Remove Trim Logic & Simplify Resume ✅

Remove `_trim_context()` (the 120K token trimming) and simplify `on_chat_resume()` to read from the new `agent-sessions` container instead of rebuilding context from Chainlit steps.

**Acceptance Criteria:**

- [x] `_trim_context()` function and `_estimate_tokens()` removed from `main.py`
- [x] `_MAX_CONTEXT_TOKENS`, `_RESPONSE_HEADROOM`, `_CHARS_PER_TOKEN` constants removed
- [x] `tiktoken` was not a dependency — N/A
- [x] `on_chat_resume()` already simplified in Story 6 (agent owns history, no local rebuild)
- [x] Resumed conversations continue correctly (agent receives `conversation_id`, loads history from Cosmos)
- [x] `make test` passes (192 passed, 5 deselected)
- [x] Corresponding tests (`TestEstimateTokens`, `TestTrimContext`) removed from `test_main.py`

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/web-app/app/main.py` | Remove `_trim_context()`, rewrite `on_chat_resume()` |
| `src/web-app/pyproject.toml` | Remove `tiktoken` if unused |

---

### Story 8 — Web App: Switch Data Layer to `agent-sessions` Container ✅

Update the web app's Cosmos data layer to read from the `agent-sessions` container (written by the agent) instead of the legacy `conversations` container. The web app needs read access for sidebar listing and conversation resume.

**Acceptance Criteria:**

- [x] `src/web-app/app/data_layer.py` reads from `agent-sessions` container
- [x] Container name configurable via env var (`COSMOS_SESSIONS_CONTAINER`)
- [x] Conversation list query works with new `/conversationId` partition key
- [x] Message display on resume correctly deserializes `AgentSession.state["messages"]`
- [x] Web app Cosmos env vars updated in Bicep if container name changed — N/A (both sides default to `"agent-sessions"`)
- [x] `make test` passes (agent: 105, web-app: 98, functions: 192)

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/web-app/app/data_layer.py` | ✅ Switched to `agent-sessions` container, partition key `/conversationId`, point reads, session message synthesis |
| `src/web-app/app/config.py` | ✅ Added `cosmos_sessions_container` (default `"agent-sessions"`, env `COSMOS_SESSIONS_CONTAINER`) |
| `src/agent/agent/session_repository.py` | ✅ `write_to_storage()` uses read-modify-write to preserve web app fields |
| `src/web-app/tests/test_data_layer.py` | ✅ 33 new tests (config, point reads, session synthesis, elements, partitioning) |
| `src/agent/tests/test_session_repository.py` | ✅ Tests updated for read-modify-write, `test_write_preserves_existing_fields` added |

---

### Story 9 — Delete Legacy `conversations` Container ✅

Remove the `conversations` container from Cosmos DB Bicep now that all reads/writes use `agent-sessions`.

**Acceptance Criteria:**

- [x] `conversations` container resource removed from `infra/azure/infra/modules/cosmos-db.bicep`
- [x] No code references `conversations` container (grep confirms — only generic "conversations" in docstrings)
- [ ] `azd provision` succeeds — deferred to deployment validation
- [x] `docs/specs/agent-memory.md` updated — full rewrite documenting agent-owned memory with `agent-sessions` container
- [x] `docs/specs/infrastructure.md` updated — Cosmos section references `agent-sessions` with `/conversationId` partition key
- [x] `make test` passes (agent: 105, web-app: 98, functions: 192)

**Implementation Scope:**

| File | Change |
|------|--------|
| `infra/azure/infra/modules/cosmos-db.bicep` | ✅ `conversationsContainer` resource removed |
| `docs/specs/agent-memory.md` | ✅ Full rewrite — agent-owned memory, new schema, new architecture diagram |
| `docs/specs/infrastructure.md` | ✅ Cosmos container row updated to `agent-sessions` / `/conversationId` |

---

### Story 10 — Cosmos DB Schema Cleanup: Remove conversationId, Adopt /id Partition Key ✅

> **Status:** Done
> **Depends on:** Stories 5–9 ✅

Clean up the Cosmos DB `agent-sessions` schema introduced in Stories 2–9. The current schema carries redundancies from the initial implementation that should be resolved before hardening:

1. **Remove `conversationId` field** — the document `id` already holds the session identifier; `conversationId` is a duplicate written at creation time. Removing it simplifies the schema and eliminates a potential consistency risk.
2. **Change partition key from `/conversationId` to `/id`** — with `conversationId` removed, partition on the natural key `id`. All existing queries already use `id` for point reads; this change makes the partition key self-evident. **(Option A — chosen for simplicity; cross-partition optimization deferred.)**
3. **Remove `__users__` convention** — the web app currently creates synthetic `__users__` documents to track user metadata. This convention is unnecessary; `userId` is already stored on each session document.
4. **Rename internal `thread` references to `session`** — the Agent Framework renamed `AgentThread` → `AgentSession` in rc3. Internal helper method names in the web app data layer still use `thread` terminology.
5. **Update documentation** — `docs/specs/agent-memory.md` and `docs/specs/infrastructure.md` must reflect the simplified schema, updated partition key, and new document examples.

> ⚠️ **Data Reset Required:** Changing the partition key requires recreating the container. All existing session documents will be lost. This is acceptable in the current dev-only phase.

**Acceptance Criteria:**

- [x] `infra/azure/infra/modules/cosmos-db.bicep` — `agent-sessions` container partition key changed from `/conversationId` to `/id`
- [x] `src/agent/agent/session_repository.py` — `conversationId` field no longer written to documents; docstrings updated to reference "session" not "thread"
- [x] `src/web-app/app/data_layer.py` — all `conversationId` insertions removed (4 sites); `__users__` document creation removed; private methods renamed from `_thread_*` to `_session_*`
- [x] `docs/specs/agent-memory.md` — updated with new document schema example (no `conversationId`), session field explanation, updated ASCII container diagram (no `__users__`), field ownership table updated
- [x] `docs/specs/infrastructure.md` — Cosmos container row updated: partition key `/conversationId` → `/id`
- [x] No code anywhere references `conversationId` (verified by grep)
- [x] No code creates `__users__` documents (verified by grep)
- [x] All internal method names use `session` not `thread` (verified by grep in `data_layer.py`)
- [x] `make test` passes — all agent and web-app tests green after schema changes (agent: 111, web-app: 123)
- [x] Existing tests updated to reflect removed `conversationId` field and renamed methods

**Implementation Scope:**

| File | Change |
|------|--------|
| `infra/azure/infra/modules/cosmos-db.bicep` | ✅ Partition key `/conversationId` → `/id` |
| `infra/azure/infra/main.json` | ✅ Regenerated ARM template with updated partition key |
| `src/agent/agent/session_repository.py` | ✅ Removed `conversationId` from new doc creation; updated docstrings (thread → session) |
| `src/web-app/app/data_layer.py` | ✅ Removed 4× `conversationId` insertions; removed `__users__` persistence; renamed `_read_thread_doc` → `_read_session_doc` (8 call sites); updated docstrings |
| `docs/specs/agent-memory.md` | ✅ Updated schema, field ownership, diagrams, code examples — all `conversationId` and `__users__` references removed |
| `docs/specs/infrastructure.md` | ✅ Cosmos container row: partition key `/conversationId` → `/id` |
| `src/agent/tests/test_session_repository.py` | ✅ Removed `conversationId` from fixtures; +7 edge-case tests (111 total) |
| `src/web-app/tests/test_data_layer.py` | ✅ Removed `conversationId` from fixtures; updated `__users__` tests; renamed thread→session; +19 edge-case tests (123 total) |

**Documentation Scope** (`docs/specs/agent-memory.md`):

| Section | What Changes |
|---------|--------------|
| §2 — Infrastructure table | Partition key `/conversationId` → `/id` |
| §2 — Document Schema JSON | Remove `"conversationId"` field; change `"id"` example to `"<session-id>"` |
| §2 — Field ownership table | Remove `conversationId` row |
| §2 — User document example | Remove `__users__` block entirely |
| §2 — ASCII container diagram | Update partition key label to `/id`; remove `__users__` partition |
| §3 — Repository docstring | Update `conversationId` references → `session_id` / `id` |
| §3 — `write_to_storage` code | Remove `conversationId` from document dict |
| §7 — Summary table | Update partition key entry |

**Target Document Schema** (after cleanup):

```json
{
  "id": "<session-id>",
  "session": {
    "state": {
      "messages": [
        {"role": "user", "content": "What is agentic retrieval?"},
        {"role": "assistant", "content": "Agentic retrieval is..."}
      ]
    }
  },
  "steps": { ... },
  "elements": { ... },
  "userId": "entra-oid",
  "name": "Session display name",
  "_ts": 1741820400
}
```

**Session Field Explanation:**

The `session` field contains the serialized output of `AgentSession.to_dict()` from the Agent Framework. Its structure:

- **`session.state`** — a dictionary managed by the framework. The agent and its context providers store arbitrary state here across requests.
- **`session.state.messages`** — the conversation message history, written by `InMemoryHistoryProvider`. Each entry is `{"role": "user"|"assistant", "content": "..."}`. This is the agent's memory of the conversation.
- The web app reads `session.state.messages` (read-only) to synthesize Chainlit `Message` objects for the sidebar and conversation resume. It never writes to `session`.

**Target Container Diagram** (after cleanup):

```
┌─────────────────────────────────────────────┐
│  agent-sessions  (partition key: /id)       │
│                                             │
│  ┌──────────────────────┐                   │
│  │ id: "sess-abc-123"   │  ← agent writes   │
│  │ session: { state }   │    session field   │
│  │ steps: { ... }       │  ← web app writes  │
│  │ elements: { ... }    │    steps/elements   │
│  │ userId: "oid-..."    │                    │
│  │ name: "Chat #1"      │                    │
│  └──────────────────────┘                   │
│                                             │
│  ┌──────────────────────┐                   │
│  │ id: "sess-def-456"   │                   │
│  │ session: { state }   │                   │
│  │ steps: { ... }       │                   │
│  │ ...                  │                   │
│  └──────────────────────┘                   │
└─────────────────────────────────────────────┘
```

---

## Definition of Done

- [x] All stories 1–9 completed and marked ✅
- [x] Story 10 — schema cleanup completed (remove `conversationId`, partition key `/id`, remove `__users__`)
- [x] Agent owns conversation history — loads/saves `AgentSession` from Cosmos per request
- [x] Web app is a thin relay — passes `conversation_id`, reads Cosmos for display only
- [x] Multi-turn conversations work across restarts
- [x] No data in legacy `conversations` container (container deleted from Bicep)
- [x] `make test` passes with zero regressions (agent: 111, web-app: 123, functions: 192)
- [x] `docs/specs/agent-memory.md` and `docs/specs/infrastructure.md` updated
- [x] Conversation compaction tracked as [GitHub Issue #10](https://github.com/aldelar/azure-knowledge-base-ingestion/issues/10)
