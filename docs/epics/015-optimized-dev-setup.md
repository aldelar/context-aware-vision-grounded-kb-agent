# Epic 015 — Optimized Dev Setup (Zero Azure Cloud Dependency)

> **Status:** Draft
> **Created:** March 26, 2026
> **Updated:** March 26, 2026

## Objective

Replace the current Azure-dependent local development workflow with a **zero-Azure-cloud, Docker-only dev environment**. All Azure service dependencies are replaced by local emulators (Cosmos DB emulator, Azurite, AI Search Simulator) and Ollama for LLM/embedding/vision. Separate Makefile targets for `dev-*` and `prod-*` with a clean environment-driven config layer.

After this epic:

- **Zero Azure cloud dependency for dev** — no `az login`, no Azure subscription, no cloud cost for local development; AZD can still be used locally as a parameter store
- **Docker-only dev infrastructure** — 5 infrastructure containers (Cosmos emulator, Azurite, AI Search Simulator, Ollama, Aspire Dashboard)
- **Containerized application services** — all 4 services (fn-convert, fn-index, agent, web-app) run in Docker
- **Ollama for local LLM** — `phi4-mini` (chat), `mxbai-embed-large` (embeddings), `moondream` (vision)
- **Environment-aware vector dimensions** — dev uses 1024-dim embeddings, prod stays on the repo's current 1536-dim Azure embeddings
- **Environment-driven config** — `ENVIRONMENT=dev|prod` switches between emulator/Ollama auth and Azure/managed-identity auth via factory functions
- **Local converter is fixed** — Docker Compose always runs MarkItDown locally; `CONVERTER` only affects Azure deploy/pipeline selection
- **Current prod converter topology retained** — `azure.yaml` / `infra/main.bicep` keep the three converter services; `CONVERTER` selects the operationally active one for deploy and pipeline targets unless infra is later made conditional
- **Clean Makefile** — `dev-*` and `prod-*` target namespaces with shared `help`, `set-project`, `set-converter`
- **Practical test taxonomy** — unit + integration by default, optional `uitest` browser tier kept separate
- **Aspire Dashboard** — local OpenTelemetry observability (traces, logs, metrics) matching prod App Insights

## Success Criteria

- [ ] `docker-compose.dev-infra.yml` starts all 5 infrastructure containers
- [ ] `docker-compose.dev-services.yml` builds and starts all 4 application containers
- [ ] `docker-compose.dev-services.yml` builds local `fn-convert` from `fn_convert_markitdown/Dockerfile`
- [ ] Ollama serves `phi4-mini`, `mxbai-embed-large`, and `moondream` models
- [ ] `ENVIRONMENT=dev` config switch routes all SDK clients to local emulators/Ollama
- [ ] `EMBEDDING_VECTOR_DIMENSIONS` drives dev (`1024`) vs prod (`1536`) vector behavior across index creation, query embedding, and tests
- [ ] 11 Azure SDK call sites updated with dev-mode factories (4 LLM/embedding/vision + 7 storage/data)
- [ ] `src/web-app/app/config.py` participates in the same dev/prod config model as the agent and functions
- [ ] `DefaultAzureCredential` used in prod; emulator keys/connection strings in dev
- [ ] AI Search Simulator handles vector + full-text search via official Python SDK
- [ ] Aspire Dashboard collects OpenTelemetry traces from all services
- [ ] `.env.dev.template` documents all required env vars for dev
- [ ] `scripts/dev-init-emulators.sh` initializes all emulator resources (Cosmos DBs, blob containers, Ollama models)
- [ ] Integration tests use `-test` suffixed resources where supported by the resource type (e.g. `kb-agent-test`, `staging-test`, `kb-articles-test`); storage account names remain lowercase alphanumeric only
- [ ] Browser tests remain under `@pytest.mark.uitest` and stay out of default `dev-test`
- [ ] `e2e` terminology removed from test strategy/docs where practical; service-backed tests use `integration`
- [ ] Makefile rewritten with `dev-*` / `prod-*` targets
- [ ] `CONVERTER` maps to existing prod AZD service names without changing the current 3-service Azure topology
- [ ] `make dev-infra-up && make dev-services-up` brings up full working local environment
- [ ] `make dev-test` runs unit + integration tests against local Docker infra
- [ ] `make dev-test-ui` runs optional browser tests separately
- [ ] `make dev-pipeline` runs full KB pipeline locally (convert + index)
- [ ] Full local end-to-end: user asks question in web-app → agent queries local Search Simulator → returns answer
- [ ] `docs/specs/environments-setup.md` reflects the final environment definitions
- [ ] `docs/setup-and-makefile.md` updated with new workflow
- [ ] Epic doc updated with completion status

---

## Background

See [docs/research/008-optimized-dev-setup.md](../research/008-optimized-dev-setup.md) for the full research document covering emulator selection, Ollama model comparison, API architecture analysis, and resource naming audit.

See [docs/specs/environments-setup.md](../specs/environments-setup.md) for the target environment definitions.

### Current vs. Target

| Aspect | Current | After Epic 015 |
|--------|---------|----------------|
| Dev Azure dependency | Full RG (~15 resources) | **Zero Azure cloud dependency** — all runtime infra in Docker |
| Dev monthly cost | ~$50–100 | **$0** |
| `az login` for dev | Required | **Not needed** |
| Local emulators | None | Cosmos emu + Azurite + Search Simulator + Ollama + Aspire |
| LLM for dev | Azure AI Services | Ollama (`phi4-mini`, `mxbai-embed-large`, `moondream`) |
| Vector dimensions | Hard-coded 1536 | Config-driven: 1024 in dev, 1536 in prod |
| Docker containers | 0 | 9 (5 infra + 4 services) |
| Makefile structure | Mixed local/Azure | Clean `dev-*` / `prod-*` namespaces |
| Converter topology | 3 Azure converter services, manually chosen | Dev always uses MarkItDown locally; prod keeps the same 3 Azure services and `CONVERTER` selects the operationally active one |
| Test tiers | unit + integration + optional uitest | unit + integration by default, optional uitest |
| Auth in dev | `DefaultAzureCredential` → Azure | Emulator keys + Ollama (no auth) |
| Observability in dev | None | Aspire Dashboard (OpenTelemetry) |
| Config switching | Per-service env vars | `ENVIRONMENT=dev\|prod` + factory functions |

### Files Requiring Dev-Mode Factories (11 files)

#### LLM / Embedding / Vision (4 files → Ollama in dev)

| File | Current SDK | Dev Replacement | Ollama Model |
|------|------------|-----------------|-------------|
| `src/agent/agent/kb_agent.py` | `AzureOpenAIChatClient` | `OpenAIChatClient` → Ollama | `phi4-mini` |
| `src/functions/fn_index/embedder.py` | `EmbeddingsClient` (azure-ai-inference) | OpenAI SDK `/v1/embeddings` → Ollama | `mxbai-embed-large` |
| `src/functions/fn_index/summarizer.py` | `ChatCompletionsClient` (azure-ai-inference) | OpenAI SDK `/v1/chat/completions` → Ollama | `phi4-mini` |
| `src/functions/fn_convert_markitdown/describe_images.py` | `AzureOpenAI` (openai SDK) | `OpenAI` → Ollama | `moondream` |

#### Storage / Data (7 files → emulators in dev)

| File | Current SDK | Dev Replacement |
|------|------------|-----------------|
| `src/web-app/app/data_layer.py` | `CosmosClient` + `DefaultAzureCredential` | `CosmosClient` + emulator key |
| `src/web-app/app/image_service.py` | `BlobServiceClient` + `DefaultAzureCredential` | `BlobServiceClient` + Azurite connection string |
| `src/agent/agent/session_repository.py` | `CosmosClient` (async) + `DefaultAzureCredential` | `CosmosClient` + emulator key |
| `src/agent/agent/image_service.py` | `BlobServiceClient` + `DefaultAzureCredential` | `BlobServiceClient` + Azurite connection string |
| `src/agent/agent/search_tool.py` | `SearchClient` + `DefaultAzureCredential` | `SearchClient` + `AzureKeyCredential` (simulator API key) |
| `src/functions/shared/blob_storage.py` | `BlobServiceClient` + `DefaultAzureCredential` | `BlobServiceClient` + Azurite connection string |
| `src/functions/fn_index/indexer.py` | `SearchClient` + `SearchIndexClient` + `DefaultAzureCredential` | Same clients + `AzureKeyCredential` |

#### No Change Needed (2 files)

| File | Reason |
|------|--------|
| `src/web-app/app/main.py` | Uses `OpenAI(base_url=http://agent:8088)` — already env-agnostic |
| `src/agent/middleware/jwt_auth.py` | `REQUIRE_AUTH=false` bypasses JWT in dev |

### Additional Configuration and Wiring Files

| File | Required Change |
|------|-----------------|
| `src/web-app/app/config.py` | Add dev/prod config fields for emulator auth and resource names |
| `src/agent/main.py` | Pass configurable Cosmos session container to `CosmosAgentSessionRepository` |
| `src/functions/fn_convert_cu/function_app.py` | Stop hard-coding `staging` / `serving` |
| `src/functions/fn_convert_mistral/function_app.py` | Stop hard-coding `staging` / `serving` |
| `src/functions/fn_convert_markitdown/function_app.py` | Stop hard-coding `staging` / `serving` |
| `src/functions/fn_index/indexer.py` | Replace hard-coded vector dimensions with config |
| `src/agent/agent/search_tool.py` | Replace hard-coded vector dimensions with config |

### Scope Boundary

This epic makes local converter behavior explicit: `docker-compose.dev-services.yml` should always build and run MarkItDown for dev.

This epic keeps `CONVERTER` as an Azure-only selector. The existing `azure.yaml` and `infra/main.bicep` topology stays in place; Makefile and deployment workflow changes operate on the existing `func-convert-cu`, `func-convert-markitdown`, and `func-convert-mistral` services.

Conditional Azure provisioning and removal of non-selected converter services is **deferred** because it requires a broader AZD + Bicep refactor across service definitions, module wiring, and RBAC assignments.

---

## Stories

### Story 1 — Docker Compose for Dev Infrastructure

Create the Docker Compose file that starts all 5 infrastructure emulators. This is the foundation everything else builds on.

**Acceptance Criteria:**

- [ ] `docker-compose.dev-infra.yml` created at project root
- [ ] Cosmos DB emulator (`mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview`) on port 8081 (API) + 1234 (UI) with healthcheck
- [ ] Azurite (`mcr.microsoft.com/azure-storage/azurite:latest`) on ports 10000/10001/10002 with persistent volume
- [ ] AI Search Simulator (`ghcr.io/ellerbach/azure-ai-search-simulator:latest`) on ports 7250 (HTTPS) / 5250 (HTTP) with API keys `dev-admin-key` / `dev-query-key`
- [ ] Ollama (`ollama/ollama`) on port 11434 with GPU passthrough (`--gpus=all`) and persistent volume for models
- [ ] Aspire Dashboard (`mcr.microsoft.com/dotnet/aspire-dashboard:latest`) on ports 18888 (UI) / 18889 (OTLP gRPC)
- [ ] All services have healthchecks
- [ ] Named volumes for data persistence across restarts
- [ ] `docker compose -f docker-compose.dev-infra.yml up -d` starts all 5 containers successfully

**Implementation Scope:**

| File | Change |
|------|--------|
| `docker-compose.dev-infra.yml` | **NEW** — infrastructure emulator compose file |

---

### Story 2 — Emulator Initialization Script

Create a script that initializes all emulator resources after containers are healthy. Includes Cosmos DB databases/containers, Azurite blob containers, and Ollama model pulls.

**Acceptance Criteria:**

- [ ] `scripts/dev-init-emulators.sh` created
- [ ] Waits for Cosmos DB emulator to be healthy, then creates:
  - Dev: database `kb-agent` with containers `agent-sessions`, `conversations`, `messages`, `references`
  - Test: database `kb-agent-test` with containers `agent-sessions-test`, `conversations-test`, `messages-test`, `references-test`
- [ ] Waits for Azurite to be healthy, then creates blob containers: `staging`, `serving`, `staging-test`, `serving-test`
- [ ] Pulls Ollama models: `phi4-mini`, `mxbai-embed-large`, `moondream` (idempotent — skips if already present)
- [ ] Uses correct partition keys for each Cosmos container (matching `infra/modules/cosmos-db.bicep`)
- [ ] Script is idempotent — safe to run multiple times
- [ ] Script exits non-zero on failure with clear error message

**Implementation Scope:**

| File | Change |
|------|--------|
| `scripts/dev-init-emulators.sh` | **NEW** — emulator init script |

---

### Story 3 — Environment Config Modules + Client Factories

Add `ENVIRONMENT` env var support and factory functions to all config modules. This switches between `DefaultAzureCredential` (prod) and emulator keys/Ollama (dev).

**Acceptance Criteria:**

- [ ] `src/functions/shared/config.py` reads `ENVIRONMENT` env var (default: `prod`)
- [ ] `src/agent/agent/config.py` reads `ENVIRONMENT` env var (default: `prod`)
- [ ] `src/web-app/app/config.py` reads `ENVIRONMENT` env var (default: `prod`)
- [ ] Cosmos DB factory: emulator key in dev, `DefaultAzureCredential` in prod
- [ ] Blob Storage factory: Azurite connection string in dev, `DefaultAzureCredential` in prod
- [ ] AI Search factory: `AzureKeyCredential` + TLS skip in dev, `DefaultAzureCredential` in prod
- [ ] OpenAI/LLM factory: `OpenAI(base_url=ollama)` in dev, `AsyncAzureOpenAI` in prod
- [ ] Embedding factory: OpenAI SDK `/v1/embeddings` → Ollama in dev, `EmbeddingsClient` in prod
- [ ] Agent framework: `OpenAIChatClient` → Ollama in dev, `AzureOpenAIChatClient` in prod
- [ ] Config exposes `EMBEDDING_VECTOR_DIMENSIONS` and resource/container names instead of relying on hard-coded defaults
- [ ] All factories are unit tested (both dev and prod paths)
- [ ] `make dev-test` passes with zero regressions

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/functions/shared/config.py` | **UPDATE** — add `ENVIRONMENT`, dev-mode endpoint/key fields |
| `src/agent/agent/config.py` | **UPDATE** — add `ENVIRONMENT`, dev-mode endpoint/key fields |
| `src/web-app/app/config.py` | **UPDATE** — add `ENVIRONMENT`, dev-mode endpoint/key fields |
| `src/functions/shared/client_factories.py` | **NEW** — Cosmos, Blob, Search, OpenAI factory functions |
| `src/agent/agent/client_factories.py` | **NEW** — Cosmos, Blob, Search, OpenAI, ChatClient factory functions |
| `src/web-app/app/client_factories.py` | **NEW** — Cosmos and Blob factory functions for the web app |
| `src/functions/tests/test_shared/test_client_factories.py` | **NEW** — factory unit tests |
| `src/agent/tests/test_client_factories.py` | **NEW** — factory unit tests |
| `src/web-app/tests/test_client_factories.py` | **NEW** — factory unit tests |

---

### Story 4 — Update Storage/Data Call Sites (7 files)

Wire the factory functions into all 7 storage/data files that currently use `DefaultAzureCredential` directly.

**Acceptance Criteria:**

- [ ] `src/web-app/app/data_layer.py` — uses Cosmos factory (emulator key in dev)
- [ ] `src/web-app/app/image_service.py` — uses Blob factory (Azurite in dev)
- [ ] `src/agent/agent/session_repository.py` — uses Cosmos factory (emulator key in dev)
- [ ] `src/agent/agent/image_service.py` — uses Blob factory (Azurite in dev)
- [ ] `src/agent/agent/search_tool.py` — uses Search factory (simulator API key + TLS skip in dev)
- [ ] `src/functions/shared/blob_storage.py` — uses Blob factory (Azurite in dev)
- [ ] `src/functions/fn_index/indexer.py` — uses Search factory (simulator API key + TLS skip in dev)
- [ ] `src/agent/main.py` passes configurable session container name to `CosmosAgentSessionRepository`
- [ ] Converter entry points read configurable `STAGING_CONTAINER_NAME` / `SERVING_CONTAINER_NAME` instead of hard-coding them
- [ ] `src/functions/fn_index/indexer.py` and `src/agent/agent/search_tool.py` read vector dimensions from config instead of a hard-coded `1536`
- [ ] Prod behavior is identical to current behavior (no regressions)
- [ ] All existing unit tests still pass
- [ ] New/updated unit tests for dev-mode paths

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/web-app/app/data_layer.py` | **UPDATE** — use Cosmos factory |
| `src/web-app/app/image_service.py` | **UPDATE** — use Blob factory |
| `src/agent/agent/session_repository.py` | **UPDATE** — use Cosmos factory |
| `src/agent/agent/image_service.py` | **UPDATE** — use Blob factory |
| `src/agent/agent/search_tool.py` | **UPDATE** — use Search factory |
| `src/functions/shared/blob_storage.py` | **UPDATE** — use Blob factory |
| `src/functions/fn_index/indexer.py` | **UPDATE** — use Search factory |
| `src/agent/main.py` | **UPDATE** — pass configurable Cosmos session container name |
| `src/functions/fn_convert_cu/function_app.py` | **UPDATE** — read staging/serving container names from config |
| `src/functions/fn_convert_mistral/function_app.py` | **UPDATE** — read staging/serving container names from config |
| `src/functions/fn_convert_markitdown/function_app.py` | **UPDATE** — read staging/serving container names from config |

---

### Story 5 — Update LLM/Embedding/Vision Call Sites (4 files)

Wire the factory functions into all 4 LLM/embedding/vision files to use Ollama in dev.

**Acceptance Criteria:**

- [ ] `src/agent/agent/kb_agent.py` — uses `OpenAIChatClient` → Ollama `phi4-mini` in dev, `AzureOpenAIChatClient` in prod
- [ ] `src/functions/fn_index/embedder.py` — uses OpenAI SDK `/v1/embeddings` → Ollama `mxbai-embed-large` in dev
- [ ] `src/functions/fn_index/summarizer.py` — uses OpenAI SDK `/v1/chat/completions` → Ollama `phi4-mini` in dev
- [ ] `src/functions/fn_convert_markitdown/describe_images.py` — uses `OpenAI` → Ollama `moondream` in dev
- [ ] Dev embedding tests assert `1024` dimensions; prod-oriented tests/config continue to assert `1536`
- [ ] Prod behavior is identical to current behavior (no regressions)
- [ ] All existing unit tests still pass
- [ ] New/updated unit tests for dev-mode paths

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/agent/agent/kb_agent.py` | **UPDATE** — use ChatClient factory |
| `src/functions/fn_index/embedder.py` | **UPDATE** — use embedding factory |
| `src/functions/fn_index/summarizer.py` | **UPDATE** — use LLM factory |
| `src/functions/fn_convert_markitdown/describe_images.py` | **UPDATE** — use vision factory |

---

### Story 6 — Docker Compose for Application Services

Create the Docker Compose file for our 4 application services (fn-convert, fn-index, agent, web-app) that builds from local Dockerfiles.

**Acceptance Criteria:**

- [ ] `docker-compose.dev-services.yml` created at project root
- [ ] `fn-convert` builds from `fn_convert_markitdown/Dockerfile`, port 7071
- [ ] `fn-index` builds from `fn_index/Dockerfile`, port 7072
- [ ] `agent` builds from `src/agent/Dockerfile`, port 8088
- [ ] `web-app` builds from `src/web-app/Dockerfile`, port 8080
- [ ] All services use `.env.dev` for configuration
- [ ] Services declare `depends_on` with health conditions for their infra dependencies
- [ ] `docker compose -f docker-compose.dev-infra.yml -f docker-compose.dev-services.yml up -d` starts full stack

**Implementation Scope:**

| File | Change |
|------|--------|
| `docker-compose.dev-services.yml` | **NEW** — application service compose file |

---

### Story 7 — `.env.dev` Template

Create the template for dev environment variables with all emulator endpoints, Ollama config, and model mappings.

**Acceptance Criteria:**

- [ ] `.env.dev.template` created at project root with all required env vars
- [ ] Template includes Cosmos emulator endpoint + well-known key
- [ ] Template includes Azurite connection string
- [ ] Template includes Search Simulator endpoint + API keys
- [ ] Template includes Ollama endpoint + model names (phi4-mini, mxbai-embed-large, moondream)
- [ ] Template includes model deployment overrides (AGENT_MODEL_DEPLOYMENT_NAME, EMBEDDING_DEPLOYMENT_NAME, etc.)
- [ ] Template includes `EMBEDDING_VECTOR_DIMENSIONS` plus container/resource name overrides used by local factories and test isolation
- [ ] Template includes `REQUIRE_AUTH=false` and observability config
- [ ] `.env.dev.template` added to `.gitignore` exception (template tracked, actual `.env.dev` ignored)
- [ ] Documented in `docs/setup-and-makefile.md`

**Implementation Scope:**

| File | Change |
|------|--------|
| `.env.dev.template` | **NEW** — dev environment variable template |
| `.gitignore` | **UPDATE** — ignore `.env.dev`, track `.env.dev.template` |

---

### Story 8 — Makefile Rewrite

Replace the current Makefile with clean `dev-*` / `prod-*` target namespaces.

**Acceptance Criteria:**

- [ ] `dev-setup` — installs tools (Docker, uv) + Python deps, does NOT pull Docker images
- [ ] `dev-infra-up` — starts `docker-compose.dev-infra.yml` + runs `scripts/dev-init-emulators.sh`
- [ ] `dev-infra-down` — stops all dev infra containers
- [ ] `dev-services-up` — builds + starts all 4 app services
- [ ] `dev-services-down` — stops all dev app containers
- [ ] `dev-services-pipeline-up` — builds + starts fn-convert + fn-index only
- [ ] `dev-services-app-up` — builds + starts web-app only
- [ ] `dev-services-agents-up` — builds + starts agent only
- [ ] `dev-test` — runs unit + integration tests
- [ ] `dev-test-ui` — runs optional browser-based UI tests
- [ ] `dev-ui` — opens browser to `http://localhost:8080`
- [ ] `dev-pipeline` — runs full KB pipeline locally (convert + index)
- [ ] `dev-pipeline-convert` — runs local MarkItDown fn-convert only
- [ ] `dev-pipeline-index` — runs fn-index only
- [ ] `prod-infra-up` — provisions Azure prod RG via AZD
- [ ] `prod-infra-down` — deletes Azure prod RG (with confirmation)
- [ ] `prod-services-up` — deploys web-app, agent, fn-index, and the selected converter service for the current workflow to Azure Container Apps
- [ ] `prod-services-down` — scales down / stops services
- [ ] `prod-services-pipeline-up`, `prod-services-app-up`, `prod-services-agents-up` — sub-targets
- [ ] `prod-ui-url` — prints production web app URL
- [ ] `prod-pipeline`, `prod-pipeline-convert`, `prod-pipeline-index` — prod pipeline triggers
- [ ] `help` — shows all targets grouped by environment
- [ ] `set-project` — sets `PROJECT_NAME` in AZD env
- [ ] `set-converter` — sets `CONVERTER` in AZD env for prod targets
- [ ] Old targets removed (`azure-up`, `setup-azure`, `azure-kb`, `azure-test`, `test-ui`, etc.)
- [ ] `CONVERTER` drives which existing AZD converter service is deployed or triggered in prod; local dev always uses MarkItDown

**Implementation Scope:**

| File | Change |
|------|--------|
| `Makefile` | **REWRITE** — full replacement with dev/prod namespacing |

---

### Story 9 — Test Taxonomy and Local Integration Migration

Normalize test taxonomy around local emulators and update the existing Azure-bound integration suite to run fully locally.

**Acceptance Criteria:**

- [ ] `integration` marker descriptions updated to refer to local Docker infra rather than live Azure credentials
- [ ] `uitest` remains a separate optional marker in the web app and is excluded from default `dev-test`
- [ ] `e2e` terminology removed from test docs/file names where practical; service-backed tests use `integration`
- [ ] Shared `conftest.py` fixtures for `-test` resource names (Cosmos DB, Blob, Search)
- [ ] Integration tests use `-test` resources where supported by the resource type (e.g. `kb-agent-test`, `staging-test`, `kb-articles-test`); storage account names remain lowercase alphanumeric only
- [ ] Integration tests run against local Docker emulators and Ollama
- [ ] Existing Azure-bound tests are migrated explicitly, including web-app data/image integration tests and functions embedding/index integration tests
- [ ] `make dev-test` runs unit tests (always) + integration (when infra is up)
- [ ] `make dev-test-ui` runs browser tests separately
- [ ] All tests pass

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/agent/pyproject.toml` | **UPDATE** — integration marker description for local infra |
| `src/web-app/pyproject.toml` | **UPDATE** — integration/uitest marker descriptions and addopts |
| `src/functions/pyproject.toml` | **UPDATE** — integration marker description for local infra |
| `src/agent/tests/conftest.py` | **UPDATE** — add `-test` resource fixtures |
| `src/web-app/tests/conftest.py` | **UPDATE** — add `-test` resource fixtures |
| `src/functions/tests/conftest.py` | **UPDATE** — add `-test` resource fixtures |
| `src/web-app/tests/test_image_service_integration.py` | **UPDATE** — Azurite-backed integration |
| `src/web-app/tests/test_data_layer_integration.py` | **UPDATE** — Cosmos emulator-backed integration |
| `src/functions/tests/test_index/test_embedder.py` | **UPDATE** — local Ollama-backed integration with env-driven dimensions |
| Various test files | **UPDATE** — rename terminology, use `-test` fixtures |

---

### Story 10 — OpenTelemetry Instrumentation for Aspire Dashboard

Configure all services to export OpenTelemetry traces/logs/metrics to the Aspire Dashboard in dev and App Insights in prod.

**Acceptance Criteria:**

- [ ] All 4 services export OTLP traces to `OTEL_EXPORTER_OTLP_ENDPOINT`
- [ ] In dev: traces visible in Aspire Dashboard at `http://localhost:18888`
- [ ] In prod: traces flow to App Insights (existing behavior preserved)
- [ ] Structured logs appear in Aspire Dashboard
- [ ] Agent tool calls appear as spans in traces
- [ ] No code duplication — single OTEL setup function per service, endpoint from env var

**Implementation Scope:**

| File | Change |
|------|--------|
| `src/agent/agent/telemetry.py` | **NEW or UPDATE** — OTEL setup |
| `src/functions/shared/telemetry.py` | **NEW or UPDATE** — OTEL setup |
| `src/web-app/app/telemetry.py` | **NEW or UPDATE** — OTEL setup |

---

### Story 11 — End-to-End Local Validation

Validate the full local development workflow from `make dev-infra-up` through a user asking a question and getting an answer.

**Acceptance Criteria:**

- [ ] `make dev-setup` completes without errors
- [ ] `make dev-infra-up` starts all 5 infra containers and initializes emulators
- [ ] `make dev-services-up` builds and starts all 4 app services
- [ ] `make dev-pipeline-convert` converts sample KB articles (from `kb/staging/`)
- [ ] `make dev-pipeline-index` indexes converted articles into AI Search Simulator
- [ ] Agent responds to search queries using local Search Simulator results
- [ ] Vision/image analysis works via Ollama moondream
- [ ] Web app at `http://localhost:8080` can hold a multi-turn conversation
- [ ] `make dev-test` runs all unit + integration tests successfully
- [ ] `make dev-test-ui` runs optional browser tests successfully when requested
- [ ] `make dev-infra-down && make dev-infra-up` restores state (data persisted in volumes)

**Implementation Scope:**

No new files — this story validates the full integration of Stories 1–10.

---

### Story 12 — Documentation Update

Update all docs to reflect the new dev/prod workflow.

**Acceptance Criteria:**

- [ ] `docs/setup-and-makefile.md` — rewritten with new Makefile targets and dev workflow
- [ ] `docs/specs/environments-setup.md` — updated to reflect final implementation
- [ ] `docs/specs/infrastructure.md` — remove dev infra references, clarify prod-only
- [ ] `README.md` — quick-start section updated for Docker-first dev
- [ ] Epic doc updated with completion status

**Implementation Scope:**

| File | Change |
|------|--------|
| `docs/setup-and-makefile.md` | **REWRITE** — new dev/prod workflow |
| `docs/specs/environments-setup.md` | **UPDATE** — match final implementation |
| `docs/specs/infrastructure.md` | **UPDATE** — remove dev references |
| `README.md` | **UPDATE** — quick-start for Docker dev |

---

## Definition of Done

- [ ] All 12 stories completed with acceptance criteria checked off
- [ ] `make dev-infra-up && make dev-services-up` brings up a fully working local environment
- [ ] `make dev-test` passes all unit + integration tests
- [ ] `make dev-test-ui` is available for optional browser validation
- [ ] `make dev-pipeline` runs full convert + index pipeline locally
- [ ] Full local end-to-end conversation works (web-app → agent → search → response)
- [ ] Prod workflow (`prod-*` targets) still works with zero regressions on the retained 3-service converter topology
- [ ] No Azure dependency for any dev workflow
- [ ] All docs updated
- [ ] Epic status updated to `Done`
