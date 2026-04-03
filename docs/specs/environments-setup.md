# Environments Setup

> **Status:** Draft — March 26, 2026
> **Status:** Updated — March 26, 2026

## Overview

Two environments: **Dev** (fully local, Docker-only) and **Prod** (Azure). No staging environment — can be added later as a prod clone with a different AZD env name.

## Target Environments

| Environment | Infra Location | Services Run As | LLM / Embeddings Source | Purpose |
|-------------|---------------|-----------------|------------------------|--------|
| **Dev** (local) | Docker containers only — **zero Azure cloud dependency** | Docker containers (our code + emulators + Ollama) | Ollama (local): `qwen2.5:3b` for chat, `mxbai-embed-large` for embeddings, `moondream` for vision | Daily development, fast iteration, unit + integration tests |
| **Prod** | Azure RG (`rg-{project}-prod`) | Azure Container Apps | Azure AI Services (GPT-4.1, text-embedding-3-small, GPT-4.1 vision) | Production |

**Key design decision:** Dev has **no Azure cloud dependency**. All runtime infrastructure runs in Docker under `infra/docker/`. Azure IaC and AZD assets live under `infra/azure/`. AZD may still be used locally as a parameter store for `PROJECT_NAME` and `CONVERTER`, but dev does not require `az login`, an Azure subscription, or Azure spend.

## Project-Level Parameters

Two parameters stored in AZD env: `PROJECT_NAME` is shared across environment workflows, while `CONVERTER` is used by prod deploy and pipeline targets.

| Parameter | AZD Env Key | Values | Default | Set via |
|-----------|-------------|--------|---------|--------|
| **Project name** | `PROJECT_NAME` | 2–8 chars | _(required)_ | `make set-project name=<value>` |
| **Converter** | `CONVERTER` | `markitdown`, `content-understanding`, `mistral-doc-ai` | `markitdown` | `make set-converter converter=<value>` |

`CONVERTER` is a prod-only selector for deploy and pipeline targets. Local dev always runs the MarkItDown converter. The implemented model keeps the current three-service prod converter topology in Azure and uses `CONVERTER` as an operational selector, not as an Azure-enforced exclusivity switch.

## Service Dependency Map

| Service | Cosmos DB | AI Search | Blob Storage | AI Services / LLM | Foundry Project |
|---------|-----------|-----------|-------------|-------------------|-----------------|
| **web-app** (Next.js + CopilotKit) | Yes (conversations) | No | Yes (serving images) | No | No |
| **agent** | Yes (agent-sessions) | Yes (kb-articles index) | Yes (serving images) | Yes (GPT model for reasoning) | Yes (prod only — agent registration) |
| **fn-convert** (all variants) | No | No | Yes (staging read, serving write) | Yes (image analysis) | No |
| **fn-index** | No | Yes (push chunks to index) | Yes (serving read — images) | Yes (embeddings) | No |

## Dev Environment — Docker Topology

```
┌─ infra/docker/docker-compose.dev-infra.yml + infra/docker/docker-compose.dev-services.yml ─┐
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
│  │   :3000      │  ← browser UI entry point                   │
│  └──────────────┘                                              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
                 No Azure dependency ✓
```

9 containers total: 5 infrastructure + 4 application services.

## Azure Service Emulation Mapping

| Azure Service (prod) | Local Replacement (dev) | Docker Image | Ports | Auth |
|----------------------|------------------------|-------------|-------|------|
| **Cosmos DB** | Cosmos DB Linux Emulator (vNext preview) | `mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview` | 8081 (API), 1234 (UI) | Well-known emulator key |
| **Azure Blob Storage** | Azurite | `mcr.microsoft.com/azure-storage/azurite:latest` | 10000 (Blob), 10001 (Queue), 10002 (Table) | Well-known key / connection string |
| **Azure AI Search** | AI Search Simulator | `ghcr.io/ellerbach/azure-ai-search-simulator:latest` | 7250 (HTTPS), 5250 (HTTP) | API key (`dev-admin-key`) |
| **AI Services (LLM)** | Ollama — `qwen2.5:3b` | `ollama/ollama` (GPU optional) | 11434 | No auth (key required but ignored) |
| **AI Services (Embeddings)** | Ollama — `mxbai-embed-large` | (same ollama) | 11434 | No auth |
| **AI Services (Vision)** | Ollama — `moondream` | (same ollama) | 11434 | No auth |
| **Foundry Project** | Not needed | N/A | N/A | Agent runs as local HTTP service |
| **App Insights / Log Analytics** | Aspire Dashboard | `mcr.microsoft.com/dotnet/aspire-dashboard:latest` | 18888 (UI), 18889 (OTLP) | Anonymous |

## Ollama Models

Target hardware minimum for comfortable local inference: **32 GB RAM + RTX 1050 4 GB VRAM**. The local stack now starts in CPU-compatible mode by default; a GPU improves latency but is no longer required just to boot the dev environment.

| Model | Role | Size | Fits 4 GB VRAM? | Notes |
|-------|------|------|-----------------|-------|
| `qwen2.5:3b` | Chat / reasoning (agent, summarizer) | 1.9 GB | Yes | Qwen 2.5 3B Instruct. 128K context, strong structured-output behavior, and validated locally to return proper OpenAI-style `tool_calls` through Ollama. |
| `mxbai-embed-large` | Embeddings (fn-index) | 670 MB | Yes | 335M params, 1024-dim vectors. MTEB SOTA for BERT-large class. End-state code must read vector dimensions from config in dev. |
| `moondream` | Vision / image analysis (fn-convert) | 1.7 GB | Yes | moondream2. 1.8B params, image+text input. Edge-optimized. |

Total local disk: ~4.9 GB. Models load one at a time into VRAM.

> **Quality caveat:** `qwen2.5:3b` is still much smaller than Azure GPT-4.1. Integration tests validate **data flow and connectivity**, not production answer quality. Quality evaluation must use prod models.

## Vector Dimensions

Vector dimensions are environment-specific in the target design:

| Environment | Embedding model | Vector dimensions |
|------------|-----------------|-------------------|
| **Dev** | `mxbai-embed-large` | `1024` |
| **Prod** | `text-embedding-3-small` | `1536` |

The index schema, query embedding path, and tests must read `EMBEDDING_VECTOR_DIMENSIONS` from configuration instead of hard-coding `1536`.

## Two-Layer API Architecture

```
web-app  ──Responses API──▶  agent (FastAPI /v1/responses)
                                   │
                                   ▼  internally
                           AzureOpenAIChatClient (prod) / OpenAIChatClient (dev)
                                   │
                           Chat Completions API
                                   │
                          ▼ prod: Azure AI Services
                          ▼ dev:  Ollama
```

**Layer 1 — External (web-app → agent):** The agent exposes an OpenAI-compatible Responses API (`/v1/responses`). This is our own FastAPI code — runs identically in dev and prod.

**Layer 2 — Internal (agent → LLM backend):** The agent framework uses Chat Completions API (`/v1/chat/completions`). Dev uses `OpenAIChatClient` → Ollama. Prod uses `AzureOpenAIChatClient` → Azure AI Services.

| Concern | Dev (Ollama) | Prod (Azure) |
|---------|-------------|-------------|
| Agent framework client | `OpenAIChatClient` | `AzureOpenAIChatClient` |
| LLM API | `/v1/chat/completions` → Ollama | `/v1/chat/completions` → Azure AI Services |
| Embeddings API | `/v1/embeddings` → Ollama | `/v1/embeddings` → Azure AI Services |
| Vision (fn-convert) | `/v1/chat/completions` + `image_url` → Ollama (`moondream`) | `/v1/chat/completions` + `image_url` → Azure (GPT-4.1) |
| Tool calling | Supported (`qwen2.5:3b`) | Supported (GPT-4.1) |
| Streaming | Supported | Supported |

## Credential Strategy

| Service | Auth in Prod | Auth in Dev (Local) |
|---------|-------------|---------------------|
| Cosmos DB | `DefaultAzureCredential` (RBAC) | Well-known emulator key |
| Blob Storage | `DefaultAzureCredential` (RBAC) | Azurite well-known connection string |
| AI Search | `DefaultAzureCredential` (RBAC) | Simulator API key (`AzureKeyCredential`) |
| AI Services (LLM + Embeddings) | `DefaultAzureCredential` | Ollama (`api_key='ollama'`, required but ignored) |

Switching is driven by `ENVIRONMENT` env var (`dev` | `prod`). Code uses factory functions that return the correct client for each environment.

## Resource Naming

### Dev (emulators)

| Service | Resource Type | Dev (working) | Test (integration tests) |
|---------|--------------|--------------|-------------------------|
| **Cosmos DB** | Database | `kb-agent` | `kb-agent-test` |
| **Cosmos DB** | Container | `agent-sessions` | `agent-sessions-test` |
| **Cosmos DB** | Container | `conversations` | `conversations-test` |
| **Cosmos DB** | Container (deprecated compatibility) | `messages` | `messages-test` |
| **Cosmos DB** | Container (deprecated compatibility) | `references` | `references-test` |
| **Blob Storage** | Blob container | `staging` | `staging-test` |
| **Blob Storage** | Blob container | `serving` | `serving-test` |
| **AI Search** | Index | `kb-articles` | `kb-articles-test` |

> Test resources use `-test` suffix (hyphens, not underscores) where the target resource type allows it. For Azure Blob container names, `staging-test` and `serving-test` are valid; Azure storage account names are a separate rule set and remain lowercase alphanumeric only.

> In prod, Azure uses two separate storage accounts (`st{project}staging{env}` and `st{project}serving{env}`). In dev, Azurite is a single account (`devstoreaccount1`) with both blob containers.

### Prod (Azure)

Prod resources follow the existing Bicep naming patterns in `infra/azure/infra/main.bicep` — e.g., `cosmos-{project}-{env}`, `st{project}staging{env}`, `srch-{project}-{env}`.

## Observability

| Concern | Dev (local) | Prod (Azure) |
|---------|------------|-------------|
| Telemetry collector | Aspire Dashboard (Docker) | Azure Monitor / App Insights |
| Protocol | OpenTelemetry (OTLP gRPC) | OpenTelemetry (OTLP gRPC) → App Insights |
| Traces UI | `http://localhost:18888` | Azure Portal → App Insights |
| Logs | Aspire Dashboard structured logs | App Insights → Logs (KQL) |
| Metrics | Aspire Dashboard metrics view | App Insights → Metrics |
| Agent tracing | OpenTelemetry spans via OTLP | Foundry tracing + App Insights |
| Config | `OTEL_EXPORTER_OTLP_ENDPOINT=http://aspire-dashboard:18889` | `APPLICATIONINSIGHTS_CONNECTION_STRING` (auto via Bicep) |

Both environments use OpenTelemetry as the telemetry protocol. Only the exporter destination differs.

## `.env.dev` Template

The checked-in template uses Docker Compose service hostnames. If you run a client directly from the host machine, replace service hostnames with `localhost` equivalents.

```env
# === Environment ===
ENVIRONMENT=dev

# === Local emulators ===
COSMOS_ENDPOINT=https://localhost:8081
COSMOS_KEY=C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==
COSMOS_DATABASE_NAME=kb-agent
COSMOS_SESSIONS_CONTAINER=agent-sessions
COSMOS_CONVERSATIONS_CONTAINER=conversations
COSMOS_MESSAGES_CONTAINER=messages  # deprecated compatibility only
COSMOS_REFERENCES_CONTAINER=references  # deprecated compatibility only
STAGING_BLOB_ENDPOINT=http://localhost:10000/devstoreaccount1
SERVING_BLOB_ENDPOINT=http://localhost:10000/devstoreaccount1
STAGING_CONTAINER_NAME=staging
SERVING_CONTAINER_NAME=serving
AZURITE_CONNECTION_STRING=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://localhost:10000/devstoreaccount1;
SEARCH_ENDPOINT=https://localhost:7250
SEARCH_ADMIN_KEY=dev-admin-key
SEARCH_QUERY_KEY=dev-query-key

# === Ollama (local LLM + embeddings + vision) ===
OLLAMA_ENDPOINT=http://localhost:11434/v1
OLLAMA_CHAT_MODEL=qwen2.5:3b
OLLAMA_EMBEDDING_MODEL=mxbai-embed-large
OLLAMA_VISION_MODEL=moondream
EMBEDDING_VECTOR_DIMENSIONS=1024

# === Model deployment overrides ===
AGENT_MODEL_DEPLOYMENT_NAME=qwen2.5:3b
EMBEDDING_DEPLOYMENT_NAME=mxbai-embed-large
SUMMARY_DEPLOYMENT_NAME=qwen2.5:3b

# === Auth ===
REQUIRE_AUTH=false

# === Observability (Aspire Dashboard) ===
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:18889
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
```

Only `agent-sessions` and `conversations` are part of the active runtime model. `messages` and `references` remain provisioned for compatibility with legacy tooling and data only.

## Makefile Targets

### Dev (Local) — zero Azure cloud dependency

| Target | Description |
|--------|------------|
| `dev-setup` | Install tools (Docker, uv) + Python deps for all services |
| `dev-infra-up` | Pull images, start infra containers, pull Ollama models, init emulator resources |
| `dev-infra-down` | Stop and remove all dev infra containers |
| `dev-services-up` | Build & start ALL app services in Docker |
| `dev-services-down` | Stop all app service containers |
| `dev-services-pipeline-up` | Build & start fn-convert + fn-index only |
| `dev-services-app-up` | Build & start web-app only |
| `dev-services-agents-up` | Build & start agent only |
| `dev-test` | Run unit + integration tests |
| `dev-test-ui` | Run optional browser-based UI tests |
| `dev-ui` | Open browser to http://localhost:3000 |
| `dev-pipeline` | Run full KB pipeline locally (convert + index) |
| `dev-pipeline-convert` | Run fn-convert only (MarkItDown in dev) |
| `dev-pipeline-index` | Run fn-index only |

### Prod (Azure)

| Target | Description |
|--------|------------|
| `prod-infra-up` | Provision full Azure prod RG |
| `prod-infra-down` | Delete Azure prod RG (destructive, confirmation required) |
| `prod-services-up` | Build + deploy web-app, agent, fn-index, and the selected converter service for the current workflow; other converter services may still remain provisioned in Azure |
| `prod-services-down` | Print scale-down guidance for deployed services |
| `prod-services-pipeline-up` | Deploy the selected converter service for the current workflow + fn-index |
| `prod-services-app-up` | Deploy web-app |
| `prod-services-agents-up` | Deploy agent(s) |
| `prod-ui-url` | Print production web app URL |
| `prod-pipeline` | Run full KB pipeline in Azure |
| `prod-pipeline-convert` | Trigger fn-convert in Azure |
| `prod-pipeline-index` | Trigger fn-index in Azure |

### Shared

| Target | Description |
|--------|------------|
| `help` | Show all targets grouped by environment |
| `set-project` | Set `PROJECT_NAME` in AZD env |
| `set-converter` | Set `CONVERTER` in AZD env for prod deploy/pipeline targets |

## Test Strategy

Three practical tiers:

| Tier | Marker | Infrastructure | When |
|------|--------|---------------|------|
| **Unit** | (default, no marker) | None | Always |
| **Integration** | `@pytest.mark.integration` | Dev Docker infra running | `make dev-test` |
| **UI** | `@pytest.mark.uitest` | Dev infra + running app services + browser tooling | `make dev-test-ui` |

All integration tests run fully locally against Docker emulators and Ollama. No Azure dependency for any test tier.
