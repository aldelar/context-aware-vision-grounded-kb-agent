# Epic 008 — Per-Function Container Split

> **Status:** Draft
> **Created:** March 9, 2026
> **Updated:** March 9, 2026

## Objective

Split the monolithic Azure Functions container into **four independent Container Apps**, each with its own Docker image, managed identity, RBAC roles, and deployment lifecycle. This eliminates the current antipattern where all four functions (three converters + indexer) share a single container image that ships every dependency — including Playwright/Chromium (~500 MB) which is only needed by `fn_convert_mistral`.

After this epic, each function:

- **Deploys independently** — upgrade one converter without touching the others
- **Ships only its own dependencies** — no Playwright in the indexer, no search SDK in the converters
- **Has its own managed identity** — least-privilege RBAC per function
- **Receives only its own env vars** — no info-leak of `MISTRAL_DEPLOYMENT_NAME` to `fn_index`
- **Scales independently** — convert functions can have different scale rules than the indexer

## Success Criteria

- [ ] Four Container Apps deployed: `func-cvt-cu-{project}-{env}`, `func-cvt-mis-{project}-{env}`, `func-cvt-mit-{project}-{env}`, `func-idx-{project}-{env}`
- [ ] Each Container App has its own system-assigned managed identity with least-privilege RBAC
- [ ] Each Container App runs its own Docker image with only the dependencies it needs
- [ ] `fn_convert_mistral` is the only image that includes Playwright/Chromium
- [ ] `azure.yaml` defines 4 function services; `azd deploy --service <name>` deploys one function independently
- [ ] All Makefile targets (`convert`, `azure-convert`, `index`, `azure-index`, `test-functions`) work correctly
- [ ] `make test-functions` passes with zero regressions (156+ tests)
- [ ] Architecture and infrastructure docs updated to reflect the new topology
- [ ] Old monolithic `function_app.py` and `Dockerfile` removed

---

## Background

### Current State (the problem)

The ingestion pipeline has four Azure Functions packaged as a **single Container App**:

| Function | Purpose | Unique Dependencies | Needs Playwright? |
|----------|---------|--------------------|--------------------|
| `fn_convert_cu` | HTML→MD via Content Understanding | `beautifulsoup4`, `azure-ai-contentunderstanding` | No |
| `fn_convert_mistral` | HTML→MD via Mistral Document AI | `playwright`, `httpx`, `openai` | **Yes** |
| `fn_convert_markitdown` | HTML→MD via MarkItDown | `markitdown`, `beautifulsoup4`, `openai` | No |
| `fn_index` | MD→AI Search chunks | `azure-search-documents`, `azure-ai-inference` | No |

**Problems:**

1. **Bloated images** — all functions ship Playwright/Chromium (~500 MB) even though only `fn_convert_mistral` uses it
2. **Blast radius** — a bug in one converter's dependencies can break all four functions
3. **Over-privileged identity** — one managed identity gets Contributor on staging + serving blob, full AI Services access, and AI Search write — every function has every permission
4. **Env var info-leak** — `fn_index` receives `MISTRAL_DEPLOYMENT_NAME`; converters receive `SEARCH_ENDPOINT`
5. **Coupled deployments** — upgrading `markitdown` forces a rebuild and redeploy of all functions
6. **Config crash** — `shared/config.py` calls `sys.exit(1)` at import time if required env vars are missing; in a split world, containers that don't need all vars would crash on startup

### Proposed State

Four independent Container Apps sharing the same Container Apps Environment, ACR, and Functions runtime storage account. Each has its own:

- Docker image (only its deps)
- System-assigned managed identity
- RBAC role assignments (least privilege)
- Environment variables (only what it needs)
- `function_app.py` entry point (single trigger)
- `azure.yaml` service entry (independent deployment)

### Naming Convention

Azure limits: Container App = 32 chars, Storage Account = 24 chars.
With max inputs (`PROJECT_NAME`=8, `AZURE_ENV_NAME`=7):

| Function | Container App Name | Max Length |
|----------|-------------------|-----------|
| fn_convert_cu | `func-cvt-cu-{project}-{env}` | 27 |
| fn_convert_mistral | `func-cvt-mis-{project}-{env}` | 28 |
| fn_convert_markitdown | `func-cvt-mit-{project}-{env}` | 28 |
| fn_index | `func-idx-{project}-{env}` | 24 |

All fit within the 32-character limit. The existing Functions runtime storage account (`st{project}func{env}`) is shared across all four Container Apps — no additional storage accounts needed.

### RBAC Per Function (Least Privilege)

| Function | Staging Blob | Serving Blob | AI Services | AI Search |
|----------|:---:|:---:|:---:|:---:|
| fn_convert_cu | Contributor | Contributor | Cognitive Services User + OpenAI User | — |
| fn_convert_mistral | Contributor | Contributor | Cognitive Services User + OpenAI User | — |
| fn_convert_markitdown | Contributor | Contributor | OpenAI User only | — |
| fn_index | — | Reader | OpenAI User only | Index Data Contributor + Service Contributor |

### Per-Function Environment Variables

| Env Var | cvt-cu | cvt-mis | cvt-mit | idx |
|---------|:---:|:---:|:---:|:---:|
| `AI_SERVICES_ENDPOINT` | ✓ | ✓ | ✓ | ✓ |
| `STAGING_BLOB_ENDPOINT` | ✓ | ✓ | ✓ | — |
| `SERVING_BLOB_ENDPOINT` | ✓ | ✓ | ✓ | ✓ |
| `MISTRAL_DEPLOYMENT_NAME` | — | ✓ | — | — |
| `EMBEDDING_DEPLOYMENT_NAME` | — | — | — | ✓ |
| `SEARCH_ENDPOINT` | — | — | — | ✓ |
| `SEARCH_INDEX_NAME` | — | — | — | ✓ |
| `AzureWebJobsStorage__accountName` | ✓ | ✓ | ✓ | ✓ |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | ✓ | ✓ | ✓ | ✓ |

---

## Stories

---

### Story 1 — Package Restructure: `shared/` as Proper Package + Config Fix

> **Status:** Not started
> **Depends on:** None

Restructure `shared/` into a proper installable Python package and fix the eager config validation that blocks per-function deployment. Move `cu_client.py` into `fn_convert_cu` (its only consumer). Remove dead config.

#### Deliverables

- [ ] Create `src/functions/shared/pyproject.toml` — make `shared` a proper pip-installable package (`kb-ingestion-shared`) with its own dependencies (`azure-identity`, `azure-storage-blob`, `python-dotenv`)
- [ ] Add `shared` as a uv workspace member in root `src/functions/pyproject.toml`
- [ ] Move `shared/cu_client.py` into `fn_convert_cu/cu_client.py` and update imports — this module is only used by `fn_convert_cu` and drags `azure-ai-contentunderstanding` into `shared`
- [ ] Refactor `shared/config.py` to use per-function config classes or lazy loading:
  - Remove `sys.exit(1)` on missing env vars at import time
  - Each function validates only the env vars it needs
  - Remove dead `agent_deployment_name` field (unused by any function)
- [ ] Each `fn_*/pyproject.toml` declares `kb-ingestion-shared` as a workspace dependency via `[tool.uv.sources]`
- [ ] `make test-functions` passes with zero regressions

#### Definition of Done

- [ ] `shared/` has its own `pyproject.toml` and is a uv workspace member
- [ ] `cu_client.py` lives in `fn_convert_cu/` — no CU dependency in `shared`
- [ ] Importing `shared.config` does NOT crash if `SEARCH_ENDPOINT` is missing (only validate what's needed)
- [ ] `agent_deployment_name` removed from config
- [ ] All tests pass (156+)

---

### Story 2 — Per-Function `function_app.py` Entry Points

> **Status:** Not started
> **Depends on:** Story 1

Create a per-function `function_app.py` for each of the four functions. The monolithic `function_app.py` at the workspace root can remain temporarily (it still works), but each function directory gets its own entry point for when the split happens in Story 5.

#### Deliverables

- [ ] Create `src/functions/fn_convert_cu/function_app.py` — single `FunctionApp` instance with one HTTP trigger at `/api/convert`
- [ ] Create `src/functions/fn_convert_mistral/function_app.py` — single trigger at `/api/convert-mistral`
- [ ] Create `src/functions/fn_convert_markitdown/function_app.py` — single trigger at `/api/convert-markitdown`
- [ ] Create `src/functions/fn_index/function_app.py` — single trigger at `/api/index`
- [ ] Extract `_get_article_ids()` helper to `shared/blob_storage.py` (used by all 4 handlers, currently duplicated in monolith)
- [ ] Each per-function `function_app.py` imports only its own `fn_*` package + `shared.blob_storage` + `shared.config`
- [ ] Verify the monolithic `function_app.py` still works (no functional change yet)

#### Definition of Done

- [ ] Each function directory has a `function_app.py` that can serve as an independent Azure Functions entry point
- [ ] `_get_article_ids()` lives in `shared/blob_storage.py`
- [ ] The existing monolithic container still works (regression check)
- [ ] All tests pass

---

### Story 3 — Refactor `function-app.bicep` Into Reusable Module

> **Status:** Not started
> **Depends on:** None (can run in parallel with Stories 1–2)

Refactor `infra/modules/function-app.bicep` to be a reusable, parameterized module that can be called once per function. Extract the Functions runtime storage account creation out of the module (it should be created once and shared).

#### Deliverables

- [ ] Extract the Functions runtime storage account resource from `function-app.bicep` into `main.bicep` (created once, shared by all 4 Container Apps)
- [ ] Add parameters to `function-app.bicep`:
  - `functionName` (string) — used in Container App name: `func-${functionName}-${baseName}`
  - `azdServiceName` (string) — the `azd-service-name` tag value for `azure.yaml` mapping
  - `envVars` (array) — per-function environment variable array
  - `functionsStorageAccountName` (string) — reference to the shared storage account
- [ ] Remove hardcoded env vars from the module — caller passes the per-function set
- [ ] Ensure the module still creates: Container App, AcrPull role assignment, Functions storage Blob Data Owner role
- [ ] Validate: deploy with the refactored module (single function app, same as today) to confirm no regression

#### Definition of Done

- [ ] `function-app.bicep` accepts `functionName`, `azdServiceName`, and `envVars` params
- [ ] Functions runtime storage is created once in `main.bicep`, not inside the module
- [ ] Deploying the refactored module with current parameters produces the same single Container App as before (regression check)
- [ ] `azd provision` succeeds with the refactored Bicep

---

### Story 4 — Wire 4 Function Modules + Per-Function RBAC in `main.bicep`

> **Status:** Not started
> **Depends on:** Story 3

Update `main.bicep` to call `function-app.bicep` four times (once per function), each with its own env vars, `azd-service-name` tag, and managed identity. Wire per-function RBAC role assignments using the existing role modules.

#### Deliverables

- [ ] Define 4 function app modules in `main.bicep`:
  - `funcConvertCu` — name `cvt-cu`, service name `func-convert-cu`, env vars per table above
  - `funcConvertMistral` — name `cvt-mis`, service name `func-convert-mistral`
  - `funcConvertMarkitdown` — name `cvt-mit`, service name `func-convert-markitdown`
  - `funcIndex` — name `idx`, service name `func-index`
- [ ] Wire per-function RBAC role assignments (call role modules once per function identity):
  - Staging storage: Contributor for 3 convert functions (not fn_index)
  - Serving storage: Contributor for 3 convert functions, Reader for fn_index
  - AI Services: full Cognitive Services User + OpenAI User for CU and Mistral; OpenAI User only for MarkItDown and Index
  - AI Search: Index Data Contributor + Service Contributor for fn_index only
- [ ] Remove the old single `functionApp` module call and its RBAC assignments
- [ ] Update main.bicep outputs: 4 function URLs instead of 1
- [ ] `azd provision` succeeds and creates 4 Container Apps with correct RBAC

#### Definition of Done

- [ ] 4 Container Apps visible in Azure with correct names
- [ ] Each has its own system-assigned managed identity
- [ ] RBAC assignments verified: each identity has only the roles listed in the RBAC table
- [ ] No unused env vars leaked to any Container App
- [ ] `azd provision` clean (no errors, no dangling old resources)

---

### Story 5 — Per-Function Dockerfiles + azure.yaml + Deploy

> **Status:** Not started
> **Depends on:** Stories 1, 2, 3, 4

Create per-function Dockerfiles, update `azure.yaml` with 4 service entries, build and deploy all 4 Container Apps. Decommission the monolithic Dockerfile and `function_app.py`.

#### Deliverables

- [ ] Create per-function Dockerfiles:
  - `src/functions/fn_convert_cu/Dockerfile` — base image + `shared/` + `fn_convert_cu/`
  - `src/functions/fn_convert_mistral/Dockerfile` — same + Playwright/Chromium layer
  - `src/functions/fn_convert_markitdown/Dockerfile` — base image + `shared/` + `fn_convert_markitdown/`
  - `src/functions/fn_index/Dockerfile` — base image + `shared/` + `fn_index/`
- [ ] Update `azure.yaml`: replace single `functions` service with 4 services (`func-convert-cu`, `func-convert-mistral`, `func-convert-markitdown`, `func-index`), each pointing to its own Dockerfile and project path
- [ ] Update Makefile:
  - `azure-convert` routes to correct function URLs per analyzer
  - `azure-index` routes to `func-index` URL
  - Add per-service deploy targets if warranted
- [ ] Deploy and validate:
  - `azd deploy` builds 4 images and deploys to 4 Container Apps
  - `make azure-convert analyzer=content-understanding` hits `func-cvt-cu`
  - `make azure-convert analyzer=mistral-doc-ai` hits `func-cvt-mis`
  - `make azure-convert analyzer=markitdown` hits `func-cvt-mit`
  - `make azure-index` hits `func-idx`
- [ ] Remove monolithic `src/functions/Dockerfile`
- [ ] Remove monolithic `src/functions/function_app.py`

#### Definition of Done

- [ ] 4 independent Docker images in ACR
- [ ] `fn_convert_mistral` image includes Playwright/Chromium; other 3 do not
- [ ] `azd deploy --service func-convert-cu` (and each other service) deploys independently
- [ ] All `make azure-*` targets work correctly against the 4 Container Apps
- [ ] Old monolithic Dockerfile and function_app.py deleted
- [ ] `make test-functions` still passes

---

### Story 6 — Documentation & Cleanup

> **Status:** Not started
> **Depends on:** Story 5

Update architecture docs, infrastructure docs, and README to reflect the per-function topology. Clean up any remaining artifacts from the monolithic setup.

#### Deliverables

- [ ] Update `docs/specs/architecture.md`:
  - Reflect 4 independent Container Apps (not one monolith)
  - Update the pipeline flow diagram if it references a single function app
- [ ] Update `docs/specs/infrastructure.md`:
  - Resource inventory: 4 function Container Apps with individual names and RBAC
  - Module structure: `function-app.bicep` is now called 4 times
  - RBAC table shows per-function role assignments
- [ ] Update `README.md`:
  - `azd deploy` section reflects 4 services
  - Per-service deploy commands documented
- [ ] Create `docs/ards/ARD-007-per-function-containers.md`:
  - Document the decision to split into per-function containers
  - Context: monolithic antipattern, blast radius, over-privileged identity, bloated images
  - Trade-offs: more Container Apps, more RBAC complexity, but better isolation and least privilege
- [ ] Clean up `src/functions/.dockerignore` — remove now-irrelevant entries
- [ ] Verify `make help` is accurate

#### Definition of Done

- [ ] All docs accurately describe the 4-Container-App topology
- [ ] ARD documents the decision and trade-offs
- [ ] `make help` output matches actual targets
- [ ] No stale references to the old single `func-{project}-{env}` Container App
