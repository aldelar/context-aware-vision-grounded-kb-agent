# 008 — Environment Re-Organization (Dev / Prod)

> **Status:** Draft — March 26, 2026
> **Goal:** Maximize local containerization for dev speed; clean separation between dev and prod environments.

## 1. Problem Statement

The current setup blurs local and Azure workflows:
- Local dev requires a full Azure resource group (AI Services, Search, Storage, Cosmos DB).
- There is no docker-compose; each service runs manually via `uv run`.
- No local emulators are used — everything talks to Azure even during development.
- The Makefile mixes "Local" and "Azure" in ways that don't cleanly map to a dev/prod model.
- Tests are categorized as unit, integration, and e2e, but the e2e label adds confusion (they are really integration tests).

## 2. Target Environments

| Environment | Infra Location | Services Run As | LLM / Embeddings Source | Purpose |
|-------------|---------------|-----------------|------------------------|--------|
| **Dev** (local) | Docker containers only — **zero Azure dependency** | Docker containers (our code + emulators + Ollama) | Ollama (local): `phi4-mini` for chat, `mxbai-embed-large` for embeddings, `moondream` for vision/images | Daily development, fast iteration, unit + integration tests |
| **Prod** | Azure RG (`rg-{project}-prod`) | Azure Container Apps | Azure AI Services (GPT-4.1, text-embedding-3-large, GPT-4.1 vision) | Production |

> **Note:** Staging is intentionally omitted from this reference repo. A staging environment would be a clone of prod infra with a different AZD env name (e.g., `rg-{project}-staging`). It can be added later when CI/CD pipelines are set up.

> **Key design decision:** Dev has **no Azure dependency whatsoever**. All infrastructure runs in Docker. Bicep/IaC exists only for prod. This means no `az login`, no Azure subscription, and no Azure cost for local development.

## 3. Project-Level Parameters

Two parameters are set once per project and stored in AZD env. All Makefile targets read them automatically — no per-invocation overrides needed.

| Parameter | AZD Env Key | Values | Default | Set via |
|-----------|-------------|--------|---------|--------|
| **Project name** | `PROJECT_NAME` | 2–8 chars | _(required)_ | `make set-project name=<value>` |
| **Converter** | `CONVERTER` | `markitdown`, `content-understanding`, `mistral-doc-ai` | `markitdown` | `make set-converter converter=<value>` |

**How `CONVERTER` works:**

- Determines which `fn-convert` variant is built and deployed — only one at a time.
- In **dev**: `infra/docker/docker-compose.dev-services.yml` builds the Dockerfile for the selected converter.
- In **prod**: `azd deploy` deploys only the selected converter's container to Azure Container Apps.
- The `dev-convert` and `prod-convert` targets route to the correct function automatically.
- Changing the converter is a `make set-converter converter=X` + rebuild (`dev-services-up` or `prod-services-up`).

**Mapping:**

| `CONVERTER` value | Dockerfile | Function App (prod) | Azure route |
|-------------------|-----------|--------------------|-----------|
| `markitdown` | `fn_convert_markitdown/Dockerfile` | `func-cvt-mit-{project}-{env}` | `/api/convert-markitdown` |
| `content-understanding` | `fn_convert_cu/Dockerfile` | `func-cvt-cu-{project}-{env}` | `/api/convert` |
| `mistral-doc-ai` | `fn_convert_mistral/Dockerfile` | `func-cvt-mis-{project}-{env}` | `/api/convert-mistral` |

## 4. Service Dependency Map

### What each service needs at runtime:

| Service | Cosmos DB | AI Search | Blob Storage | AI Services / LLM | Foundry Project |
|---------|-----------|-----------|-------------|-------------------|-----------------|
| **web-app** (Chainlit) | Yes (conversations, messages, references) | No | Yes (serving images) | No | No |
| **agent** | Yes (agent-sessions) | Yes (kb-articles index) | Yes (serving images) | Yes (GPT model for reasoning) | Yes (agent registration) |
| **fn-convert** (all variants) | No | No | Yes (staging read, serving write) | Yes (CU/Mistral/GPT-4.1 for image analysis) | No |
| **fn-index** | No | Yes (push chunks to index) | Yes (serving read — images) | Yes (embeddings) | No |

### Local emulation feasibility:

| Azure Service | Local Replacement | Docker Image | Feasibility | Notes |
|---------------|------------------|--------------|-------------|-------|
| **Cosmos DB** | Cosmos DB Linux Emulator (vNext preview) | `mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview` | **Good** | NoSQL API supported, HTTP mode works for Python SDK, key-based auth (not AAD), port 8081. Supports CRUD, queries, change feed, batch, TTL. Does not support serverless throughput — use provisioned (400 RU/s) locally. |
| **Azure Blob Storage** | Azurite | `mcr.microsoft.com/azure-storage/azurite:latest` | **Excellent** | Full Blob/Queue/Table emulation. Port 10000 (Blob), 10001 (Queue), 10002 (Table). Well-known connection string. DefaultAzureCredential won't work — use connection string or well-known key locally. |
| **Azure AI Search** | Azure AI Search Simulator | `ghcr.io/ellerbach/azure-ai-search-simulator:latest` | **Good** | Community-built simulator ([GitHub](https://github.com/Ellerbach/azure-ai-search-simulator)). Supports full-text search, vector search (cosine), hybrid search, filtering, facets, sorting, highlighting, autocomplete, suggestions, scoring profiles, synonym maps. Uses Lucene.NET internally. Compatible with the official `azure-search-documents` Python SDK. API-key auth (not AAD). HTTPS on port 7250, HTTP on port 5250. Does **not** support semantic search or AI built-in skills — acceptable for our push-model usage (we only push pre-embedded chunks). |
| **AI Services (LLM)** | Ollama — `phi4-mini` | `ollama/ollama` (with `--gpus=all`) | **Good** | Microsoft Phi-4-mini-instruct (3.8B params, 2.5 GB). OpenAI-compatible API at `http://localhost:11434/v1/`. Supports `/v1/chat/completions` with tool calling, streaming, structured output. 128K context. MIT license. Fits entirely in 4 GB VRAM for fast GPU inference. Strong reasoning for its size (math, logic). Quality is below GPT-4.1 but sufficient for dev/test data-flow validation. |
| **AI Services (Embeddings)** | Ollama — `mxbai-embed-large` | (same `ollama/ollama` container) | **Excellent** | 335M param model (670 MB). Supports `/v1/embeddings` endpoint. MTEB SOTA for BERT-large class — outperforms OpenAI `text-embedding-3-large`. 512-token context. Generates 1024-dim vectors. |
| **AI Services (Vision/OCR)** | Ollama — `moondream` | (same `ollama/ollama` container) | **Good** | moondream2 (1.8B params, 1.7 GB). Tiny vision language model designed for edge devices. Supports image+text input via `/v1/chat/completions` with `image_url` content. Fits GPU alongside phi4-mini. Used by fn-convert (MarkItDown) for image analysis in dev. CU and Mistral converters still require Azure — but MarkItDown is the default for dev. |
| **Foundry Project** | Not needed for dev | N/A | **Not required** | Agent registration is a prod concern. In dev, the agent runs directly as a local HTTP service without Foundry registration. |

### 4.1 Ollama: Local LLM + Embedding Provider

**Why Ollama over Foundry Local:**

| Dimension | Foundry Local | Ollama | Winner |
|-----------|---------------|--------|--------|
| Embedding models | **None** | mxbai-embed-large, nomic-embed-text, all-minilm | **Ollama** (dealbreaker) |
| Docker image | No — native install only (winget/brew) | `ollama/ollama` with `--gpus=all` | **Ollama** |
| GPT-class chat model | gpt-oss-20b (ONNX, 14 GB — too large for 4 GB VRAM) | phi4-mini (2.5 GB — fits GPU), gpt-oss:20b, gemma3, etc. | **Ollama** (more model choices) |
| Linux support | Listed but preview-quality | First-class, stable | **Ollama** |
| OpenAI API coverage | `/v1/chat/completions` only | `/v1/chat/completions`, `/v1/embeddings`, `/v1/models`, `/v1/responses` | **Ollama** |
| Maturity | Preview (v0.3.x, 2.1k stars) | Stable (v0.18.x, 166k stars) | **Ollama** |

**Models for dev laptop (32 GB RAM + RTX 1050 4 GB VRAM minimum):**

| Model | Role | Size | Fits 4 GB VRAM? | Notes |
|-------|------|------|-----------------|-------|
| `phi4-mini` | Chat / reasoning (agent) | 2.5 GB | **Yes** | Microsoft Phi-4-mini-instruct. 3.8B params, 128K context, tool calling support. Strong reasoning (math, logic). Text-only — no vision. Best quality-per-GB for small VRAM. |
| `mxbai-embed-large` | Embeddings (fn-index) | 670 MB | **Yes** | MTEB SOTA for BERT-large class. 335M params, 1024-dim vectors. Replaces Azure `text-embedding-3-large`. |
| `moondream` | Vision / image analysis (fn-convert) | 1.7 GB | **Yes** | moondream2. 1.8B params, image+text input. Used by MarkItDown converter for image description. phi4-mini is text-only, so moondream handles vision tasks. |

> **Quality caveat:** `phi4-mini` (3.8B) is substantially smaller than Azure GPT-4.1. Integration tests should validate **data flow and connectivity**, not response quality. Quality evaluation must use prod models (see eval-driven-dev skill).

### 4.2 API Compatibility — Two-Layer Architecture

The project uses **two distinct API layers** — an important distinction for dev/prod parity:

```
web-app  ──Responses API──▶  agent (FastAPI /v1/responses)
                                   │
                                   ▼  internally
                           AzureOpenAIChatClient
                                   │
                           Chat Completions API
                                   │
                          ▼ prod: Azure AI Services
                          ▼ dev:  Ollama
```

**Layer 1 — External (web-app → agent):** The agent exposes an OpenAI-compatible **Responses API** (`/v1/responses`) via its FastAPI server. The web-app calls this endpoint. This is our own code and runs identically in dev and prod — no Ollama involvement.

**Layer 2 — Internal (agent → LLM backend):** The agent framework uses the **Chat Completions API** (`/v1/chat/completions`) via `AzureOpenAIChatClient` to talk to the LLM. This is where dev/prod diverge:

| Concern | Dev (Ollama) | Prod (Azure) |
|---------|-------------|-------------|
| Agent framework client | `OpenAIChatClient` | `AzureOpenAIChatClient` |
| LLM API | `/v1/chat/completions` → Ollama | `/v1/chat/completions` → Azure AI Services |
| Embeddings API | `/v1/embeddings` → Ollama | `/v1/embeddings` → Azure AI Services |
| Vision (fn-convert) | `/v1/chat/completions` + `image_url` → Ollama (`moondream`) | `/v1/chat/completions` + `image_url` → Azure (GPT-4.1) |
| Tool calling | Supported (phi4-mini) | Supported (GPT-4.1) |
| Streaming | Supported | Supported |

**Key insight:** Ollama only needs to be compatible with the **Chat Completions** protocol (Layer 2). The Responses API (Layer 1) is our own FastAPI server — it works the same everywhere. The Microsoft Agent Framework provides both `AzureOpenAIChatClient` (Azure) and `OpenAIChatClient` (generic OpenAI-compatible). For dev, we use `OpenAIChatClient` pointed at Ollama — same Chat Completions protocol, zero code divergence in the agent logic.

### 4.3 Observability — Dev vs Prod

| Concern | Dev (local) | Prod (Azure) |
|---------|------------|-------------|
| **Telemetry collector** | Aspire Dashboard (Docker) | Azure Monitor / App Insights |
| **Protocol** | OpenTelemetry (OTLP gRPC) | OpenTelemetry (OTLP gRPC) → App Insights |
| **Traces UI** | `http://localhost:18888` | Azure Portal → App Insights → Transaction search |
| **Logs** | Aspire Dashboard structured logs | App Insights → Logs (KQL) |
| **Metrics** | Aspire Dashboard metrics view | App Insights → Metrics |
| **Agent tracing** | OpenTelemetry spans via OTLP | Foundry tracing + App Insights |
| **Container** | `mcr.microsoft.com/dotnet/aspire-dashboard:latest` | N/A (Azure-managed) |
| **Config** | `OTEL_EXPORTER_OTLP_ENDPOINT=http://aspire-dashboard:18889` | `APPLICATIONINSIGHTS_CONNECTION_STRING` (auto via Bicep) |

**Key design:** Both environments use **OpenTelemetry** as the telemetry protocol. The only difference is the exporter destination — Aspire Dashboard locally vs App Insights in Azure. Application code instruments with OTEL SDK once; the exporter endpoint is environment-driven.

Aspire Dashboard provides a rich development-time UI for traces, structured logs, and metrics — no Azure account needed. In prod, Foundry tracing provides agent-specific observability (tool calls, reasoning steps) alongside App Insights for infrastructure telemetry.

## 5. Dev Environment Architecture

### 5.1 Docker Compose Topology — Zero Azure Dependency

```
┌─ docker-compose.dev.yml ──────────────────────────────────────┐
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ cosmosdb-emu │  │   azurite    │  │  search-simulator    │ │
│  │  :8081       │  │  :10000 blob │  │  :7250 (HTTPS)       │ │
│  │  :1234 UI    │  │  :10001 queue│  │  :5250 (HTTP)        │ │
│  └──────────────┘  │  :10002 table│  └──────────────────────┘ │
│                     └──────────────┘                           │
│  ┌──────────────┐  ┌──────────────────────────────────────┐   │
│  │   ollama     │  │  aspire-dashboard                    │   │
│  │  :11434 API  │  │  :18888 UI (traces, logs, metrics)  │   │
│  │  GPU-accel.  │  │  :18889 OTLP gRPC receiver          │   │
│  └──────────────┘  └──────────────────────────────────────┘   │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  fn-convert  │  │   fn-index   │  │      agent           │ │
│  │  (markitdown)│  │   :7072      │  │      :8088           │ │
│  │  :7071       │  │              │  │                      │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│                                                                │
│  ┌──────────────┐                                              │
│  │   web-app    │                                              │
│  │   :8080      │  ← browser UI entry point                   │
│  └──────────────┘                                              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
                 No Azure dependency ✓
```

> **Everything runs locally.** No Azure subscription, no `az login`, no cloud cost for dev.

### 5.2 No Dev Azure RG

Unlike previous iterations, **there is no dev Azure Resource Group**. All Azure service dependencies are replaced by local Docker containers:

| Azure Service (prod) | Local Replacement (dev) | Container |
|----------------------|------------------------|-----------|
| Cosmos DB | Cosmos DB Linux Emulator | `cosmosdb-emu` |
| Blob Storage | Azurite | `azurite` |
| AI Search | AI Search Simulator | `search-simulator` |
| AI Services (GPT) | Ollama — `phi4-mini` | `ollama` |
| AI Services (Embeddings) | Ollama — `mxbai-embed-large` | `ollama` |
| AI Services (Vision) | Ollama — `moondream` | `ollama` |
| Foundry Project | Not needed — agent runs as local HTTP service | N/A |
| App Insights / Log Analytics | Aspire Dashboard (OpenTelemetry) | `aspire-dashboard` |

**Bicep exists only for prod** (`infra/azure/infra/main.bicep`). No `infra/dev/` directory needed.

### 5.3 Credential Strategy for Dev

| Service | Auth in Prod | Auth in Dev (Local) |
|---------|-------------|---------------------|
| Cosmos DB | `DefaultAzureCredential` (RBAC) | **Well-known emulator key** (key-based, `AccountKey=C2y6yDjf5/R+ob0N8A7Cgv...`) |
| Blob Storage | `DefaultAzureCredential` (RBAC) | **Azurite well-known key** (connection string) |
| AI Search | `DefaultAzureCredential` (RBAC) | **Simulator API key** (`AzureKeyCredential`, self-signed TLS cert, skip verify) |
| AI Services (LLM + Embeddings) | `DefaultAzureCredential` | **No auth needed** — Ollama `api_key='ollama'` (required but ignored) |

This means the application code needs a thin config layer that switches between:
- `DefaultAzureCredential` for production
- Connection-string/key-based auth for local emulators
- OpenAI-compatible client pointing at Ollama for LLM/embeddings

**Approach:** Use an `ENVIRONMENT` env var (`dev` | `prod`). When `ENVIRONMENT=dev`, config modules use emulator endpoints and keys, and point the OpenAI client at Ollama (`http://ollama:11434/v1/`). When `ENVIRONMENT=prod` (default), use `DefaultAzureCredential` and Azure endpoints.

## 6. Makefile Target Design

### 6.1 Dev (Local) Targets

```makefile
# === Dev (Local) — zero Azure dependency ===
dev-setup                      # Install tools (Docker, uv) + Python deps for all services
dev-infra-up                   # Pull images, start infra containers, pull Ollama models, init emulator resources
dev-infra-down                 # Stop and remove all dev infra containers
dev-services-up                # Build & start ALL app services in Docker
dev-services-down              # Stop all app service containers
  dev-services-pipeline-up     # Build & start fn-convert + fn-index only
  dev-services-app-up          # Build & start web-app only
  dev-services-agents-up       # Build & start agent only
dev-test                       # Run unit + integration tests
dev-ui                         # Open browser to http://localhost:8080

# Pipeline triggers (dev)
dev-pipeline                   # Run full KB pipeline locally (convert + index)
dev-pipeline-convert           # Run fn-convert only
dev-pipeline-index             # Run fn-index only
```

### 6.2 Prod (Azure) Targets

```makefile
# === Prod (Azure) ===
prod-infra-up                  # Provision full Azure prod RG (all resources)
prod-infra-down                # Delete Azure prod RG (destructive, confirmation required)
prod-services-up               # Build + deploy all services to Azure Container Apps
prod-services-down             # Scale down / stop all services (without deleting infra)
  prod-services-pipeline-up    # Deploy fn-convert + fn-index
  prod-services-app-up         # Deploy web-app
  prod-services-agents-up      # Deploy agent(s)
prod-ui-url                    # Print production web app URL

# Pipeline triggers (prod)
prod-pipeline                  # Run full KB pipeline in Azure (upload + convert + index)
prod-pipeline-convert          # Trigger fn-convert in Azure
prod-pipeline-index            # Trigger fn-index in Azure
```

### 6.3 Shared Targets

```makefile
# === Shared ===
help                           # Show all targets grouped by environment
set-project                    # Set PROJECT_NAME in AZD env (2-8 chars)
set-converter                  # Set CONVERTER in AZD env (markitdown | content-understanding | mistral-doc-ai)
```

### 6.4 Targets Removed

| Old Target | Replacement |
|-----------|-------------|
| `azure-up` | `prod-infra-up` + `prod-services-up` |
| `azure-kb` | `prod-pipeline` |
| `azure-test` | Merged into `dev-test` with `@pytest.mark.integration` |
| `azure-app-url` | `prod-ui-url` |
| `test-ui` / `test-ui-auto` | Dropped — no e2e tests in the new model |
| `setup-azure` | `prod-infra-up` (Azure only exists for prod) |
| `setup` | `dev-setup` (no alias needed) |
| `test` | `dev-test` (no alias needed) |

## 7. Test Strategy

### 7.1 Two tiers only

| Tier | Marker | What it tests | Infrastructure needed | When to run |
|------|--------|---------------|----------------------|-------------|
| **Unit** | (default, no marker) | Business logic, pure functions, mocked externals | None | Always, `make dev-test` |
| **Integration** | `@pytest.mark.integration` | Real service calls — search queries, Cosmos reads, blob access, LLM calls | Dev Docker infra running (`make dev-infra-up`) | `make dev-test` (with infra up) |

### 7.2 Changes

- **Remove `e2e` marker** — current "e2e" tests are actually integration tests that call deployed endpoints. Fold them into `integration`.
- **Integration tests run against local Docker infra** (emulators) when possible.
- **All integration tests run fully locally** — no Azure dependency. LLM calls go to Ollama, search to the simulator, storage to emulators.

### 7.3 Test Isolation — `-test` Resources

Integration tests must not pollute the dev working environment. All emulated storage services provision **parallel `-test` resources** that tests own exclusively (create/tear down per test run).

**Naming constraints from Azure:**
- **Blob container names:** lowercase letters, digits, and hyphens only (no underscores). 3-63 chars.
- **Cosmos DB database/container names:** most characters including hyphens allowed. Max 256 chars.
- **AI Search index names:** lowercase letters, digits, and hyphens only. 2-128 chars.

All test resources use the `-test` suffix (hyphens, not underscores) for consistency and Azure compatibility.

#### Actual resource names (validated against codebase):

| Service | Resource Type | Dev (working) | Test (integration tests) |
|---------|--------------|--------------|-------------------------|
| **Cosmos DB** | Database | `kb-agent` | `kb-agent-test` |
| **Cosmos DB** | Container | `agent-sessions` | `agent-sessions-test` |
| **Cosmos DB** | Container | `conversations` | `conversations-test` |
| **Cosmos DB** | Container | `messages` | `messages-test` |
| **Cosmos DB** | Container | `references` | `references-test` |
| **Blob Storage (Azurite)** | Blob container | `staging` | `staging-test` |
| **Blob Storage (Azurite)** | Blob container | `serving` | `serving-test` |
| **AI Search (Simulator)** | Index | `kb-articles` | `kb-articles-test` |

> **Note:** In prod, Azure uses two **separate storage accounts** (`st{project}staging{env}` and `st{project}serving{env}`), each with one blob container (`staging` and `serving` respectively). In dev, Azurite is a single storage account (`devstoreaccount1`) with both blob containers. This is fine — the code references containers by name via `STAGING_BLOB_ENDPOINT` / `SERVING_BLOB_ENDPOINT`, and in dev both point to the same Azurite account.

**How it works:**

1. **Startup script** (`scripts/dev-init-emulators.sh`) creates both dev and test resources when `dev-infra-up` runs:
   - Cosmos DB: databases `kb-agent` + `kb-agent-test`, each with containers: `agent-sessions`, `conversations`, `messages`, `references` (and their `-test` counterparts in the test database)
   - Azurite: blob containers `staging`, `serving`, `staging-test`, `serving-test`
   - AI Search Simulator: no pre-creation needed (tests create/delete indexes via SDK)

2. **Integration test fixtures** (in `conftest.py`) use the `-test` resource names:
   ```python
   @pytest.fixture
   def test_cosmos_database():
       """Return the -test Cosmos database name."""
       return "kb-agent-test"

   @pytest.fixture
   def test_search_index():
       """Return the -test search index name."""
       return "kb-articles-test"

   @pytest.fixture
   def test_blob_containers():
       """Return the -test blob container names."""
       return {"staging": "staging-test", "serving": "serving-test"}
   ```

3. **Test setup/teardown** — each integration test module or session-scoped fixture:
   - Creates the `-test` index / containers it needs (idempotent)
   - Seeds test data
   - Cleans up after itself (delete documents, or drop and recreate)

4. **Config** — integration tests set `COSMOS_DATABASE_NAME=kb-agent-test`, `SEARCH_INDEX_NAME=kb-articles-test`, etc. via environment or fixture override. The application config modules already read these from env vars, so no code changes needed — just different env values for test runs.

## 8. Docker Compose Design

### 8.1 `infra/docker/docker-compose.dev-infra.yml` — Emulators

```yaml
# Local infrastructure emulators
services:
  cosmosdb:
    image: mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview
    ports:
      - "8081:8081"    # Cosmos endpoint
      - "1234:1234"    # Data Explorer UI
    environment:
      - PROTOCOL=https
    healthcheck:
      test: ["CMD", "curl", "-fk", "https://localhost:8081/_explorer/emulator.pem"]
      interval: 10s
      timeout: 5s
      retries: 30

  azurite:
    image: mcr.microsoft.com/azure-storage/azurite:latest
    ports:
      - "10000:10000"  # Blob
      - "10001:10001"  # Queue
      - "10002:10002"  # Table
    volumes:
      - azurite-data:/data
    command: "azurite --blobHost 0.0.0.0 --queueHost 0.0.0.0 --tableHost 0.0.0.0"

  search-simulator:
    image: ghcr.io/ellerbach/azure-ai-search-simulator:latest
    ports:
      - "7250:8443"    # HTTPS (SDK-compatible)
      - "5250:8080"    # HTTP
    environment:
      - SimulatorSettings__AdminApiKey=dev-admin-key
      - SimulatorSettings__QueryApiKey=dev-query-key
    volumes:
      - search-data:/app/data
      - lucene-indexes:/app/lucene-indexes

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"   # OpenAI-compatible API
    volumes:
      - ollama-data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 10s
      timeout: 5s
      retries: 30

  aspire-dashboard:
    image: mcr.microsoft.com/dotnet/aspire-dashboard:latest
    ports:
      - "18888:18888"   # Dashboard UI
      - "18889:18889"   # OTLP gRPC receiver
    environment:
      - DOTNET_DASHBOARD_UNSECURED_ALLOW_ANONYMOUS=true

volumes:
  azurite-data:
  search-data:
  lucene-indexes:
  ollama-data:
```

> **Ollama model pull:** After `dev-infra-up`, the init script runs:
> ```
> docker exec ollama ollama pull phi4-mini
> docker exec ollama ollama pull mxbai-embed-large
> docker exec ollama ollama pull moondream
> ```
> Models are cached in the `ollama-data` volume. Subsequent starts skip the download.

### 8.2 `infra/docker/docker-compose.dev-services.yml` — Our Services

The `fn-convert` service builds the Dockerfile selected by the `CONVERTER` project parameter. The Makefile resolves the Dockerfile path before invoking `docker-compose`.

```yaml
# Application services (built from local Dockerfiles)
# CONVERTER_DOCKERFILE is set by Makefile based on AZD env CONVERTER value
services:
  fn-convert:
    build:
      context: ./src/functions
      dockerfile: ${CONVERTER_DOCKERFILE:-fn_convert_markitdown/Dockerfile}
    ports:
      - "7071:80"
    env_file: .env.dev
    depends_on:
      azurite:
        condition: service_healthy

  fn-index:
    build:
      context: ./src/functions
      dockerfile: fn_index/Dockerfile
    ports:
      - "7072:80"
    env_file: .env.dev
    depends_on:
      azurite:
        condition: service_healthy

  agent:
    build:
      context: ./src/agent
    ports:
      - "8088:8088"
    env_file: .env.dev
    depends_on:
      cosmosdb:
        condition: service_healthy

  web-app:
    build:
      context: ./src/web-app
    ports:
      - "8080:8080"
    env_file: .env.dev
    environment:
      - AGENT_ENDPOINT=http://agent:8088
    depends_on:
      - agent
      - cosmosdb
```

### 8.3 `.env.dev` Template

```env
# === Local emulators ===
ENVIRONMENT=dev
COSMOS_ENDPOINT=https://localhost:8081
COSMOS_KEY=C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==
COSMOS_DATABASE_NAME=kb-agent
STAGING_BLOB_ENDPOINT=http://localhost:10000/devstoreaccount1
SERVING_BLOB_ENDPOINT=http://localhost:10000/devstoreaccount1
AZURITE_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://localhost:10000/devstoreaccount1;
SEARCH_ENDPOINT=https://localhost:7250
SEARCH_ADMIN_KEY=dev-admin-key
SEARCH_QUERY_KEY=dev-query-key

# === Ollama (local LLM + embeddings + vision) ===
OLLAMA_ENDPOINT=http://localhost:11434/v1
OLLAMA_CHAT_MODEL=phi4-mini
OLLAMA_EMBEDDING_MODEL=mxbai-embed-large
OLLAMA_VISION_MODEL=moondream

# === Model deployment overrides (point at Ollama models) ===
AGENT_MODEL_DEPLOYMENT_NAME=phi4-mini
EMBEDDING_DEPLOYMENT_NAME=mxbai-embed-large
SUMMARY_DEPLOYMENT_NAME=phi4-mini

# === Auth ===
REQUIRE_AUTH=false

# === Observability (Aspire Dashboard) ===
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:18889
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
```

## 9. Code Changes Required

### 9.1 Config Module Updates

Both `src/functions/shared/config.py` and `src/agent/agent/config.py` need:

1. **Read `ENVIRONMENT` env var** (default: `prod`).
2. **When `ENVIRONMENT=dev`:**
   - Cosmos DB: use `COSMOS_KEY` + `COSMOS_ENDPOINT` (key-based auth).
   - Blob Storage: use `AZURITE_CONNECTION_STRING` (connection string auth).
   - AI Search: use `AzureKeyCredential(SEARCH_ADMIN_KEY)` + `SEARCH_ENDPOINT` (API key auth, skip TLS verify for self-signed cert).
   - LLM (chat): use OpenAI SDK pointing at Ollama (`OLLAMA_ENDPOINT`, model `OLLAMA_CHAT_MODEL`).
   - Embeddings: use OpenAI SDK pointing at Ollama (`OLLAMA_ENDPOINT`, model `OLLAMA_EMBEDDING_MODEL`).
3. **When `ENVIRONMENT=prod` (default):**
   - All services: use `DefaultAzureCredential` (RBAC, managed identity).
   - LLM + embeddings: use Azure AI Services endpoint.

### 9.2 Client Factory Pattern

Create thin factory functions that return the right client based on environment:

```python
# Example: cosmos_client_factory.py
def create_cosmos_client(config: Config) -> CosmosClient:
    if config.environment == "dev":
        return CosmosClient(config.cosmos_endpoint, credential=config.cosmos_key)
    return CosmosClient(config.cosmos_endpoint, credential=DefaultAzureCredential())
```

Similar for `BlobServiceClient` and `SearchClient`:

```python
# Example: search_client_factory.py
def create_search_client(config: Config, index_name: str) -> SearchClient:
    if config.environment == "dev":
        # AI Search Simulator: API key + skip self-signed cert verification
        import requests
        from azure.core.credentials import AzureKeyCredential
        from azure.core.pipeline.transport import RequestsTransport
        session = requests.Session()
        session.verify = False
        transport = RequestsTransport(session=session, connection_verify=False)
        return SearchClient(
            config.search_endpoint, index_name,
            AzureKeyCredential(config.search_admin_key),
            transport=transport, connection_verify=False,
        )
    return SearchClient(
        config.search_endpoint, index_name,
        DefaultAzureCredential(),
    )
```

For LLM / embeddings, create an OpenAI client factory:

```python
# Example: openai_client_factory.py
from openai import AsyncAzureOpenAI, AsyncOpenAI

def create_openai_client(config: Config) -> AsyncOpenAI:
    if config.environment == "dev":
        # Ollama: OpenAI-compatible API, no auth needed
        return AsyncOpenAI(
            base_url=config.ollama_endpoint,  # http://ollama:11434/v1
            api_key="ollama",                 # required but ignored
        )
    # Prod: Azure AI Services with managed identity
    return AsyncAzureOpenAI(
        azure_endpoint=config.ai_services_endpoint,
        azure_ad_token_provider=get_token_provider(),
    )
```

### 9.3 All Azure SDK Call Sites (Audit)

For full zero-Azure dev, **every** `DefaultAzureCredential` / Azure SDK call site needs a dev-mode alternative. Here is the exhaustive list from the codebase:

#### LLM / Embedding / Vision (→ Ollama in dev)

| File | Current SDK | Dev Replacement | Ollama Model |
|------|------------|-----------------|-------------|
| `src/agent/agent/kb_agent.py` | `AzureOpenAIChatClient` (agent-framework) | `OpenAIChatClient` → Ollama | `phi4-mini` |
| `src/functions/fn_index/embedder.py` | `EmbeddingsClient` (azure-ai-inference) | OpenAI SDK `/v1/embeddings` → Ollama | `mxbai-embed-large` |
| `src/functions/fn_index/summarizer.py` | `ChatCompletionsClient` (azure-ai-inference) | OpenAI SDK `/v1/chat/completions` → Ollama | `phi4-mini` |
| `src/functions/fn_convert_markitdown/describe_images.py` | `AzureOpenAI` (openai SDK) | `OpenAI` → Ollama | `moondream` |
| `src/functions/fn_convert_mistral/describe_images.py` | `AzureOpenAI` | N/A — Mistral converter is Azure-only (not used in dev) | — |
| `src/functions/fn_convert_cu/...` | Content Understanding SDK | N/A — CU converter is Azure-only (not used in dev) | — |

#### Storage / Data (→ Emulators in dev)

| File | Current SDK | Dev Replacement |
|------|------------|-----------------|
| `src/web-app/app/data_layer.py` | `CosmosClient` + `DefaultAzureCredential` | `CosmosClient` + emulator key |
| `src/web-app/app/image_service.py` | `BlobServiceClient` + `DefaultAzureCredential` | `BlobServiceClient` + Azurite connection string |
| `src/agent/agent/session_repository.py` | `CosmosClient` (async) + `DefaultAzureCredential` | `CosmosClient` + emulator key |
| `src/agent/agent/image_service.py` | `BlobServiceClient` + `DefaultAzureCredential` | `BlobServiceClient` + Azurite connection string |
| `src/agent/agent/search_tool.py` | `SearchClient` + `DefaultAzureCredential` | `SearchClient` + `AzureKeyCredential` (simulator API key) |
| `src/functions/shared/blob_storage.py` | `BlobServiceClient` + `DefaultAzureCredential` | `BlobServiceClient` + Azurite connection string |
| `src/functions/fn_index/indexer.py` | `SearchClient` + `SearchIndexClient` + `DefaultAzureCredential` | Same clients + `AzureKeyCredential` (simulator API key) |

#### No Change Needed

| File | Reason |
|------|--------|
| `src/web-app/app/main.py` (`_create_agent_client`) | Uses `OpenAI(base_url=http://agent:8088)` for HTTP endpoints — already works with dev |
| `src/agent/main.py` (`from_agent_framework`) | Local HTTP server adapter — no Foundry dependency |
| `src/agent/middleware/jwt_auth.py` | `REQUIRE_AUTH=false` bypasses JWT validation in dev |

**Summary:** 11 files need dev-mode factories (4 LLM/embedding/vision + 7 storage/data). All changes are config-driven via `ENVIRONMENT=dev`.

**Additional dev-mode env vars needed:**

| Env Var | Purpose | Used By |
|---------|---------|---------|
| `REQUIRE_AUTH=false` | Skip JWT validation in agent middleware | `src/agent/middleware/jwt_auth.py` |
| `SUMMARY_DEPLOYMENT_NAME=phi4-mini` | Override summarizer model for Ollama | `src/functions/fn_index/summarizer.py` |
| `EMBEDDING_DEPLOYMENT_NAME=mxbai-embed-large` | Override embedding model for Ollama | `src/functions/fn_index/embedder.py` (via `shared/config.py`) |
| `AGENT_MODEL_DEPLOYMENT_NAME=phi4-mini` | Override agent model for Ollama | `src/agent/agent/config.py` |

### 9.4 Cosmos DB Emulator TLS

The Cosmos DB emulator uses a self-signed certificate. For Python SDK:
- Set environment variable: `COSMOS_EMULATOR_DISABLE_SSL=true` or
- Import the emulator's certificate, or
- Use HTTP mode on the vNext emulator (recommended for dev simplicity)

### 9.5 Azurite Container Initialization

Azurite starts empty. The initialization script (`scripts/dev-init-emulators.sh`) creates all required blob containers on startup:

**Dev blob containers:**
- `staging` — source articles for fn-convert
- `serving` — processed output for fn-index and image serving

**Test blob containers (integration test isolation):**
- `staging-test` — used exclusively by integration tests
- `serving-test` — used exclusively by integration tests

**Cosmos DB databases:**
- `kb-agent` (dev) with containers: `agent-sessions`, `conversations`, `messages`, `references`
- `kb-agent-test` (test) with containers: `agent-sessions-test`, `conversations-test`, `messages-test`, `references-test`

Can use `az storage container create` with Azurite connection string, or a small Python init script.

## 10. Infra — Prod Only (No Dev Bicep)

Since dev has **zero Azure dependency**, there is no `infra/dev/` directory. Bicep exists only for prod under `infra/azure/infra/`.

### 10.1 `infra/azure/infra/main.bicep` — Production (unchanged)

~15 module calls, roles, wiring for full Azure deployment via `azd provision`. This is the only Bicep that exists.

### 10.2 No dev Bicep needed

Dev infrastructure is 100% Docker-based. No Azure resources, no Bicep for dev.

## 11. Migration Steps (Implementation Order)

### Phase 1: Foundation
1. [ ] Create `infra/docker/docker-compose.dev-infra.yml` with Cosmos emulator + Azurite + AI Search Simulator + Ollama + Aspire Dashboard
2. [ ] Create `.env.dev.template` with emulator + Ollama connection details
3. [ ] Create `scripts/dev-init-emulators.sh` — init dev + `-test` resources (Cosmos DBs + containers, blob containers) + pull Ollama models (`phi4-mini`, `mxbai-embed-large`, `moondream`)
4. [ ] Add `ENVIRONMENT` env var to config modules (`shared/config.py`, `agent/config.py`)
5. [ ] Create client factory functions for Cosmos DB, Blob Storage, Search, and OpenAI/Ollama
6. [ ] Add dev-mode factories for **all 11 Azure SDK call sites** (see Section 9.3 audit):
   - **LLM/embedding/vision (4 files):**
     - `src/agent/agent/kb_agent.py` — `AzureOpenAIChatClient` → `OpenAIChatClient` (Ollama)
     - `src/functions/fn_index/embedder.py` — `EmbeddingsClient` → OpenAI `/v1/embeddings` (Ollama)
     - `src/functions/fn_index/summarizer.py` — `ChatCompletionsClient` → OpenAI `/v1/chat/completions` (Ollama)
     - `src/functions/fn_convert_markitdown/describe_images.py` — `AzureOpenAI` → `OpenAI` (Ollama `moondream`)
   - **Storage/data (7 files):**
     - `src/web-app/app/data_layer.py` — `CosmosClient` → emulator key
     - `src/web-app/app/image_service.py` — `BlobServiceClient` → Azurite
     - `src/agent/agent/session_repository.py` — `CosmosClient` → emulator key
     - `src/agent/agent/image_service.py` — `BlobServiceClient` → Azurite
     - `src/agent/agent/search_tool.py` — `SearchClient` → simulator API key
     - `src/functions/shared/blob_storage.py` — `BlobServiceClient` → Azurite
     - `src/functions/fn_index/indexer.py` — `SearchClient` + `SearchIndexClient` → simulator API key
7. [ ] Verify web-app and agent work against local emulators + Ollama

### Phase 2: Makefile + Services
8. [ ] Create `infra/docker/docker-compose.dev-services.yml` for our application containers
9. [ ] Rewrite Makefile with `dev-*` and `prod-*` target structure + `set-converter`

### Phase 3: Test Consolidation
10. [ ] Remove `e2e` test marker — merge into `integration`
11. [ ] Create shared test fixtures for `-test` resources (conftest.py per service)
12. [ ] Update integration tests to use `-test` resources, local emulators, and Ollama
13. [ ] Ensure `make dev-test` runs unit tests (always) + integration (when infra is up)

### Phase 4: Cleanup
14. [ ] Update `docs/setup-and-makefile.md` with new workflow
15. [ ] Update `docs/specs/infrastructure.md` — remove dev infra references
16. [ ] Remove old Makefile targets (`azure-up`, `setup-azure`, etc.)

## 12. Open Questions

1. **fn-convert variants in dev:** ~~Do we run all 3 converters?~~ → **Resolved.** Only the converter selected by `CONVERTER` project parameter is built/deployed. One converter at a time, set via `make set-converter converter=<value>`. Default is `markitdown`.

2. **AI Search in dev:** ~~Should we use the Free tier in dev RG?~~ → **Resolved.** Use the [Azure AI Search Simulator](https://github.com/Ellerbach/azure-ai-search-simulator) Docker container locally. Supports full-text, vector, and hybrid search with the official Python SDK. No Azure instance needed for dev at all.

3. **Functions runtime in Docker:** Azure Functions containers use the `mcr.microsoft.com/azure-functions/python:4-python3.11` base image which expects the Functions host. For local Docker dev, should we keep the Functions host or run the Python code directly (as a simple HTTP server)? → **Recommendation: Keep Functions host in Docker** — matches prod runtime, avoids divergence.

## 13. Estimated Impact

| Metric | Current | After |
|--------|---------|-------|
| Azure resources needed for dev | ~15 (full RG) | **0** — zero Azure dependency |
| Monthly dev Azure cost | ~$50-100 (all resources) | **$0** |
| Azure subscription required for dev | Yes | **No** |
| Time to start dev environment | 5-10 min (Azure provision) | ~60 sec (Docker up) + first-time model pull |
| Services requiring `az login` | All | **None** (dev is fully local) |
| Docker containers for dev infra | 0 | 5 (Cosmos emu + Azurite + Search sim + Ollama + Aspire) |
| Docker containers for dev services | 0 | 4 (fn-convert + fn-index + agent + web-app) |
| Total Docker containers | 0 | 9 |
| Local disk for Ollama models | 0 | ~4.9 GB (`phi4-mini` 2.5 GB + `mxbai-embed-large` 670 MB + `moondream` 1.7 GB) |
| GPU VRAM usage (RTX A2000 4 GB) | N/A | ~2.5 GB for phi4-mini, ~670 MB for embeddings, ~1.7 GB for moondream (one model loaded at a time) |
