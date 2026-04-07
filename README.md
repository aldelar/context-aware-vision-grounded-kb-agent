# Context Aware & Vision Grounded KB Agent

A reference implementation that transforms HTML knowledge base articles into an AI-searchable, image-aware index — and reasons over them with a vision-grounded conversational agent.

Enterprise knowledge bases store thousands of technical articles as HTML pages bundled with screenshots, diagrams, and UI captures. These articles are rich in information but invisible to AI search:

- **Traditional keyword search misses context** — queries fail to surface relevant articles when the terminology doesn't match exactly.
- **Token-based chunking breaks documents at arbitrary boundaries** — splitting on token count ignores the semantic structure of articles, producing chunks that lose coherence.
- **Images are completely lost** — screenshots, diagrams, and UI captures that often carry critical information are stripped out and never indexed.

This reference implementation solves all three problems with a two-stage ingestion pipeline and an agent that can *see*.

The agent is able to leverage images to support its answers, not just answer as text. When a search result contains images, the agent can view them and reason about their visual content — providing richer, more complete answers that draw on the full fidelity of the original articles.

![Context Aware & Vision Grounded KB Agent — using an image from a search chunk to support its answer](docs/assets/app.png)

The agent has access to well formed chunks broken down based on the understanding of the original context, by paragraphs, tables, and images together, not just arbitrary token splits. This structure-aware chunking preserves the coherence of the original content and leads to higher quality retrieval and more accurate answers.

![Context Aware & Vision Grounded KB Agent — a chunk is a complete paragraph and has the fidelity of the original (including images)](docs/assets/app2.png)

## Deployment Layout

The project runs in two modes. **Local dev** uses Docker Compose with emulators and local models for rapid, self-contained iteration with zero Azure dependency. **Azure prod** deploys the same application services to Azure Container Apps backed by managed Azure platform services. The code is the same — only the infrastructure underneath changes.

```mermaid
block-beta
  columns 5

  block:DEV_INFRA:2
    columns 1
    DI_TITLE["🐳 Infra · Local Docker"]
    DI1["Cosmos DB Emulator"]
    DI2["Azurite · Storage Emulator"]
    DI3["AI Search Simulator"]
    DI4["Ollama · Local LLMs<br/><i>qwen2.5 · moondream · mxbai-embed</i>"]
    DI5["Aspire Dashboard<br/><i>OpenTelemetry</i>"]
  end

  space

  block:PROD_INFRA:2
    columns 1
    PI_TITLE["☁️ Infra · Azure Services"]
    PI1["Azure Cosmos DB"]
    PI2["Azure Storage Account"]
    PI3["Azure AI Search"]
    PI4["Microsoft Foundry<br/><i>gpt-(5-mini/4.1) · text-embedding-3-small</i>"]
    PI5["Azure Monitor · App Insights<br/><i>OpenTelemetry</i>"]
    PI6["API Management · AI Gateway"]
    PI7["Azure Container Registry"]
  end

  block:DEV_SVC:2
    columns 1
    DS_TITLE["🐳 Services · Local Docker"]
    DS1["fn-convert"]
    DS2["fn-index"]
    DS3["agent<br/><i>Microsoft Agent Framework</i>"]
    DS4["web-app<br/><i>CopilotKit · AG-UI protocol</i>"]
  end

  space

  block:PROD_SVC:2
    columns 1
    PF_TITLE["☁️ Services · Azure Functions"]
    PF1["fn-convert"]
    PF2["fn-index"]
    PS_TITLE["☁️ Services · Azure Container Apps"]
    PS3["agent<br/><i>Microsoft Agent Framework</i>"]
    PS4["web-app<br/><i>CopilotKit · AG-UI protocol</i>"]
  end

  style DI_TITLE fill:#1565c0,stroke:#1976d2,color:#ffffff
  style DS_TITLE fill:#1565c0,stroke:#1976d2,color:#ffffff
  style PI_TITLE fill:#bf360c,stroke:#e65100,color:#ffffff
  style PF_TITLE fill:#bf360c,stroke:#e65100,color:#ffffff
  style PS_TITLE fill:#bf360c,stroke:#e65100,color:#ffffff

  style DEV_INFRA fill:#263238,stroke:#37474f,color:#cfd8dc
  style DEV_SVC fill:#263238,stroke:#37474f,color:#cfd8dc
  style PROD_INFRA fill:#3e2723,stroke:#4e342e,color:#d7ccc8
  style PROD_SVC fill:#3e2723,stroke:#4e342e,color:#d7ccc8

  style DI1 fill:#37474f,stroke:#455a64,color:#eceff1
  style DI2 fill:#37474f,stroke:#455a64,color:#eceff1
  style DI3 fill:#37474f,stroke:#455a64,color:#eceff1
  style DI4 fill:#37474f,stroke:#455a64,color:#eceff1
  style DI5 fill:#37474f,stroke:#455a64,color:#eceff1

  style PI1 fill:#4e342e,stroke:#5d4037,color:#efebe9
  style PI2 fill:#4e342e,stroke:#5d4037,color:#efebe9
  style PI3 fill:#4e342e,stroke:#5d4037,color:#efebe9
  style PI4 fill:#4e342e,stroke:#5d4037,color:#efebe9
  style PI5 fill:#4e342e,stroke:#5d4037,color:#efebe9
  style PI6 fill:#4e342e,stroke:#5d4037,color:#efebe9
  style PI7 fill:#4e342e,stroke:#5d4037,color:#efebe9

  style DS1 fill:#37474f,stroke:#455a64,color:#eceff1
  style DS2 fill:#37474f,stroke:#455a64,color:#eceff1
  style DS3 fill:#37474f,stroke:#455a64,color:#eceff1
  style DS4 fill:#37474f,stroke:#455a64,color:#eceff1

  style PF1 fill:#4e342e,stroke:#5d4037,color:#efebe9
  style PF2 fill:#4e342e,stroke:#5d4037,color:#efebe9
  style PS3 fill:#4e342e,stroke:#5d4037,color:#efebe9
  style PS4 fill:#4e342e,stroke:#5d4037,color:#efebe9
```

## Getting Started

### Shared

Set the converter backend used by the pipeline (applies to both local and Azure workflows):

```bash
make set-converter name=markitdown   # or: cu (Content Understanding), mistral (Mistral Document AI)
```

### Local / Dev

The local workflow is Docker-first and does not require Azure cloud resources, Azure credentials, or Entra auth. It uses smaller local Ollama-hosted models (`qwen2.5:3b`, `mxbai-embed-large`, `moondream`), so it is self-contained and cheap to run, but answer quality is below the Azure-hosted production path.

If you use an NVIDIA GPU with a native Linux or local-WSL Docker engine (not Docker Desktop), run the GPU setup once first:

```bash
sudo make dev-setup-gpu
```

Then bring everything up:

```bash
make dev-up
```

`dev-up` installs local dependencies, starts emulators, builds all services, runs the pipeline, and prints the local UI URL.

For faster UI iteration, run the backends locally and start the Next.js app on the host with hot reload:

```bash
make dev-infra-up
make dev-services-pipeline-up
make dev-services-agents-up
make dev-pipeline
make dev-ui-live
```

That keeps the infra, functions, and agent in Docker, but serves the web app directly from `src/web-app` on `http://localhost:3001` so UI changes reload immediately.

`make dev-ui-live` runs in the current terminal and can be stopped with `Ctrl+C`. It also writes a copy of its output to `.tmp/logs/dev-ui-live.log`, which you can tail from another terminal with `make dev-ui-live-logs`. If an existing hot-reload server is already running, stop it with `make dev-ui-live-stop`.

If the backends are already up, use:

```bash
make dev-ui-live
```

To print the hot-reload URL only, use:

```bash
make dev-ui-live-url
```

### Azure / Prod

Set the project name, then bring everything up:

```bash
make set-project name=myproj
make prod-up
```

`prod-up` installs Azure CLI and AZD if missing, provisions infrastructure, deploys services, runs the pipeline, and prints the deployed web app URL.

See [docs/setup-and-makefile.md](docs/setup-and-makefile.md) for the full target reference.

---

## Core Patterns

This solution demonstrates eight architectural patterns for building production-quality AI agents over enterprise content. Each solves a real problem encountered when moving from prototype to production.

### 1. Pluggable Document Normalization

**Problem:** KB articles come in many formats (HTML, PDF, PowerPoint), each requiring different extraction logic. Coupling extraction and indexing creates a monolith that's hard to extend.

**Pattern:** A two-stage pipeline decoupled by a **serving contract** — a normalized Markdown + images format (`article.md` + `images/` folder). The converter stage (`fn-convert`) transforms any source format into this contract; the indexing stage (`fn-index`) only reads Markdown. The existing converters already handle the hard parts (text extraction, image analysis, Markdown assembly) — adapting them to accept PDF, PowerPoint, Word, or other document types requires minimal changes on the input side, while the indexing pipeline remains completely untouched.

This repo currently handles HTML as input. Three interchangeable converter backends for HTML prove the pluggability of the pattern:

| Backend | Text Extraction | Image Description | Trade-off |
|---------|----------------|-------------------|-----------|
| **Content Understanding** | Azure CU `prebuilt-documentSearch` (HTML-direct) | Custom CU `kb-image-analyzer` (GPT-4.1) | Highest fidelity; CU internal calls can't be routed through an API gateway |
| **Mistral Document AI** | HTML → PDF (Playwright) + Mistral OCR | GPT-4.1 vision | Gateway-compatible; requires Chromium for PDF rendering |
| **MarkItDown** | Local Python ([MarkItDown](https://github.com/microsoft/markitdown) library) | GPT-4.1 vision | Fastest, cheapest — only GPT-4.1 vision calls are billed |

Select at runtime: `make convert analyzer=markitdown`

```mermaid
flowchart LR
    SRC["📄 Source Documents<br/><i>HTML, PDF, Word,<br/>PowerPoint, ...</i>"]

    MIT["MarkItDown"]
    CU["Content Understanding"]
    MIS["Mistral Document AI"]

    MD["Serving Contract<br/><b>article.md + images/</b><br/><i>Markdown Document</i>"]

    IDX["fn-index<br/>Chunk → Embed → Index"]

    SRC --> MIT
    SRC -.-> CU
    SRC -.-> MIS
    MIT & CU & MIS --> MD --> IDX

    style SRC fill:#90a4ae,stroke:#b0bec5,color:#1a237e
    style MIT fill:#455a64,stroke:#546e7a,color:#ffffff
    style CU fill:#455a64,stroke:#546e7a,color:#ffffff
    style MIS fill:#455a64,stroke:#546e7a,color:#ffffff
    style MD fill:#1565c0,stroke:#1976d2,color:#ffffff
    style IDX fill:#455a64,stroke:#546e7a,color:#ffffff
```

---

### 2. Structure-Aware Chunking

**Problem:** Token-based chunking splits documents at arbitrary boundaries — breaking paragraphs mid-sentence, separating tables from their headers, and losing the relationship between images and the text they illustrate. The resulting chunks are noisy and lack coherence.

**Pattern:** The indexer (`fn-index`) splits Markdown by **document structure** (headings and sections), not by token count. Each chunk is a complete, coherent section:

- **Paragraphs** are never split mid-sentence or mid-thought
- **Tables** stay intact with their headers
- **Images** that appear within a section stay co-located in the same chunk, with their AI-generated description embedded alongside the surrounding text

Each chunk is a **self-contained unit of meaning** — the text, its structure, and its supporting visuals travel together. This directly improves retrieval quality: when a chunk matches a query, the full context is there, not fragments scattered across adjacent chunks.

```mermaid
flowchart LR
    subgraph Article["<i>Markdown Document</i>"]
        direction TB
        S1["Section: Overview<br/><i>paragraphs + links</i>"]
        S2["Section: Architecture<br/><i>paragraph + 🖼 diagram<br/>+ image description</i>"]
        S3["Section: Configuration<br/><i>paragraph + table</i>"]
    end

    subgraph Chunks["Index"]
        direction TB
        C1["Chunk 1 — complete section"]
        C2["Chunk 2 — text + image intact"]
        C3["Chunk 3 — table with headers"]
    end

    S1 --> C1
    S2 --> C2
    S3 --> C3

    style Article fill:#1565c0,stroke:#1976d2,color:#ffffff
    style Chunks fill:#0d47a1,stroke:#1565c0,color:#ffffff
```

---

### 3. Vision-Grounded Retrieval

**Problem:** AI-generated image descriptions capture the gist of a visual but lose significant fidelity — UI details, spatial relationships, and visual cues that text alone cannot fully convey. Agents relying solely on text descriptions give incomplete answers when the image carries critical information.

**Pattern:** Images serve a **dual purpose** in this system:

1. **Search relevance (text descriptions)** — During ingestion, each image gets an AI-generated description (what the screenshot shows, UI elements, navigation path). This description is embedded in the chunk text and vectorized alongside it, boosting search relevance for visual concepts.

2. **Visual reasoning (source images)** — At query time, a `VisionImageMiddleware` intercepts search results, downloads the actual source images from blob storage, and injects them as base64 `Content.from_data()` into the LLM conversation. The LLM **sees** the real screenshot or diagram — not just the text description — and can reason about its visual content.

The agent can then embed images inline in its response using `![alt](/api/images/...)` markdown, rendered by the browser via a same-origin image proxy.

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent
    participant S as AI Search
    box rgba(249, 168, 37, 0.25)
        participant V as Vision Middleware
    end
    participant B as Blob Storage

    U->>A: Ask question
    A->>S: Hybrid search (vector + keyword)
    S-->>A: Chunks with image_urls[]
    A->>V: Intercept tool result
    V->>B: Download source images
    B-->>V: PNG bytes
    V-->>A: Inject base64 images into LLM conversation
    Note over A: LLM sees actual images +<br/>text chunks, reasons over both
    A-->>U: Answer with inline images
```

---

### 4. Agent-Owned Conversation Memory

**Problem:** When the web app owns conversation history, the UI layer must build, serialize, trim, and pass the full conversation context on every request. That couples the frontend to the agent's context-management strategy and makes resume fidelity harder to preserve.

**Pattern:** The agent owns canonical conversation state using the [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/)'s session persistence and compaction. Both the agent and the web app use Cosmos DB as their persistence backend. A custom `CosmosAgentSessionRepository` persists `AgentSession` state to the `agent-sessions` container. The web app owns only lightweight `conversations` metadata for sidebar CRUD and thread selection.

The detailed contracts now live in the dedicated specs: [Agent Session](docs/specs/agent-session.md) defines canonical session persistence and transcript hydration, and [Conversation State Model](docs/specs/conversation-state-model.md) defines ownership boundaries across the web app, AG-UI, and future workflows.

```mermaid
flowchart LR
    UI["Web App<br/>Next.js + CopilotKit"] -->|"threadId via AG-UI"| Agent["KB Agent<br/>CosmosAgentSessionRepository"]
    Agent -->|"canonical transcript"| Sessions[("agent-sessions")]
    UI -->|"sidebar metadata"| Conversations[("conversations")]
```

---

### 5. Zero-Trust Identity Model

**Problem:** Managing connection strings, API keys, and secrets across multiple services is error-prone and creates a large attack surface. Key rotation is manual, and any leaked credential exposes the entire service.

**Pattern:** **No keys, no secrets, no connection strings** — every service-to-service interaction uses Azure Managed Identity with least-privilege RBAC.

| Layer | Mechanism |
|-------|-----------|
| **Service-to-service** | System-assigned managed identity on each Container App, with per-service RBAC roles defined in Bicep |
| **Developer access** | `DefaultAzureCredential` — same code works locally (Azure CLI identity) and deployed (managed identity) |
| **User authentication** | Entra ID Easy Auth (platform sidecar) + Next.js header extraction for per-user session ownership |
| **Agent API protection** | In-code JWT middleware (RS256, JWKS-cached) for external HTTPS ingress; environment-gated (`REQUIRE_AUTH`) for local dev bypass |
| **Data access** | Cosmos DB native RBAC (Built-in Data Contributor) — local auth disabled, Entra-only |

All RBAC role assignments are declared in Bicep and deployed with the infrastructure — no manual portal configuration.

```mermaid
flowchart TD
    DEV["Developer<br/>(Azure CLI)"]
    MI_A["Agent MI"]
    MI_W["Web App MI"]
    ENT["Entra ID"]

    subgraph Services["Azure Services"]
        AI["AI Services"]
        SRCH["AI Search"]
        BLOB["Blob Storage"]
        CDB["Cosmos DB"]
    end

    DEV -->|DefaultAzureCredential| Services
    ENT -->|Easy Auth + JWT| MI_A & MI_W
    MI_A -->|"RBAC (Bicep)"| Services
    MI_W -->|"RBAC (Bicep)"| Services

    style Services fill:#2a2d32,stroke:#5a6068
    style MI_A fill:#3949ab,stroke:#5c6bc0,color:#ffffff
    style MI_W fill:#455a64,stroke:#546e7a,color:#ffffff
```

---

### 6. AI Gateway

**Problem:** Agents deployed as Container Apps have ephemeral FQDNs that change on redeployment, and no centralized traffic governance. Adding rate limiting, content safety filters, or usage analytics requires application code changes.

**Pattern:** Azure API Management acts as a stable proxy URL fronting the agent Container App. This decouples the agent's internal FQDN from all consumers — the web app, Foundry agent registration, and future integrations all use the same gateway URL, which never changes across redeployments.

Beyond stable routing, APIM provides an extensible policy pipeline — without touching agent code:

- **Rate limiting & throttling** — protect the agent from burst traffic
- **Token tracking & cost analytics** — meter usage per consumer or tenant
- **Content safety filters** — add pre-call and post-call content filtering policies
- **Scaling governance** — route traffic across multiple agent instances
- **Access control** — API key, OAuth, or subscription-based access policies

```mermaid
flowchart LR
    CHAT["CopilotKit UI"] --> APIM["APIM<br/>AI Gateway"]
    APIM -->|"stable proxy URL"| AGENT["Agent<br/>Container App"]
    APIM -.->|"rate limiting,<br/>content safety,<br/>token tracking"| GOV["Policy Pipeline"]

    style CHAT fill:#455a64,stroke:#546e7a,color:#ffffff
    style APIM fill:#6d8f6d,stroke:#8aac8a,color:#ffffff
    style AGENT fill:#3949ab,stroke:#5c6bc0,color:#ffffff
```

---

### 7. Built-in Observability

**Problem:** Agents involve multi-step chains (tool calls, model invocations, session load/save) that are opaque without structured telemetry. Debugging production issues requires visibility into each step, and different environments need different telemetry backends.

**Pattern:** The [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/) provides built-in OpenTelemetry instrumentation — tool calls, model invocations, and session lifecycle are automatically traced as spans with no application code required. The agent startup detects which telemetry backend is available and configures accordingly:

- **Azure Monitor** (production) — via `APPLICATIONINSIGHTS_CONNECTION_STRING`
- **OTLP exporter** (local dev) — via `OTEL_EXPORTER_OTLP_ENDPOINT` (e.g., Aspire Dashboard)
- **No-op** (simple local dev) — when neither is set

The same binary runs in all three modes — framework telemetry flows automatically once a backend is configured.

```mermaid
flowchart LR
    AGENT["Agent<br/>Container App"] --> FW["Agent Framework<br/>auto-instrumentation"]
    FW --> MON{"Backend?"}
    MON -->|"APPINSIGHTS_*"| AI["Application Insights<br/>(Azure Monitor)"]
    AI --> FOUNDRY["Microsoft Foundry<br/>trace visualization"]
    MON -->|"OTLP_ENDPOINT"| ASP["Aspire Dashboard"]
    MON -->|"neither"| NOP["No-op"]

    style AGENT fill:#3949ab,stroke:#5c6bc0,color:#ffffff
    style FW fill:#3949ab,stroke:#5c6bc0,color:#ffffff
    style FOUNDRY fill:#4a148c,stroke:#6a1b9a,color:#ffffff
```

![Agent trace in Azure Monitor — tool calls, model invocations, and session lifecycle as OpenTelemetry spans](docs/assets/trace.png)

*Traces are stored in Application Insights and visualized here in the Microsoft Foundry portal — available when the agent is registered to Foundry via `bash scripts/register-agent.sh`.*

---

### 8. Contextual Tool Filtering

**Problem:** Agent tools query backends (AI Search, databases) but have no way to apply per-user security filters without leaking identity context into the LLM prompt. Injecting department or role into the system prompt exposes sensitive authorization logic to the model and creates prompt injection risks.

**Pattern:** Three-layer out-of-band propagation using [`ContextVar`](https://docs.python.org/3/library/contextvars.html) → [`FunctionMiddleware`](https://learn.microsoft.com/en-us/agent-framework/) → `**kwargs`. JWT claims are extracted at the HTTP boundary and stored in a `ContextVar`. A `SecurityFilterMiddleware` (Agent Framework `FunctionMiddleware`) resolves Entra group GUIDs to department names and writes enriched values into `context.kwargs`. Tools receive departments, roles, and tenant ID as plain `**kwargs` and build backend-specific filters (OData for AI Search, SQL WHERE clauses for databases). The LLM never sees the filter context. Tools are testable in isolation by passing kwargs directly.

**Index metadata pipeline:** The `department` field in the AI Search index is populated via a `metadata.json` contract between the convert and index stages. `fn-convert` reads articles from `staging/{department}/{article-id}/`, writes the processed output to flat `serving/{article-id}/`, and generates a `metadata.json` file containing `{"department": "engineering"}` (and any future index fields). `fn-index` reads `metadata.json` from each article folder and uses its fields directly as AI Search index fields — no knowledge of the staging folder structure is needed. This makes the metadata extensible: adding a new index dimension only requires `fn-convert` to write an additional field to `metadata.json`.

```mermaid
flowchart LR
    A["HTTP Request<br/>(Bearer token)"] --> B["JWT Middleware<br/>validates token,<br/>sets ContextVar"]
    B --> C["Agent Framework<br/>agent.run()"]
    C --> D["SecurityFilterMiddleware<br/>resolves groups,<br/>writes to kwargs"]
    D -->|"1 call"| G["Graph API<br/>(simulated)"]
    D --> E["search_knowledge_base<br/>builds OData from **kwargs"]

    H["Unit Test"] -.->|"departments=[...]"| E

    style B fill:#2e7d32,color:#fff
    style D fill:#e65100,color:#fff
    style E fill:#1565c0,color:#fff
    style G fill:#b71c1c,color:#fff
    style H fill:#6a1b9a,color:#fff
```

> See [docs/specs/contextual-tool-filtering.md](docs/specs/contextual-tool-filtering.md) for the full architecture comparison and implementation details.

---

## Architecture

A **two-stage ingestion pipeline** builds an image-aware search index, and a **conversational agent** (Container App with Foundry integration for tracing) reasons over it with vision capabilities. A **Next.js + CopilotKit thin client** calls the agent via the **AG-UI protocol** through an APIM AI Gateway, while conversation persistence is split between agent-owned `agent-sessions` and web-app-owned `conversations` metadata.

```mermaid
flowchart LR
    subgraph Pipeline["Ingestion Pipeline"]
        SA1["Source<br/>Documents"] --> CVT["fn_convert ✱<br/>HTML → MD"] --> SA2["Markdown<br/>Documents"] --> IDX["fn_index<br/>MD → index"]
        CVT --> IMG["Images"]
    end

    IDX --> AIS["AI Search<br/>kb-articles index"]

    subgraph AgentSvc["KB Agent"]
        AGENT["<b>Agent</b>"]
        VIS["<b>Vision Middleware</b>"]
    end

    AGENT -->|query| AIS
    AGENT -->|reason| AF["Foundry<br/>GPT-4.1 + Embeddings"]
    VIS -->|fetch| IMG
    VIS -->|inject| AGENT
    AGENT -->|sessions| COSMOS["Cosmos DB"]

    CHAT["CopilotKit UI"] -->|AG-UI + citation lookups| APIM["APIM"] --> AGENT
    CHAT -->|conversation metadata| COSMOS

    style AgentSvc fill:#3949ab,stroke:#5c6bc0,color:#ffffff
    style Pipeline fill:#455a64,stroke:#546e7a,color:#ffffff
    style APIM fill:#6d8f6d,stroke:#8aac8a,color:#ffffff
    style COSMOS fill:#616161,stroke:#757575,color:#ffffff
    style SA2 fill:#1565c0,stroke:#1976d2,color:#ffffff
    style SA1 fill:#90a4ae,stroke:#b0bec5,color:#1a237e
    style AIS fill:#0d47a1,stroke:#1565c0,color:#ffffff
    style VIS fill:#8b7535,stroke:#a6893f,color:#ffffff
    style IMG fill:#8b7535,stroke:#a6893f,color:#ffffff
    style AF fill:#4a148c,stroke:#6a1b9a,color:#ffffff
    style CHAT fill:#455a64,stroke:#546e7a,color:#ffffff
```

**✱ fn_convert** — three interchangeable converter backends, selected at runtime via `analyzer=`. Each runs as its own Container App. See the [Architecture spec](docs/specs/architecture.md) for pipeline details, converter backends, and index schema.

---

## Project Structure

```
├── docs/
│   ├── ards/            Architecture Decision Records
│   ├── epics/           Epic and story tracking
│   ├── research/        Spike results and research notes
│   └── specs/           Architecture, infrastructure, agent-session, and conversation ownership specs
├── infra/
│   ├── azure/           AZD project, hooks, and Bicep IaC for Azure resources
│   └── docker/          Local Docker Compose topology for dev infra + services
├── kb/
│   ├── staging/         Source articles (HTML + images)
│   └── serving/         Processed articles (Markdown + images)
├── scripts/             Automation: dev setup, agent registration, auth config
├── src/
│   ├── agent/           KB Agent — Container App (Starlette + Agent Framework)
│   ├── functions/       4 Azure Functions (fn_convert_cu, fn_convert_mistral,
│   │                    fn_convert_markitdown, fn_index) — each a Container App
│   └── web-app/         Next.js + CopilotKit thin client (AG-UI runtime + Cosmos metadata layer)
└── Makefile             Developer workflow — local + Azure targets
```

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/specs/architecture.md) | Pipeline design, converter backends, index schema, agent components, image flow |
| [Infrastructure](docs/specs/infrastructure.md) | Bicep modules, resource inventory, model deployments, RBAC, networking |
| [Agent Session](docs/specs/agent-session.md) | Canonical agent-session persistence, transcript hydration, and resume behavior |
| [Conversation State Model](docs/specs/conversation-state-model.md) | Ownership boundaries across the web app, AG-UI, workflows, and specialists |
| [Setup & Makefile Guide](docs/setup-and-makefile.md) | Full Makefile reference, local/Azure workflows, resource naming |
| [Architecture Decision Records](docs/ards/) | Key design decisions with rationale and alternatives considered |

## Considerations for Production

The Azure teardown flow in this repo is optimized for rapid development and iteration. `make prod-down` is intentionally aggressive: it deletes the active environment and also purges known soft-deleted Azure resources that otherwise block immediate redeploy with the same names.

That convenience should not be treated as a production baseline. In a production setup, soft-delete and recovery protections should be reviewed service by service and kept where they support your operational and compliance requirements. The current repo behavior is aimed at shortening the destroy-and-recreate loop for engineering work, not at maximizing recovery safety after accidental deletion.
