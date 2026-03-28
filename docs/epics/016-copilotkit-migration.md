# Epic 016 — CopilotKit Migration with AG-UI Protocol

> **Status:** In Progress
> **Created:** March 27, 2026
> **Updated:** March 28, 2026

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

- [ ] Agent exposes AG-UI endpoint alongside existing Responses API
- [ ] `agent-framework-ag-ui` package added to agent dependencies
- [ ] AG-UI endpoint streams tool call events, text deltas, and run lifecycle events
- [ ] Next.js + CopilotKit web app renders chat using native CopilotKit components
- [ ] `CopilotChat` (or `CopilotSidebar`) renders with default CopilotKit styling — no Chainlit look recreation
- [ ] `search_knowledge_base` tool calls shown in real-time via `useRenderTool`
- [ ] Copilot Runtime routes requests to agent AG-UI endpoint via `HttpAgent`
- [ ] Image proxy endpoint (`/api/images/[...path]`) serves blobs from Azure Storage
- [ ] Inline images in agent responses render correctly in the CopilotKit chat
- [x] Citations from search results are displayed in the UI (custom component or markdown rendering)
- [ ] Conversation starters available on the welcome screen
- [ ] Auth: Entra Easy Auth works in prod, local dev works without auth
- [ ] Docker image builds and deploys via `azd deploy --service web-app`
- [ ] `docker-compose.dev-services.yml` updated for the new Next.js web app
- [ ] Makefile targets (`dev-services-app-up`, `dev-test`, `dev-ui`) work with the new stack
- [ ] `azure.yaml` updated for the new web app service
- [ ] Architecture spec updated to reflect CopilotKit + AG-UI
- [ ] `make dev-test` passes with zero regressions on agent and functions (web-app tests rewritten)
- [x] ARD-016 documents the decision to migrate from Chainlit to CopilotKit
- [x] Multi-turn conversations persist and resume correctly (AG-UI `threadId` maps to agent session `conversation_id`)
- [ ] End-to-end validated: user asks KB question in CopilotKit UI → real-time tool call visible → streamed answer with inline images and citations displayed

## Validation Snapshot

- [x] `cd src/agent && uv run pytest tests/ -o addopts= -m "not uitest"` passed earlier in the implementation cycle after AG-UI endpoint integration
- [x] `cd src/web-app && npm test` passes with history hydration and citation rendering coverage
- [x] `cd src/web-app && npm run build` passes with `/api/conversations/[threadId]/messages` included in the production app
- [ ] Full manual end-to-end validation from the local dev stack is still pending

### Validation Criteria

Before marking this epic as Done, the following end-to-end scenarios must be manually verified:

1. **Local dev stack**: `make dev-services-up` → open `http://localhost:3000` → ask a KB question → see `search_knowledge_base` tool call rendered in real time → receive streamed answer with inline images and `Ref #N` citations
2. **Multi-turn conversation**: send a follow-up question in the same thread → agent recalls context from the previous turn (session loaded from `agent-sessions` Cosmos container via `threadId`)
3. **Conversation resume**: close the browser → reopen → select a previous conversation from the sidebar → previous messages load and the conversation continues with full context
4. **Image rendering**: answer contains `![alt](/api/images/...)` markdown → image loads from the Next.js proxy endpoint
5. **Agent Responses API unaffected**: `curl -X POST http://localhost:8088/v1/responses ...` still returns a valid streamed response (backward compatibility)

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
| 1 | **AG-UI on agent, not replacing Responses API** | The agent gains a new AG-UI endpoint via `add_agent_framework_fastapi_endpoint`. The existing `/v1/responses` endpoint stays for backward compatibility and other consumers (Foundry registration, testing). |
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
| `src/web-app/package.json` | **NEW** — Node.js dependencies (next, react, @copilotkit/react-core, @copilotkit/runtime, @ag-ui/client, @azure/storage-blob, @azure/identity) |
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

> **Status:** Not Started
> **Depends on:** None

Add the `agent-framework-ag-ui` package to the agent and register an AG-UI endpoint alongside the existing Responses API. The agent becomes dual-protocol: Responses API at `/v1/responses` and AG-UI SSE at `/ag-ui`.

#### Deliverables

- [ ] `agent-framework-ag-ui` added to `src/agent/pyproject.toml` dependencies
- [ ] `add_agent_framework_fastapi_endpoint` called in `src/agent/main.py` to register `/ag-ui` endpoint
- [ ] AG-UI endpoint coexists with `from_agent_framework` Starlette routes on the same server
- [ ] The AG-UI adapter receives the same `Agent` instance (with tools, session repo, middleware)
- [ ] AG-UI events stream correctly: `RUN_STARTED`, `TEXT_MESSAGE_*`, `TOOL_CALL_*`, `RUN_FINISHED`
- [ ] `search_knowledge_base` tool calls emit `TOOL_CALL_START`, `TOOL_CALL_ARGS`, `TOOL_CALL_END` events
- [ ] AG-UI `threadId` correctly maps to the session repository's `conversation_id` — multi-turn conversations persist across requests
- [ ] Existing `/v1/responses` endpoint unaffected — `make dev-test` on agent passes without regressions
- [ ] Manual verification: curl/httpie against `/ag-ui` returns SSE event stream

#### Notes

- The `from_agent_framework` adapter creates a Starlette app. The AG-UI adapter uses FastAPI. These need to be composed (mount FastAPI as a sub-app on the Starlette app, or switch the whole server to FastAPI with the existing routes mounted).
- The session repository, vision middleware, and security filter middleware must all work through the AG-UI path — verify that `add_agent_framework_fastapi_endpoint` passes the agent with all middleware intact.
- JWT authentication on the AG-UI endpoint must be maintained — use FastAPI `dependencies` parameter.
- **Critical: thread/session mapping** — The Responses API passes `conversation_id` via `extra_body.conversation.id`. The AG-UI protocol uses `threadId` in its run request. Verify that the `agent-framework-ag-ui` adapter maps `threadId` → the session repository's `conversation_id` parameter. If it doesn't, this is a blocker — a custom wrapper or adapter configuration will be needed. Spike this before proceeding to Story 2.

#### Definition of Done

- [ ] `cd src/agent && uv run pytest tests/ -o addopts= -m "not uitest"` passes with zero regressions
- [ ] `curl -N -X POST http://localhost:8088/ag-ui -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"What is Azure AI Search?"}],"threadId":"test-thread-1"}'` returns an SSE stream with `RUN_STARTED`, `TEXT_MESSAGE_CONTENT`, and `RUN_FINISHED` events
- [ ] A second request with the same `threadId` returns an answer that references the previous turn (session persistence works)
- [ ] `curl -X POST http://localhost:8088/v1/responses ...` (existing Responses API) still works unchanged

---

### Story 2 — Next.js + CopilotKit Project Scaffold

> **Status:** Not Started
> **Depends on:** None (parallel with Story 1)

Create the new Next.js + CopilotKit web app project structure, replacing the Chainlit Python project. The new project should use CopilotKit's default styling with minimal customization.

#### Deliverables

- [ ] `src/web-app/` restructured as a Next.js project (App Router)
- [ ] `package.json` with dependencies: `next`, `react`, `@copilotkit/react-core`, `@copilotkit/runtime`, `@ag-ui/client`, `@azure/storage-blob`, `@azure/identity`, `@azure/cosmos`
- [ ] `tsconfig.json`, `next.config.ts`, `tailwind.config.ts` (if using Tailwind — CopilotKit's default)
- [ ] Root layout imports `@copilotkit/react-ui/v2/styles.css`
- [ ] CopilotKit provider wraps the app: `<CopilotKit runtimeUrl="/api/copilotkit">`
- [ ] `CopilotChat` component renders on the main page with welcome message and conversation starters
- [ ] Copilot Runtime API route at `app/api/copilotkit/route.ts` with `ExperimentalEmptyAdapter`
- [ ] `HttpAgent` registered as `"default"` agent pointing at the agent's AG-UI endpoint
- [ ] `.env.local` / `.env.sample` with `AGENT_ENDPOINT` and other required vars
- [ ] App builds and runs locally (`npm run dev`) showing the CopilotKit chat interface
- [ ] Old Chainlit files removed: `pyproject.toml`, `uv.lock`, `.chainlit/`, `chainlit.md`, `app/` (Python), `public/` (Chainlit assets)

#### Target Source Layout

```
src/web-app/
├── package.json                         # Node.js dependencies
├── tsconfig.json                        # TypeScript config
├── next.config.ts                       # Next.js config
├── tailwind.config.ts                   # Tailwind CSS (CopilotKit default)
├── postcss.config.js                    # PostCSS for Tailwind
├── Dockerfile                           # Node.js 20, multi-stage build
├── .env.sample                          # Required env vars
├── .env.local                           # Local dev overrides (gitignored)
│
├── app/                                 # Next.js App Router
│   ├── layout.tsx                       # Root layout — CopilotKit provider + styles
│   ├── page.tsx                         # Main page — CopilotChat + useRenderTool
│   ├── globals.css                      # Tailwind base styles
│   │
│   └── api/
│       ├── copilotkit/
│       │   └── route.ts                 # Copilot Runtime — HttpAgent → agent AG-UI
│       ├── images/
│       │   └── [...path]/
│       │       └── route.ts             # Image proxy — blob download from Azure Storage
│       └── conversations/
│           └── route.ts                 # Conversation CRUD — Cosmos DB sidebar metadata
│
├── components/
│   ├── SearchToolRenderer.tsx           # useRenderTool for search_knowledge_base
│   └── CitationDisplay.tsx              # Expandable citation cards
│
├── lib/
│   ├── config.ts                        # Env-aware configuration
│   ├── cosmos.ts                        # Cosmos DB client factory (dev/prod)
│   └── blob.ts                          # Blob storage client factory (dev/prod)
│
├── public/                              # Static assets (favicon, logo)
│
└── __tests__/                           # Jest/Vitest tests
    ├── image-proxy.test.ts
    ├── conversations.test.ts
    └── components/
        └── SearchToolRenderer.test.tsx
```

#### Notes

- Agent endpoint URL comes from `AGENT_ENDPOINT` env var (same pattern as current Chainlit app)
- For local dev, the runtime points at `http://localhost:8088/ag-ui`
- For prod, the runtime points at the APIM gateway URL (or internal Container App FQDN)

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

> **Status:** Not Started
> **Depends on:** Story 2

Re-implement the image proxy endpoint in Next.js and ensure inline images from agent responses render correctly in the CopilotKit chat.

#### Deliverables

- [ ] Next.js API route at `app/api/images/[...path]/route.ts`
- [ ] Uses `@azure/storage-blob` `BlobServiceClient` + `@azure/identity` `DefaultAzureCredential` to download blobs
- [ ] Returns blob content with correct content-type header and `Cache-Control: public, max-age=3600`
- [ ] For local dev (Azurite): uses connection string from env var
- [ ] Agent responses containing `![alt](/api/images/...)` markdown render as inline images in the chat
- [ ] Image URL normalization for common LLM URL patterns (hallucinated domains, missing leading slash, `attachment:` prefix) — simplified version of the existing Python normalizer, implemented as a post-processing step or CopilotKit message transform

#### Definition of Done

- [ ] `curl http://localhost:3000/api/images/{article_id}/images/{file.png}` returns an image with correct content-type
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

#### Definition of Done

- [x] Sidebar lists previous conversations for the current user, ordered by most recent
- [x] Creating a new conversation generates a unique thread ID and persists metadata to `conversations` container
- [x] Selecting a previous conversation loads its messages into the CopilotKit chat
- [x] A follow-up message in a resumed conversation includes full prior context (agent session continuity)
- [x] `@azure/cosmos` client correctly connects to both Cosmos emulator (dev) and Azure Cosmos DB (prod)

---

### Story 7 — Authentication

> **Status:** Not Started
> **Depends on:** Story 2

Configure authentication for the CopilotKit web app — Entra Easy Auth in prod, auto-accept in dev.

#### Deliverables

- [ ] `<CopilotKit headers={{ Authorization: ... }}>` passes Entra bearer token in prod
- [ ] Token acquisition uses `@azure/identity` or Easy Auth headers (X-MS-CLIENT-PRINCIPAL-ID)
- [ ] Local dev: no auth required — agent runs with `REQUIRE_AUTH=false`
- [ ] User identity extracted from Easy Auth headers for conversation ownership (userId in sidebar)
- [ ] User groups extracted and forwarded to agent via `X-User-Groups` header (for contextual tool filtering)
- [ ] CORS configuration on the Copilot Runtime if needed (same-origin in Container App, may need configuration for local dev)

#### Notes

- **Header propagation through Copilot Runtime**: The `HttpAgent` in the Copilot Runtime may not forward arbitrary custom headers (like `X-User-Groups`) to the agent by default. Verify that the `HttpAgent` configuration supports custom header forwarding, or implement a middleware/wrapper that injects these headers. If `HttpAgent` doesn't support this, the headers may need to be passed via the AG-UI run request metadata instead.
- Easy Auth headers (`X-MS-CLIENT-PRINCIPAL-ID`, `X-MS-CLIENT-PRINCIPAL`) are injected by the Container App platform before reaching the Node.js process — they are available in Next.js API routes via `request.headers`.

#### Definition of Done

- [ ] In prod (with Easy Auth): user identity is extracted from `X-MS-CLIENT-PRINCIPAL-ID` and used as `userId` for conversation ownership
- [ ] In prod: `X-User-Groups` header reaches the agent and contextual tool filtering works (department-scoped search results)
- [ ] In dev: app works without auth — auto-accepts as `local-user`, agent runs with `REQUIRE_AUTH=false`

---

### Story 8 — Docker, Deployment & Infrastructure

> **Status:** Not Started
> **Depends on:** Story 2

Update the Dockerfile, Docker Compose, Bicep, azure.yaml, and Makefile for the new Node.js-based web app.

#### Deliverables

- [ ] New `src/web-app/Dockerfile` — Node.js 20-slim base, multi-stage build (deps → build → runtime), `next start` on port 3000
- [ ] `docker-compose.dev-services.yml` updated: web-app service builds from new Dockerfile, ports `3000:3000`
- [ ] `azure.yaml` updated: web-app service uses `language: docker` (Node.js Docker build)
- [ ] `infra/modules/container-app.bicep` updated: `targetPort` changes from 8080 to 3000, remove Chainlit-specific env vars (CHAINLIT_AUTH_SECRET, OAUTH_AZURE_AD_*), add CopilotKit env vars
- [ ] Easy Auth redirect URIs updated in `scripts/setup-redirect-uris.sh` if port matters
- [ ] Makefile targets updated: `dev-setup` installs npm dependencies for web-app, `dev-test` runs appropriate test command for web-app, `dev-ui` echoes correct URL
- [ ] `.env.dev.template` updated: remove Chainlit vars, ensure `AGENT_ENDPOINT` points to AG-UI endpoint
- [ ] `azd deploy --service web-app` builds and deploys the new Next.js container successfully
- [ ] `infra/modules/apim-agent-api.bicep` updated: add APIM operation for the `/ag-ui` POST endpoint (or explicitly document that the Copilot Runtime connects via the agent's internal FQDN, bypassing APIM)
- [ ] `messages` and `references` Cosmos containers preserved in `infra/modules/cosmos-db.bicep` for backward compatibility — marked with a comment for future removal

#### Notes

- **APIM route for AG-UI**: The current `apim-agent-api.bicep` only defines operations for `/responses`, `/liveness`, `/readiness`. The new `/ag-ui` endpoint needs an APIM operation if the Copilot Runtime routes through APIM in prod. Alternatively, if the Copilot Runtime runs inside the same Container Apps Environment, it can connect to the agent via internal FQDN (`http://agent-{project}-{env}.internal.{cae-domain}:8088/ag-ui`) bypassing APIM entirely. Choose one approach and document it.
- **Cosmos container deprecation**: The `messages` and `references` Cosmos containers were owned by the Chainlit DataLayer. After this migration they are no longer written to, but should NOT be deleted from Bicep in this epic — existing data may still be useful for reference. Add a `// DEPRECATED: previously used by Chainlit DataLayer. Safe to remove after confirming no consumers.` comment.

#### Definition of Done

- [ ] `docker build -t web-app-test src/web-app/` succeeds
- [ ] `docker-compose -f docker-compose.dev-services.yml up web-app` starts the Next.js container on port 3000
- [ ] `azd deploy --service web-app` completes without errors in a test environment
- [ ] `make dev-services-app-up` starts the containerized web app
- [ ] `make dev-ui` prints `http://localhost:3000`

---

### Story 9 — Web App Tests

> **Status:** In Progress
> **Depends on:** Stories 2–6

Write tests for the new CopilotKit web app. Replace the existing Chainlit pytest suite with appropriate JavaScript/TypeScript tests.

#### Deliverables

- [x] Test framework set up (Jest or Vitest)
- [ ] Unit tests for: image proxy API route, conversation API routes, image URL normalization logic, config loading
- [x] Component tests for: tool rendering component, citation display component
- [ ] Integration test: CopilotKit chat sends message → receives streamed response (mock agent)
- [x] Test configuration in `package.json` scripts
- [ ] `make dev-test` runs web-app tests correctly alongside Python tests for agent and functions

#### Definition of Done

- [x] `cd src/web-app && npm test` passes all unit and component tests
- [ ] `make dev-test` passes: functions (pytest), agent (pytest), web-app (jest/vitest) — zero regressions
- [ ] Test coverage includes: image proxy route, conversation CRUD routes, image URL normalization, tool renderer component, citation component

---

### Story 10 — Documentation & Cleanup

> **Status:** In Progress
> **Depends on:** Stories 1–9

Update all documentation to reflect the CopilotKit + AG-UI architecture. Clean up removed Chainlit artifacts.

#### Deliverables

- [x] `docs/ards/ARD-016-copilotkit-migration.md` created — documents the decision to migrate from Chainlit to CopilotKit with AG-UI
- [ ] `docs/specs/architecture.md` updated: replace Chainlit references with CopilotKit + AG-UI, update conversation flow diagram, update image flow diagram, update key design decisions table
- [x] `docs/specs/infrastructure.md` updated: web app container port and tech stack
- [ ] `docs/setup-and-makefile.md` updated: new setup instructions (Node.js prereqs, npm install)
- [ ] `src/web-app/.env.sample` rewritten for Node.js environment
- [ ] `README.md` updated if it references Chainlit
- [ ] Remove any orphaned Chainlit references in other epics/docs (informational, not rewriting history)
- [ ] `messages` and `references` Cosmos containers marked as deprecated in `infra/modules/cosmos-db.bicep` with comments (containers preserved, not deleted)
- [x] Epic 016 doc updated with completion status

#### Definition of Done

- [x] ARD-016 exists and documents: decision, alternatives considered, rationale, consequences
- [ ] `docs/specs/architecture.md` no longer references Chainlit; diagrams show CopilotKit + AG-UI flow
- [x] `docs/specs/infrastructure.md` shows web app as Node.js/Next.js on port 3000
- [ ] `grep -r "chainlit" docs/` returns zero hits in specs and setup docs (epics are historical — ok to keep)
- [ ] Epic 016 status updated to `Done` with a Validation Snapshot section
