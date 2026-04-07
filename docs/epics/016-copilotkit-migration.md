# Epic 016 — CopilotKit Migration with AG-UI Protocol

> **Status:** In Progress
> **Created:** March 27, 2026
> **Updated:** April 3, 2026

## Objective

Replace the **Chainlit** thin client web app with a **CopilotKit** + **Next.js** frontend and enable the **AG-UI protocol** on the agent, delivering a modern, interactive chat experience that showcases tool calls in real time.

After this epic:

- **CopilotKit replaces Chainlit** — the web app is a Next.js application using CopilotKit's prebuilt components (`CopilotChat` or `CopilotSidebar`), adopting native CopilotKit look and feel (not a carbon copy of Chainlit)
- **AG-UI protocol enabled on the agent** — the existing Starlette agent gains an AG-UI endpoint via the `agent-framework-ag-ui` package, streaming structured events (tool calls, text deltas, state updates) to the frontend
- **Real-time tool call visibility** — the `search_knowledge_base` tool call is rendered in the UI as it happens (query, progress, results), using CopilotKit's `useRenderTool` / `useDefaultRenderTool` hooks
- **Copilot Runtime** as backend-for-frontend — a Node.js Copilot Runtime proxies requests from the React frontend to the agent's AG-UI endpoint via `HttpAgent`
- **Image proxy re-implemented** — a Next.js API route downloads images from Azure Blob Storage and serves them to the browser, replacing the Chainlit FastAPI-based proxy
- **Conversation persistence adapted** — the agent continues to own session state via `agent-sessions` Cosmos container; the web app's sidebar/history is powered by a new lightweight persistence layer in the Next.js backend (replacing Chainlit's 3-container DataLayer)
- **Authentication preserved** — Entra ID Easy Auth on the Container App protects the frontend in prod; CopilotKit passes auth headers through to the agent
- **Deployment topology unchanged** — the web app Container App in the existing Container Apps Environment serves the Next.js app (port 3000), the agent Container App is unchanged

## Success Criteria

- [x] Agent exposes AG-UI endpoint alongside existing Responses API
- [x] `agent-framework-ag-ui` package added to agent dependencies
- [x] AG-UI endpoint streams tool call events, text deltas, and run lifecycle events
- [x] Next.js + CopilotKit web app renders chat using native CopilotKit components
- [x] `CopilotChat` (or `CopilotSidebar`) renders with default CopilotKit styling — no Chainlit look recreation
- [x] `search_knowledge_base` tool activity is shown in real time in the chat
- [x] Copilot Runtime routes requests to agent AG-UI endpoint via `HttpAgent`
- [x] Image proxy endpoint (`/api/images/[...path]`) serves blobs from Azure Storage
- [x] Inline images in agent responses render correctly in the CopilotKit chat
- [x] Citations from search results are displayed in the UI (custom component or markdown rendering)
- [x] Conversation starters available on the welcome screen
- [x] Auth: Entra Easy Auth headers are forwarded in prod and local dev works without auth
- [ ] Docker image builds and deploys via `azd deploy --service web-app`
- [x] `docker-compose.dev-services.yml` updated for the new Next.js web app
- [x] Makefile targets (`dev-services-app-up`, `dev-test`, `dev-ui`) work with the new stack
- [x] `azure.yaml` updated for the new web app service
- [x] Architecture spec updated to reflect CopilotKit + AG-UI
- [x] `make dev-test` passes with zero regressions on agent and functions (web-app tests rewritten)
- [x] ARD-016 documents the decision to migrate from Chainlit to CopilotKit
- [x] Multi-turn conversations persist and resume correctly (AG-UI `threadId` maps to agent session `conversation_id`)
- [ ] End-to-end validated: user asks KB question in CopilotKit UI → real-time tool call visible → streamed answer with inline images and citations displayed

## Validation Snapshot

- [x] `make dev-infra-up` succeeds end to end, initializes Cosmos/Azurite, and is idempotent on repeat runs
- [x] `make dev-test` passes cleanly on the repaired local stack
- [x] `az bicep build --file infra/azure/infra/main.bicep` succeeds after the APIM and Cosmos comment updates
- [x] `docker build -t web-app-test src/web-app/` succeeds for the Next.js web app
- [x] `make dev-services-app-up` starts the web-app container on port 3000 and `curl -I http://localhost:3000` returns `200 OK`
- [x] `curl -sS -L -X POST http://localhost:8088/ag-ui/ ...` returns an AG-UI SSE stream with `RUN_STARTED`, `TEXT_MESSAGE_CONTENT`, and `RUN_FINISHED`
- [x] `curl -sS -X POST http://localhost:8088/responses ...` still returns a valid Responses API payload
- [x] Functions tests: `190 passed, 23 skipped`
- [x] Agent tests: `201 passed` including AG-UI, streaming, grounding, citation lookup, and session persistence coverage
- [x] Web-app tests: `62 passed` including auth helpers, conversation routes, image proxy route, local blob fallback coverage, config loading, citation/image transforms, transcript hydration, sidebar CRUD interactions, live-only thinking/collapsible citation coverage, citation markdown table rendering, and same-turn tool-call citation association for final assistant answers
- [ ] Full manual browser E2E validation from the local dev stack is still pending

### Validation Criteria

Before marking this epic as Done, the following end-to-end scenarios must be manually verified:

1. **Local dev stack**: `make dev-services-up` → open `http://localhost:3000` → ask a KB question → see `search_knowledge_base` tool call rendered in real time → receive streamed answer with inline images and `Ref #N` citations
2. **Multi-turn conversation**: send a follow-up question in the same thread → agent recalls context from the previous turn (session loaded from `agent-sessions` Cosmos container via `threadId`)
3. **Conversation resume**: close the browser → reopen → select a previous conversation from the sidebar → previous messages load and the conversation continues with full context
4. **Image rendering**: answer contains `![alt](/api/images/...)` markdown → image loads from the Next.js proxy endpoint
5. **Agent Responses API unaffected**: `curl -X POST http://localhost:8088/responses ...` still returns a valid streamed response (backward compatibility)

---

## Background

### Current State

The web app is a **Chainlit** Python thin client that calls the agent via the OpenAI-compatible Responses API:

| Aspect | Current Implementation |
|--------|------------------------|
| Framework | Chainlit (Python) |
| Protocol | OpenAI Responses API (SSE via `client.responses.create(stream=True)`) |
| Language | Python 3.11 |
| Components | `cl.Message`, `cl.Text` side panels, `cl.Starter` |
| Tool visibility | None — tool calls are hidden; only post-processed citations shown |
| Streaming | Socket.IO (Chainlit) + SSE (Responses API) — requires 120s ping timeout workaround |
| Image proxy | FastAPI route at `/api/images/...` inside Chainlit app |
| Persistence | Custom `CosmosDataLayer(BaseDataLayer)` — 3 containers (conversations, messages, references) |
| Auth | Chainlit OAuth callback + header auth callback; Entra Easy Auth in prod |
| Port | 8080 |
| Dockerfile | Python 3.11-slim, `chainlit run app/main.py` |

### Target State

The web app is a **CopilotKit** + **Next.js** application communicating with the agent via the AG-UI protocol:

| Aspect | Target Implementation |
|--------|----------------------|
| Framework | CopilotKit v2 + Next.js (React) |
| Protocol | AG-UI protocol (event-based SSE) |
| Language | TypeScript / Node.js 20+ |
| Components | `CopilotChat` or `CopilotSidebar` (native CopilotKit look) |
| Tool visibility | Real-time — `useRenderTool` shows `search_knowledge_base` executing |
| Streaming | AG-UI events → CopilotKit (native SSE, no Socket.IO) |
| Image proxy | Next.js API route at `/api/images/[...path]` |
| Persistence | Lightweight Cosmos DB layer in Next.js API routes for sidebar history |
| Auth | `<CopilotKit headers={{ Authorization: token }}>` + Entra Easy Auth |
| Port | 3000 |
| Dockerfile | Node.js 20-slim, `next start` |

### Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **AG-UI on agent, not replacing Responses API** | The agent gains a new AG-UI endpoint via `add_agent_framework_fastapi_endpoint`. The existing `/responses` endpoint stays for backward compatibility and other consumers (Foundry registration, testing). |
| 2 | **Copilot Runtime as BFF** | The Copilot Runtime runs in the Next.js process, providing auth forwarding, agent routing, and AG-UI middleware. This is the recommended CopilotKit architecture and keeps agent endpoints server-side. |
| 3 | **Native CopilotKit look** | Use default CopilotKit styles and components — `CopilotChat` with slot-based customization only for branding (colors, labels). No attempt to recreate Chainlit's layout or interaction model. |
| 4 | **`useRenderTool` for search tool** | The `search_knowledge_base` tool call is rendered with a custom React component showing search progress and results in real time. This is the primary UX upgrade over Chainlit. |
| 5 | **Next.js API route for image proxy** | Replaces the Python FastAPI proxy. Uses `@azure/storage-blob` + `@azure/identity` (`DefaultAzureCredential`) to download blobs server-side. Same-origin pattern eliminates CORS/CSP issues. |
| 6 | **Simplified conversation persistence** | Drop Chainlit's 3-container DataLayer. Agent still owns `agent-sessions`. The new web app stores minimal sidebar metadata (thread list, titles) in the existing `conversations` Cosmos container via a lightweight API route. Messages are owned by the agent session — no web-app-side message storage needed. |
| 7 | **Preserve deployment topology** | The web app Container App stays in the same CAE. Only the Docker image and port change. Bicep module updated for port 3000 and Node.js base image. Easy Auth config unchanged. |
| 8 | **`agent-framework-ag-ui` package** | The official Python AG-UI adapter for Agent Framework. `add_agent_framework_fastapi_endpoint(app, agent, "/ag-ui")` wires up SSE streaming, tool call events, state snapshots — zero custom protocol work. |

### Change Impact Summary

| Component | Action |
|-----------|--------|
| `src/agent/pyproject.toml` | **ADD** `agent-framework-ag-ui` dependency |
| `src/agent/main.py` | **ADD** AG-UI endpoint registration alongside existing Responses API |
| `src/web-app/` | **REWRITE** — entire directory becomes a Next.js + CopilotKit project |
| `src/web-app/package.json` | **NEW** — Node.js dependencies (next, react, @copilotkit/react-core, @copilotkit/runtime, @ag-ui/client, @azure/storage-blob, @azure/identity, @azure/cosmos) |
| `src/web-app/Dockerfile` | **REWRITE** — Node.js 20 base, `next build` + `next start` |
| `src/web-app/pyproject.toml` | **DELETE** — no longer a Python project |
| `src/web-app/.chainlit/` | **DELETE** — Chainlit config |
| `src/web-app/chainlit.md` | **DELETE** — Chainlit welcome markdown |
| `src/web-app/app/` (Python) | **DELETE** — replaced by Next.js `app/` directory |
| `src/web-app/tests/` | **REWRITE** — Jest/Vitest tests for the new Next.js app |
| `docker-compose.dev-services.yml` | **UPDATE** — web-app service uses Node.js Dockerfile, port 3000 |
| `azure.yaml` | **UPDATE** — web-app service language changes to `js` or `docker` |
| `infra/modules/container-app.bicep` | **UPDATE** — target port 3000, remove Chainlit-specific env vars |
| `Makefile` | **UPDATE** — dev-setup installs npm deps, dev-test runs Jest instead of pytest for web-app |
| `docs/specs/architecture.md` | **UPDATE** — replace Chainlit references with CopilotKit + AG-UI |
| `docs/ards/ARD-016-copilotkit-migration.md` | **NEW** — architecture decision record |
| `.env.dev.template` | **UPDATE** — remove Chainlit env vars, add any CopilotKit-specific vars |
| `src/web-app/.env.sample` | **REWRITE** — Node.js env var names |

---

## Stories

---

### Story 1 — AG-UI Endpoint on the Agent

> **Status:** Completed
> **Depends on:** None

Add the `agent-framework-ag-ui` package to the agent and register an AG-UI endpoint alongside the existing Responses API. The agent becomes dual-protocol: Responses API at `/responses` and AG-UI SSE at `/ag-ui`.

#### Deliverables

- [x] `agent-framework-ag-ui` added to `src/agent/pyproject.toml` dependencies
- [x] AG-UI endpoint registered in `src/agent/main.py`
- [x] AG-UI endpoint coexists with `from_agent_framework` Starlette routes on the same server
- [x] The AG-UI adapter receives the same `Agent` instance (with tools, session repo, middleware)
- [x] AG-UI endpoint streams text, tool, and run lifecycle events
- [x] `search_knowledge_base` tool calls stream through the AG-UI event flow
- [x] AG-UI `threadId` correctly maps to the session repository's `conversation_id` — multi-turn conversations persist across requests
- [x] Existing `/responses` endpoint unaffected — agent tests pass without regressions
- [x] Manual verification: curl/httpie against `/ag-ui` returns SSE event stream

#### Notes

- The `from_agent_framework` adapter creates a Starlette app. The AG-UI adapter uses FastAPI. These need to be composed (mount FastAPI as a sub-app on the Starlette app, or switch the whole server to FastAPI with the existing routes mounted).
- The session repository, vision middleware, and security filter middleware must all work through the AG-UI path — verify that `add_agent_framework_fastapi_endpoint` passes the agent with all middleware intact.
- Regression repair (2026-03-31): the mounted `/ag-ui` app now wraps the shared agent with the same session repository used by `from_agent_framework`. The earlier mount only enabled Cosmos persistence on the Responses adapter, which left AG-UI traffic unable to read or write `agent-sessions` for sidebar thread UUIDs during local resume flows.
- JWT authentication on the AG-UI endpoint must be maintained — use FastAPI `dependencies` parameter.
- **Critical: thread/session mapping** — The Responses API passes `conversation_id` via `extra_body.conversation.id`. The AG-UI protocol uses `threadId` in its run request. Verify that the `agent-framework-ag-ui` adapter maps `threadId` → the session repository's `conversation_id` parameter. If it doesn't, this is a blocker — a custom wrapper or adapter configuration will be needed. Spike this before proceeding to Story 2.

#### Definition of Done

- [ ] `cd src/agent && uv run pytest tests/ -o addopts= -m "not uitest"` passes with zero regressions
- [x] `curl -N -X POST http://localhost:8088/ag-ui/ -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"What is Azure AI Search?"}],"threadId":"test-thread-1"}'` returns an SSE stream with `RUN_STARTED`, `TEXT_MESSAGE_CONTENT`, and `RUN_FINISHED` events
- [ ] A second request with the same `threadId` returns an answer that references the previous turn (session persistence works)
- [x] `curl -X POST http://localhost:8088/responses ...` (existing Responses API) still works unchanged

---

### Story 2 — Next.js + CopilotKit Project Scaffold

> **Status:** Completed
> **Depends on:** None (parallel with Story 1)

Create the new Next.js + CopilotKit web app project structure, replacing the Chainlit Python project. The new project should use CopilotKit's default styling with minimal customization.

#### Deliverables

- [x] `src/web-app/` restructured as a Next.js project (App Router)
- [x] `package.json` with dependencies: `next`, `react`, `@copilotkit/react-core`, `@copilotkit/runtime`, `@ag-ui/client`, `@azure/storage-blob`, `@azure/identity`, `@azure/cosmos`
- [ ] `tsconfig.json`, `next.config.ts`, `tailwind.config.ts` (if using Tailwind — CopilotKit's default)
- [ ] Root layout imports `@copilotkit/react-ui/v2/styles.css`
- [ ] CopilotKit provider wraps the app: `<CopilotKit runtimeUrl="/api/copilotkit">`
- [ ] `CopilotChat` component renders on the main page with welcome message and conversation starters
- [ ] Copilot Runtime API route at `app/api/copilotkit/route.ts` with `ExperimentalEmptyAdapter`
- [ ] `HttpAgent` registered as `"default"` agent pointing at the agent's AG-UI endpoint
- [ ] `.env.local` / `.env.sample` with `AGENT_ENDPOINT` and other required vars
- [ ] App builds and runs locally (`npm run dev`) showing the CopilotKit chat interface
- [ ] Old Chainlit files removed: `pyproject.toml`, `uv.lock`, `.chainlit/`, `chainlit.md`, `app/` (Python), `public/` (Chainlit assets)

#### Definition of Done

- [ ] `cd src/web-app && npm install` completes without errors
- [ ] `cd src/web-app && npm run dev` starts the app on `http://localhost:3000`
- [ ] CopilotKit chat interface renders with welcome message and conversation starters
- [ ] All old Chainlit files deleted — no `.py`, `.chainlit/`, `chainlit.md`, `uv.lock` remain in `src/web-app/`

---

### Story 3 — Real-Time Tool Call Rendering

> **Status:** Not Started
> **Depends on:** Story 1, Story 2

Implement `useRenderTool` for the `search_knowledge_base` tool to display the agent's search activity in real time. This is the primary UX improvement over Chainlit.

#### Deliverables

- [ ] `useRenderTool({ name: "search_knowledge_base", render: ... })` registered in the main content area
- [ ] Tool call "in progress" state shows: search query, loading animation
- [ ] Tool call "complete" state shows: number of results found, article titles, brief summary
- [ ] `useDefaultRenderTool` added as a catch-all for any other tool calls
- [ ] Rendering uses CopilotKit's native component patterns (no custom CSS framework)
- [ ] Tool call rendering integrates smoothly with the streaming text response

#### Definition of Done

- [ ] Ask "What is Azure AI Search?" → `search_knowledge_base` tool call appears in the chat with query and loading state
- [ ] After tool completes, results summary (article titles, result count) renders in the chat
- [ ] Agent's text answer streams in below/after the tool call rendering
- [ ] Any unexpected tool calls show a generic fallback via `useDefaultRenderTool`

---

### Story 4 — Image Proxy & Inline Image Rendering

> **Status:** Completed
> **Depends on:** Story 2

Re-implement the image proxy endpoint in Next.js and ensure inline images from agent responses render correctly in the CopilotKit chat.

#### Deliverables

- [x] Next.js API route at `app/api/images/[...path]/route.ts`
- [x] Uses `@azure/storage-blob` `BlobServiceClient` + `@azure/identity` `DefaultAzureCredential` to download blobs
- [x] Returns blob content with correct content-type header and `Cache-Control: public, max-age=3600`
- [x] For local dev (Azurite): uses connection string from env var
- [ ] Agent responses containing `![alt](/api/images/...)` markdown render as inline images in the chat
- [x] Image URL normalization for common LLM URL patterns (hallucinated domains, missing leading slash, `attachment:` prefix) — simplified version of the existing Python normalizer, implemented as a post-processing step or CopilotKit message transform

#### Notes

- Regression repair (2026-04-03): the web-app image proxy now keeps `/api/images/...` as the browser-facing path but falls back to checked-in `kb/serving` assets during local dev/test when the backing blob content is unavailable, which restores inline images inside expanded citation Ref blocks without bypassing the same-origin backend proxy.
- Docker parity repair (2026-04-03): the local `web-app` container still runs `NODE_ENV=production`, so the dev fallback is now keyed off `ENVIRONMENT=dev` and the compose service mounts `./kb/serving` into `/app/kb/serving` read-only. That restores the same image-proxy behavior in `make dev-services-app-up` that already worked in `make dev-ui-live`.
- Citation/image repair (2026-04-03): the agent runtime still emits search tool payloads with `ref_number` and `/api/images/...`, but current AG-UI turns can split the tool-call assistant message from the final assistant answer. The web renderer now associates search citations across the whole assistant/tool block for the current turn, inserts any missing `Ref #N` markers inline into the relevant paragraph, and places fallback proxy-backed images inline instead of appending a `Sources:` footer.

#### Definition of Done

- [x] `curl http://localhost:3000/api/images/{article_id}/images/{file.png}` returns an image with correct content-type
- [ ] With Azurite running, the proxy downloads from the local emulator (dev mode)
- [ ] An agent answer containing `![alt](/api/images/...)` renders the image inline in the CopilotKit chat
- [ ] An agent answer with a hallucinated domain URL (e.g., `https://learn.microsoft.com/api/images/...`) is normalized to `/api/images/...` and renders correctly

---

### Story 5 — Citation Display

> **Status:** Completed
> **Depends on:** Story 3

Display search citations in the CopilotKit chat. Replace Chainlit's `cl.Text` side-panel elements with CopilotKit-native rendering.

#### Deliverables

- [x] Citations from `search_knowledge_base` tool output displayed as expandable sections or links below the answer
- [x] Each citation shows: article title, section header, content preview
- [x] Citation component uses CopilotKit patterns (custom component via `useRenderTool` result rendering, or a dedicated React component)
- [x] `Ref #N` markers in agent text link to the corresponding citation
- [x] Inline images in citation content render via the image proxy

#### Notes

- The current system does complex post-processing (ref expansion, normalization, dedup). In the CopilotKit world, much of this may be simpler because the tool call output events contain structured data that can be directly rendered as React components.
- Evaluate whether citations are best rendered via the tool-rendering system or as part of the text message post-processing.
- Regression repair (2026-04-03): citation cards now restore from AG-UI `function_call` / `function_result` content blocks, default to collapsed state, and render the expanded citation body as markdown so hyperlinks and inline images survive resume flows.
- Regression repair (2026-04-03): expanded citation markdown now renders inline images as block-level content with sane sizing and applies dedicated table styling/wrapping so article diagrams and markdown comparison tables read correctly inside Ref cards.

#### Definition of Done

- [x] Agent answer includes `Ref #1`, `Ref #2` markers → each links/scrolls to the corresponding citation card
- [x] Citation cards show article title, section header, and a content preview
- [x] Citations with images render those images via the proxy endpoint

---

### Story 6 — Conversation Persistence & History Sidebar

> **Status:** Completed
> **Depends on:** Story 2

Implement lightweight conversation persistence so users can see and resume previous conversations.

#### Deliverables

- [x] Next.js API routes for conversation CRUD: list conversations (sidebar), create conversation, get conversation
- [x] Conversations stored in the existing `conversations` Cosmos container (partition key `/userId`)
- [x] Uses `@azure/cosmos` SDK with `DefaultAzureCredential` (prod) or emulator key (dev)
- [x] Auto-title from first user message (80 chars max), matching current behavior
- [x] Conversation list displayed in a sidebar or thread selector
- [x] Selected conversation passes `thread_id` / `conversation_id` to the agent via AG-UI thread context
- [x] Agent loads session state from `agent-sessions` container based on the thread ID (existing behavior)
- [x] **Conversation resume**: when a user selects a previous conversation, previous messages are hydrated into the CopilotKit chat
- [x] Message hydration reads from the `agent-sessions` container (which stores the full message history in `session.state["messages"]`) via a Next.js API route, then passes the messages to CopilotKit's initial message state

#### Notes

- The agent already owns session state and history. The web app only needs to store sidebar metadata (title, timestamp, userId) — not individual messages.
- CopilotKit Premium offers a "threads" feature, but for self-hosted deployments, a simple Cosmos-backed API is more appropriate and consistent with the existing architecture.
- **Conversation resume mechanism**: When a user selects a previous conversation from the sidebar, the web app reads the `agent-sessions` document for that `conversation_id` (the agent stores the full message history in `session.state["messages"]`). These messages are then passed to CopilotKit as the initial message state when mounting the chat for that thread. This is the same pattern the current Chainlit app uses in `on_chat_resume()`. A new Next.js API route (`/api/conversations/[id]/messages`) reads from the `agent-sessions` Cosmos container (read-only — the agent owns writes).
- Regression repair (2026-03-31): AG-UI-persisted transcripts can land in `session.state.in_memory.messages`, and the underlying agent may overwrite `service_session_id` with a provider response ID during the turn. Resume hydration now accepts the `in_memory.messages` shape, and the mounted AG-UI path restores the requested conversation ID before saving so sidebar thread UUIDs remain the stable key for both writes and reads.
- Regression repair (2026-04-03): resume hydration also reconstructs assistant tool calls and tool results from persisted AG-UI `contents` blocks, so restored conversations keep the original search activity cards and citation affordances instead of dropping them on reload.
- Sidebar actions now use inline rename on title double-click and a custom confirmation dialog for deletes instead of browser prompt/confirm dialogs.

#### Definition of Done

- [x] Sidebar lists previous conversations for the current user, ordered by most recent
- [x] Creating a new conversation generates a unique thread ID and persists metadata to `conversations` container
- [x] Selecting a previous conversation loads its messages into the CopilotKit chat
- [x] A follow-up message in a resumed conversation includes full prior context (agent session continuity)
- [x] `@azure/cosmos` client correctly connects to both Cosmos emulator (dev) and Azure Cosmos DB (prod)

---

### Story 7 — Authentication

> **Status:** Completed
> **Depends on:** Story 2

Configure authentication for the CopilotKit web app — Entra Easy Auth in prod, auto-accept in dev.

#### Deliverables

- [x] Runtime forwards an Authorization header in prod when available and falls back to managed identity for server-side agent calls
- [x] Token acquisition uses `@azure/identity` or Easy Auth headers (X-MS-CLIENT-PRINCIPAL-ID)
- [x] Local dev: no auth required — agent runs with `REQUIRE_AUTH=false`
- [x] User identity extracted from Easy Auth headers for conversation ownership (userId in sidebar)
- [x] User groups extracted and forwarded to agent via `X-User-Groups` header (for contextual tool filtering)
- [ ] CORS configuration on the Copilot Runtime if needed (same-origin in Container App, may need configuration for local dev)

#### Notes

- **Header propagation through Copilot Runtime**: The `HttpAgent` in the Copilot Runtime may not forward arbitrary custom headers (like `X-User-Groups`) to the agent by default. Verify that the `HttpAgent` configuration supports custom header forwarding, or implement a middleware/wrapper that injects these headers. If `HttpAgent` doesn't support this, the headers may need to be passed via the AG-UI run request metadata instead.
- Easy Auth headers (`X-MS-CLIENT-PRINCIPAL-ID`, `X-MS-CLIENT-PRINCIPAL`) are injected by the Container App platform before reaching the Node.js process — they are available in Next.js API routes via `request.headers`.

#### Definition of Done

- [x] In prod (with Easy Auth): user identity is extracted from `X-MS-CLIENT-PRINCIPAL-ID` and used as `userId` for conversation ownership
- [x] In prod: `X-User-Groups` header reaches the agent and contextual tool filtering works (department-scoped search results)
- [x] In dev: app works without auth — auto-accepts as `local-user`, agent runs with `REQUIRE_AUTH=false`

---

### Story 8 — Docker, Deployment & Infrastructure

> **Status:** In Progress
> **Depends on:** Story 2

Update the Dockerfile, Docker Compose, Bicep, azure.yaml, and Makefile for the new Node.js-based web app.

#### Deliverables

- [x] New `src/web-app/Dockerfile` — Node.js 20-slim base, multi-stage build (deps → build → runtime), `next start` on port 3000
- [x] `docker-compose.dev-services.yml` updated: web-app service builds from new Dockerfile, ports `3000:3000`
- [x] `azure.yaml` updated: web-app service uses `language: docker` (Node.js Docker build)
- [x] `infra/modules/container-app.bicep` updated: `targetPort` changes from 8080 to 3000, remove Chainlit-specific env vars (CHAINLIT_AUTH_SECRET, OAUTH_AZURE_AD_*), add CopilotKit env vars
- [x] Easy Auth redirect URIs updated in `scripts/setup-redirect-uris.sh` for the Next.js Easy Auth callback only
- [x] Makefile targets updated: `dev-setup` installs npm dependencies for web-app, `dev-test` runs appropriate test command for web-app, `dev-ui` echoes correct URL
- [x] `.env.dev.template` updated: remove Chainlit vars, ensure `AGENT_ENDPOINT` points to AG-UI endpoint
- [ ] `azd deploy --service web-app` builds and deploys the new Next.js container successfully
- [x] `infra/modules/apim-agent-api.bicep` updated: add APIM operation for the `/ag-ui` POST endpoint (and the thread-scoped citation lookup endpoint used by the web app)
- [x] Cosmos persistence deployment paths now provision only the active `agent-sessions` and `conversations` containers

#### Notes

- **APIM route for AG-UI**: The current `apim-agent-api.bicep` only defines operations for `/responses`, `/liveness`, `/readiness`. The new `/ag-ui` endpoint needs an APIM operation if the Copilot Runtime routes through APIM in prod. Alternatively, if the Copilot Runtime runs inside the same Container Apps Environment, it can connect to the agent via internal FQDN (`http://agent-{project}-{env}.internal.{cae-domain}:8088/ag-ui`) bypassing APIM entirely. Choose one approach and document it.
- **Cosmos container retirement**: The `messages` and `references` Cosmos containers were owned by the Chainlit DataLayer. After the migration audit confirmed there were no active consumers, they were removed from live IaC and local bootstrap so fresh environments only provision `agent-sessions` and `conversations`.

#### Definition of Done

- [x] `docker build -t web-app-test src/web-app/` succeeds
- [x] `docker-compose -f docker-compose.dev-services.yml up web-app` starts the Next.js container on port 3000
- [ ] `azd deploy --service web-app` completes without errors in a test environment
- [x] `make dev-services-app-up` starts the containerized web app
- [x] `make dev-ui` prints `http://localhost:3000`

---

### Story 9 — Web App Tests

> **Status:** In Progress
> **Depends on:** Stories 2–6

Write tests for the new CopilotKit web app. Replace the existing Chainlit pytest suite with appropriate JavaScript/TypeScript tests.

#### Deliverables

- [x] Test framework set up (Jest or Vitest)
- [x] Unit tests for: image proxy API route, conversation API routes, image URL normalization logic, config loading
- [x] Component tests for: tool rendering component, citation display component
- [ ] Integration test: CopilotKit chat sends message → receives streamed response (mock agent)
- [x] Test configuration in `package.json` scripts
- [x] `make dev-test` runs web-app tests correctly alongside Python tests for agent and functions

#### Definition of Done

- [x] `cd src/web-app && npm test` passes all unit and component tests
- [x] `make dev-test` passes: functions (pytest), agent (pytest), web-app (jest/vitest) — zero regressions
- [x] Test coverage includes: image proxy route, conversation CRUD routes, image URL normalization, tool renderer component, citation component

---

### Story 10 — Documentation & Cleanup

> **Status:** In Progress
> **Depends on:** Stories 1–9

Update all documentation to reflect the CopilotKit + AG-UI architecture. Clean up removed Chainlit artifacts.

#### Deliverables

- [x] `docs/ards/ARD-016-copilotkit-migration.md` created — documents the decision to migrate from Chainlit to CopilotKit with AG-UI
- [x] `docs/specs/architecture.md` updated: replace Chainlit references with CopilotKit + AG-UI, update conversation flow diagram, update image flow diagram, update key design decisions table
- [x] `docs/specs/infrastructure.md` updated: web app container port and tech stack
- [x] `docs/specs/agent-session.md` created as the authoritative spec for canonical agent-owned transcript persistence
- [x] Legacy broad memory spec retired; live docs now point to the session and conversation ownership specs
- [x] `docs/setup-and-makefile.md` updated: new setup instructions (Node.js prereqs, npm install)
- [x] `src/web-app/.env.sample` rewritten for Node.js environment
- [x] `README.md` updated if it references Chainlit
- [ ] Remove any orphaned Chainlit references in other epics/docs (informational, not rewriting history)
- [x] Legacy `messages` and `references` Cosmos containers retired from live IaC, local bootstrap, and current setup docs
- [x] Epic 016 doc updated with completion status

#### Definition of Done

- [x] ARD-016 exists and documents: decision, alternatives considered, rationale, consequences
- [x] `docs/specs/architecture.md` no longer references Chainlit in current-state sections; diagrams show CopilotKit + AG-UI flow
- [x] `docs/specs/infrastructure.md` shows web app as Node.js/Next.js on port 3000
- [x] Current live docs use `agent-session.md` as the authoritative session persistence spec and `conversation-state-model.md` as the ownership-boundary spec
- [x] `grep -r "chainlit" docs/` returns zero hits in specs and setup docs (epics are historical — ok to keep)
- [ ] Epic 016 status updated to `Done` with a Validation Snapshot section

---

## Salvage Addendum

This addendum keeps the original epic body intact and adds the recovery work needed to make the current `epic-016` implementation deliver the same user-visible functionality as `origin/main`, while still showcasing AG-UI reasoning and tool details.

### Main-Branch Review

| Main behavior to preserve | Gap on `epic-016` | Added story |
|---|---|---|
| MAF runtime alignment | RC6 upgrade and event validation still missing | Story 11 |
| Default CopilotKit styling | Current UI is over-customized and brittle | Story 12 |
| Structured transcript fidelity | Resume path flattens messages and drops structure | Story 13 |
| Agent thinking visibility | Reasoning is not rendered in the current UI | Story 14 |
| Live tool transparency | Tool activity is not consistently driven by the real AG-UI event model | Story 15 |
| Citation/ref parity | Dedupe and ref normalization from main are incomplete | Story 16 |
| Image repair/fallback parity | Malformed URL repair and fallback images are incomplete | Story 17 |
| Auth/session context parity | Final user-token/app-identity contract is still ambiguous | Story 18 |
| Starter prompts | First-turn UX parity is not explicitly tracked | Story 19 |
| Sidebar ownership and auto-title | Persistence exists, but parity guarantees are not explicit | Story 20 |
| Resume continuity parity | Loaded history does not yet equal uninterrupted chat fidelity | Story 21 |
| Diagnostics/tests/final validation | Current tests miss runtime regressions and diagnostics remain open | Story 22 |

### Story 11 — Upgrade to MAF RC6 and Revalidate AG-UI

> **Status:** Completed
> **Depends on:** Story 1

Upgrade the agent runtime from RC5 to RC6 and revalidate the AG-UI behavior the frontend depends on.

#### Deliverables

- [x] Upgrade `agent-framework-core` and `agent-framework-azure-ai` to `1.0.0rc6`
- [x] Align `agent-framework-ag-ui` to the latest compatible beta
- [x] Refresh lockfiles and rerun affected agent tests
- [x] Revalidate AG-UI lifecycle, reasoning/tool events, auth dependencies, and `threadId` session mapping on RC6
- [ ] Document the frontend-facing AG-UI event contract used by the web app

#### Definition of Done

- [x] Agent tests pass on RC6
- [x] Manual AG-UI verification shows the expected event stream on RC6
- [x] `/responses` remains unaffected

---

### Story 12 — Strip the UI Back to Bare Default CopilotKit CSS

> **Status:** Completed
> **Depends on:** Story 2

Reset the web app to stock CopilotKit styling before additional UX fixes.

#### Deliverables

- [x] Import the recommended CopilotKit stylesheet path for the current version
- [x] Remove the custom shell that recreates a bespoke chat layout
- [x] Delete deep overrides against CopilotKit internal class names unless strictly required
- [x] Keep only minimal branding tokens, typography, and copy wrappers
- [x] Preserve usable desktop and mobile layout after the reset

#### Definition of Done

- [ ] The app reads visually as default CopilotKit rather than a custom re-skin
- [ ] `globals.css` no longer contains broad overrides of CopilotKit internals

---

### Story 13 — Preserve Full AG-UI Transcript Fidelity

> **Status:** Completed
> **Depends on:** Stories 1 and 6

Define and preserve the structured transcript model needed for both live rendering and resumed threads.

#### Deliverables

- [x] Define the canonical TypeScript shape for assistant, user, tool, and reasoning records
- [x] Preserve structured tool-call and reasoning fields in conversation APIs and hydrators
- [x] Remove lossy message flattening from resume paths
- [x] Ensure live rendering and resumed rendering consume the same model

#### Definition of Done

- [x] Reloading a thread preserves the fields required to replay tool and reasoning state
- [x] The app no longer depends on brittle string-only reconstruction for core transcript behavior

---

### Story 14 — Restore Agent Thinking Visibility

> **Status:** Completed
> **Depends on:** Story 13

Render supported reasoning activity from AG-UI so the UI showcases agent thinking transparently.

#### Deliverables

- [x] Render reasoning events or reasoning-role messages in the chat flow
- [x] Associate reasoning state with the correct assistant turn
- [x] Show clear running/completed states for reasoning blocks
- [x] Persist and replay reasoning artifacts on resumed threads where supported by stored transcript data

#### Definition of Done

- [ ] A live run surfaces reasoning activity before or alongside the final answer
- [ ] Resumed threads retain prior reasoning artifacts where available

---

### Story 15 — Restore Live Tool Transparency From Real AG-UI State

> **Status:** Completed
> **Depends on:** Stories 3 and 13

Make tool rendering depend on the actual AG-UI/CopilotKit event model rather than ad hoc fabricated state.

#### Deliverables

- [x] Wire `search_knowledge_base` rendering to the real live event model
- [x] Show query, running status, and structured results as the tool executes
- [x] Add a generic fallback renderer for unexpected tools
- [x] Avoid duplicate raw tool-result rows while preserving debugging value
- [x] Standardize on one supported integration path for tool rendering

#### Definition of Done

- [ ] The user can watch `search_knowledge_base` execute in real time
- [ ] Tool status is consistent during live streaming and after reload

---

### Story 16 — Restore Citation and Reference Parity

> **Status:** Completed
> **Depends on:** Stories 5 and 15

Bring back the citation behaviors from main that kept references stable and navigable.

#### Deliverables

- [x] Deduplicate citations deterministically
- [x] Normalize and renumber `Ref #N` markers so they match citation cards
- [x] Inject discoverable reference tokens when the model omits them
- [x] Keep citation numbering stable across streaming and resume

#### Definition of Done

- [ ] `Ref #N` markers always resolve to the correct citation card
- [ ] Citation numbering remains stable after dedupe and rehydration

---

### Story 17 — Restore Image URL Repair and Fallback Images

> **Status:** Completed
> **Depends on:** Stories 4 and 16

Port the remaining main-branch image normalization logic so inline images are reliable even when the model output is malformed.

#### Deliverables

- [x] Normalize malformed image URLs, including missing leading slash, hallucinated hostnames, and `attachment:` forms
- [x] Rewrite indexed `[Image: ...](images/...)` references to proxy-backed markdown where needed
- [x] Add fallback inline image injection from citations when the answer omits inline image markdown
- [x] Verify proxy behavior still works in both dev and prod

#### Definition of Done

- [ ] Malformed image URLs still resolve to `/api/images/...`
- [ ] Answers that omit inline image markdown still surface cited images when appropriate

---

### Story 18 — Preserve Auth and Session Context Parity

> **Status:** Completed
> **Depends on:** Stories 7 and 11

Clarify and implement the final auth/session-context contract between Easy Auth, the Copilot Runtime, and the agent.

#### Deliverables

- [x] Decide and document whether the runtime forwards user bearer tokens, uses app identity, or uses a hybrid model
- [x] Preserve Easy Auth user identity extraction for conversation ownership
- [x] Preserve local-dev fallback without auth
- [x] Preserve `X-User-Groups` or equivalent metadata required by contextual tool filtering
- [x] Ensure the chosen contract works for both live chat and resumed threads

#### Definition of Done

- [ ] In prod, user identity and group context reach the agent as intended
- [ ] In dev, the app still works without auth and uses the expected local identity

---

### Story 19 — Restore Starter Prompts and First-Turn UX

> **Status:** Completed
> **Depends on:** Story 2

Bring back the helpful first-turn experience from the original app while keeping the UI lightweight.

#### Deliverables

- [x] Restore starter prompts on the empty-thread state
- [x] Keep the first-turn layout coherent with default CopilotKit styling
- [x] Ensure starter usage aligns with conversation creation and auto-title behavior

#### Definition of Done

- [ ] New sessions show starter prompts before the first message
- [ ] Using a starter prompt creates a normal conversation flow with the correct title behavior

---

### Story 20 — Restore Sidebar CRUD, Ownership, and Auto-Title Parity

> **Status:** Completed
> **Depends on:** Stories 6 and 18

Bring the sidebar behavior up to the ownership and usability expectations set by the original app.

#### Deliverables

- [x] Ensure list/create/read/update/delete operations are ownership-aware
- [x] Preserve auto-title from the first user turn
- [x] Keep most-recent ordering stable
- [x] Verify delete behavior removes only the current user's thread metadata and web-app-owned artifacts

#### Definition of Done

- [ ] Users can create, rename, and delete only their own conversations
- [ ] First-turn auto-title behavior matches the original experience

---

### Story 21 — Restore Resume Fidelity and Multi-Turn Continuity

> **Status:** Completed
> **Depends on:** Stories 13, 18, and 20

Make resumed conversations behave like uninterrupted ones.

#### Deliverables

- [x] Rehydrate full transcript state from `agent-sessions` without dropping reasoning/tool structure
- [x] Preserve follow-up continuity after reload and thread selection
- [x] Ensure resumed threads do not duplicate or reorder prior messages
- [x] Validate ownership checks before loading history

#### Definition of Done

- [ ] Reloading and resuming a thread preserves prior context and UI artifacts
- [ ] A follow-up question in a resumed thread behaves the same as if the thread had never been closed

#### Notes

- Regression repair (2026-04-03): resume hydration now accepts persisted AG-UI tool messages whose `function_result` payload lives in `contents[].result` instead of `contents[].output`, so restored `search_knowledge_base` cards replay as completed with their stored chunk summaries instead of falling back to a stale `Searching` placeholder.

---

### Story 22 — Close Diagnostics, Tests, and Final Validation

> **Status:** In Progress
> **Depends on:** Stories 11–21

Finish the salvage work by making the branch clean, verifiable, and deployable.

#### Deliverables

- [x] Fix the current web-app diagnostic issues, including the `vitest/globals` type configuration problem
- [x] Add unit tests for citation/image normalization, auth helpers, and conversation APIs
- [x] Add integration coverage for live AG-UI event handling and resume fidelity
- [x] Ensure `make dev-test` exercises the web-app alongside agent/functions tests
- [x] Refresh the epic checklist and validation snapshot with actual final status after implementation

#### Definition of Done

- [x] `make dev-test` passes cleanly
- [ ] Local manual E2E passes for reasoning, tool activity, citations, images, auth, starters, sidebar CRUD, and resume
- [ ] The epic can be closed without unresolved parity gaps versus the original app

---

## Conversation Ownership Cleanup Addendum

These follow-on stories capture the cleanup needed after the migration landed so the docs, APIs, and future workflow support all reflect the same ownership model:

- the agent owns the canonical transcript in `agent-sessions`
- the web app owns only lightweight `conversations` metadata
- workflows may keep internal shared or specialist-local state without creating new authoritative transcript stores

### Story 23 — Split Session Persistence from Conversation Ownership Specs

> **Status:** Completed
> **Depends on:** Story 10

Finish the documentation split so `agent-session.md` is the source of truth for agent-owned transcript persistence and `conversation-state-model.md` is the source of truth for ownership boundaries across the UI, AG-UI, workflows, and specialists.

#### Deliverables

- [x] Remove any remaining live-doc claims that the retired broad memory spec is the authoritative implementation spec
- [x] Ensure live docs point to `agent-session.md` for canonical transcript persistence details
- [x] Ensure live docs point to `conversation-state-model.md` for ownership boundaries and workflow semantics
- [x] Leave historical epics and scratchpads intact unless they claim present-day authority
- [x] Make the retired `messages` and `references` containers clearly read as non-runtime artifacts in current docs

#### Definition of Done

- [x] Repository docs no longer point current-state readers at the retired broad memory spec filename
- [x] Current specs no longer describe `messages` or `references` as active runtime stores

### Story 24 — Enforce Metadata-Only `conversations` Ownership

> **Status:** Completed
> **Depends on:** Stories 6, 20, 21, and 23

Audit and tighten the web app conversation layer so `conversations` remains a metadata-only store for sidebar and UI state.

#### Deliverables

- [x] Define the allowed `conversations` schema and ownership contract in code and docs
- [x] Verify Next.js conversation routes write only metadata fields such as thread title, timestamps, ownership, and other basic UI state
- [x] Keep transcript hydration read-only and sourced from `agent-sessions`
- [x] Add regression tests that fail if the web app starts writing transcript, reasoning, or tool history into `conversations`
- [x] Remove any code comments or docs that imply web-app-owned durable message storage

#### Definition of Done

- [x] No web-app write path persists user, assistant, tool, or reasoning transcript content outside `agent-sessions`
- [x] `conversations` remains sufficient for sidebar CRUD, thread selection, and other basic UI state only

### Story 25 — Make Workflow Session Ownership Implementation-Ready

> **Status:** Completed
> **Depends on:** Stories 21, 23, and 24

Prepare the persistence and UI contract for future MAF workflows without introducing a second transcript owner.

#### Deliverables

- [x] Define the top-level workflow-exposed AG-UI agent as the canonical thread owner in workflow mode
- [x] Define how specialist attribution and inline handoff markers are surfaced without splitting the conversation or reassigning canonical ownership
- [x] Define the allowed backend-only workflow shared state and optional specialist-local state
- [x] Ensure all planned workflow UI models continue to bind to one user-visible `threadId`
- [x] Identify any API or schema additions needed for workflow metadata while keeping transcript ownership agent-side

#### Definition of Done

- [x] Workflow mode still has exactly one authoritative transcript per user-visible thread
- [x] Specialist-local state is explicit, optional, backend-owned, and non-canonical
- [x] No planned workflow feature requires the UI to own a durable transcript store

### Story 26 — Finalize Legacy Container Retirement Boundaries

> **Status:** Completed
> **Depends on:** Stories 23 and 24

Close the loop on the old `messages` and `references` model so the runtime and docs stop carrying ambiguity about whether those containers still matter.

#### Deliverables

- [x] Audit active code, scripts, and runtime paths for reads or writes to `messages` and `references`
- [x] If no active consumers remain, document the retirement gap and identify every path still recreating those containers
- [x] Record the follow-up implementation scope needed to remove them from IaC, local bootstrap, and current docs
- [x] Ensure tests and docs reflect no active runtime dependency on those containers

#### Definition of Done

- [x] Active runtime paths do not depend on `messages` or `references`
- [x] The repo has one documented retirement plan for the legacy containers

#### Notes

- Follow-up implementation landed in Story 28 after the live local Cosmos audit showed that the retired containers were still being recreated by Bicep and emulator bootstrap code.

### Story 27 — Compact Stored Search Results and Lazy Citation Enrichment

> **Status:** Completed
> **Depends on:** Stories 21 and 23

Keep resumed conversations lightweight without losing the ability to inspect cited search chunks in the UI.

#### Deliverables

- [x] Persist compact `search_knowledge_base` tool results in `agent-sessions` with stable chunk handles plus summary-sized preview text
- [x] Keep the agent as the only component that resolves chunk handles into full AI Search documents
- [x] Add an agent-owned citation lookup endpoint scoped by `threadId`, `toolCallId`, and `refNumber`
- [x] Add a web-app proxy route that validates conversation ownership before forwarding citation lookup requests to the agent
- [x] Update the CopilotKit citation renderer to show stored summaries immediately and lazily load full excerpts on demand
- [x] Add regression tests for compact persistence, citation lookup authorization boundaries, and lazy citation enrichment

#### Definition of Done

- [x] Resumed threads no longer require full raw chunk content in stored tool results to render citations
- [x] The browser never sends arbitrary chunk handles directly to a search-backed endpoint
- [x] `make dev-test` passes after the compact-result and lazy-enrichment rework

#### Notes

- Regression repair (2026-04-03): compact-result persistence and transcript-scoped citation lookup now also understand tool messages serialized via AG-UI `contents[].function_result.result`, which keeps lazy source enrichment compatible with older or less-normalized stored transcript shapes. Restored compact citations now auto-load the full chunk on first expand, and they only fall back to the stored summary when the backing chunk can no longer be found.

### Story 28 — Retire Legacy Cosmos Containers From IaC and Bootstrap

> **Status:** Completed
> **Depends on:** Stories 8, 10, and 26

Remove the unused Chainlit-era `messages` and `references` containers from every current deployment and bootstrap path so new local and Azure environments provision only the active conversation stores.

#### Deliverables

- [x] Remove `messages` and `references` from `infra/azure/infra/modules/cosmos-db.bicep`
- [x] Regenerate the compiled Azure template so `infra/azure/infra/main.json` no longer declares those containers
- [x] Remove the legacy container names from `.env.dev`, `.env.dev.template`, emulator bootstrap, and clean targets
- [x] Update infrastructure and environment docs to describe only `agent-sessions` and `conversations` as current resources
- [x] Document the Azure cleanup requirement for already-provisioned environments: full teardown/recreate or explicit manual delete, because incremental deployments do not remove orphaned child resources

#### Definition of Done

- [x] Fresh local bootstrap provisions only `agent-sessions` and `conversations` plus their `-test` variants
- [x] `az bicep build --file infra/azure/infra/main.bicep` succeeds and the generated template no longer contains `messages` or `references`
- [x] Current live docs no longer imply the retired containers will be redeployed automatically

### Story 29 — Repair README Agent Memory Documentation

> **Status:** Completed
> **Depends on:** Stories 23 and 28

Repair the README's agent-memory section so it accurately describes the current ownership model, renders without Mermaid parser errors, and points readers at the dedicated memory specs.

#### Deliverables

- [x] Replace the broken README mermaid diagram with a valid diagram showing only the active stores
- [x] Update the section narrative to state that `agent-sessions` is canonical and `conversations` is metadata-only
- [x] Point the section to `docs/specs/agent-session.md` and `docs/specs/conversation-state-model.md`
- [x] Update the README documentation index to include both memory specs under their current filenames

#### Definition of Done

- [x] The README agent-memory section renders without the prior Mermaid parse error
- [x] README readers land on the dedicated memory specs instead of stale or misleading container descriptions

### Story 30 — Upgrade MAF to 1.0 GA and Latest AG-UI Pre-Release ✅

> **Status:** Done
> **Depends on:** Stories 1, 11

Upgrade the Microsoft Agent Framework from RC6 pre-release to the 1.0 GA release and pull in the latest `agent-framework-ag-ui` pre-release. This aligns the project with the stable public API surface and picks up any AG-UI improvements or fixes published after the `1.0.0b260330` beta.

#### Context

The project currently pins:

| Package | Current | Target |
|---|---|---|
| `agent-framework-core` | `>=1.0.0rc6` | `>=1.0.0` (GA, released 2026-04-02) |
| `agent-framework-openai` | (transitive via core) | Explicit dep — extracted from core in RC6 ([#4818](https://github.com/microsoft/agent-framework/pull/4818)) |
| `agent-framework-azure-ai` | `>=1.0.0rc6` | Stays at RC6 — no GA release yet |
| `agent-framework-ag-ui` | `>=1.0.0b260330` | `>=1.0.0b260402` (bumped alongside 1.0 GA in [#5062](https://github.com/microsoft/agent-framework/pull/5062)) |
| `azure-ai-agentserver-agentframework` | `>=1.0.0b17` | Latest compatible pre-release |
| `@ag-ui/client` (npm) | `^0.0.48` | Latest available |

The `[tool.uv]` section contains `override-dependencies` that forced RC6 past `azure-ai-agentserver-agentframework`'s upper-bound pin (`<=rc3`). These overrides should be revisited — the 1.0 GA release may be compatible natively, or the overrides need updating to target `>=1.0.0`. Note: 1.0 GA dependency floors now require `>=1.0.0,<2` for promoted packages, which may conflict with the current override approach.

A [migration guide](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes) is published — read it before starting code changes.

#### Risks

- **Private API breakage** — the agent code imports from internal modules (`agent_framework._middleware`, `agent_framework._compaction`, `agent_framework._sessions`). The 1.0 GA release may have promoted these to public API, renamed them, or removed them. Each import site must be checked and migrated.
- **`Message(text=...)` removal** — 1.0 GA removes the deprecated `text` parameter from the `Message` constructor ([#5062](https://github.com/microsoft/agent-framework/pull/5062)). All `Message()` construction sites must use `Message(contents=[...])` instead.
- **`BaseContextProvider` / `BaseHistoryProvider` alias removal** — 1.0 GA removes these deprecated aliases. If `InMemoryHistoryProvider` or any agent code references them, the migration may be more involved.
- **Package split: `agent-framework-openai`** — RC6 extracted `agent-framework-openai` as a separate package from core ([#4818](https://github.com/microsoft/agent-framework/pull/4818)). `from agent_framework.azure import AzureOpenAIChatClient` and `from agent_framework.openai import OpenAIChatClient` in `client_factories.py` may require this as an explicit dependency. Import paths may also have changed (e.g., `agent_framework.azure` → `agent_framework.foundry`).
- **AG-UI adapter API changes** — `AgentFrameworkAgent` and `add_agent_framework_fastapi_endpoint` signatures may have changed between betas.
- **`azure-ai-agentserver-agentframework` compatibility** — the `from_agent_framework` adapter may need a newer beta to work with core 1.0 without overrides.
- **Agentserver monkeypatch fragility** — `main.py` patches deep internals of `AgentFrameworkOutputStreamingConverter` (null text delta workaround). A newer `azure-ai-agentserver-agentframework` version may have fixed the underlying bug or renamed these internals.
- **npm `@ag-ui/client` protocol changes** — a major bump on the JS side could affect the web-app Copilot Runtime wiring.

#### Deliverables

- [x] Read the official [MAF 1.0 migration guide](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes) before starting code changes
- [x] Bump `agent-framework-core` to `>=1.0.0` in `pyproject.toml`
- [x] Bump `agent-framework-azure-ai` to the latest available version in `pyproject.toml`
- [x] Bump `agent-framework-ag-ui` to `>=1.0.0b260402` (or newer) in `pyproject.toml`
- [x] Bump `azure-ai-agentserver-agentframework` to the latest compatible version in `pyproject.toml`
- [x] Add `agent-framework-openai` (or `agent-framework-foundry`) as explicit dependency if import paths require it after the RC6 package split
- [x] Revisit and update (or remove) `[tool.uv] override-dependencies` — they should no longer be needed if upstream pins are compatible with 1.0
- [x] Migrate any private API imports (`_middleware`, `_compaction`, `_sessions`) to their 1.0 public equivalents
- [x] Audit all `Message()` construction sites for removed `text=` parameter — use `Message(contents=[...])` pattern
- [x] Verify no code depends on removed `BaseContextProvider` / `BaseHistoryProvider` aliases
- [x] Verify `from agent_framework.azure import AzureOpenAIChatClient` and `from agent_framework.openai import OpenAIChatClient` still resolve after the package split — update import paths if needed
- [x] Review `_patch_agentserver_streaming_converter()` monkeypatch in `main.py` — check if the null-text-delta bug is fixed upstream and remove the patch if so
- [x] Test whether the OTel ContextVar cleanup workaround (dev-mode `configure_otel_providers()` skip) can be removed on 1.0
- [x] Bump `@ag-ui/client` in `src/web-app/package.json` to the latest version — **reverted to `^0.0.48`**: 0.0.51 introduced content types (`image`, `audio`) incompatible with CopilotKit 1.54.1's type definitions; must be upgraded together with CopilotKit
- [x] Regenerate lockfiles (`uv lock` for agent, `npm install` for web-app)
- [x] Run the full agent test suite and fix any regressions from API changes
- [x] Run the full web-app test suite and fix any regressions
- [ ] Manually verify AG-UI SSE stream and Responses API still work end-to-end
- [x] Update `requirements.txt` if maintained separately

#### Definition of Done

- [x] `cd src/agent && uv run pytest tests/ -o addopts= -m "not uitest"` passes with zero regressions
- [x] `cd src/web-app && npm test` passes with zero regressions
- [x] `make dev-test` passes cleanly
- [ ] `curl` against `/ag-ui` and `/responses` returns valid event streams
- [x] No `agent_framework._*` private module imports remain in agent code
- [x] No `Message(text=...)` calls remain in agent code
- [x] `_patch_agentserver_streaming_converter()` is either removed (bug fixed upstream) or verified still compatible with the new `azure-ai-agentserver-agentframework` version
- [x] `from_agent_framework()` adapter works with core 1.0 — `/responses` endpoint returns valid streamed responses
- [x] `uv.lock` resolves without override hacks (or overrides are documented as still necessary with rationale)
- [x] `package-lock.json` resolves with `@ag-ui/client` `^0.0.48` (compatible with CopilotKit 1.54.1)