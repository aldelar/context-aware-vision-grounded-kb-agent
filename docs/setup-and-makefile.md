# Setup & Makefile Guide

## Prerequisites

- **Python 3.11+** and **[uv](https://docs.astral.sh/uv/)** package manager
- **Azure CLI** (`az`) — authenticated via `az login`
- **Azure Developer CLI** (`azd`) — for provisioning infrastructure
- **Azure Functions Core Tools** (`func`) — for Azure deployment
- An Azure subscription with access to AI Services, AI Search, and model deployments

## Resource Naming

All Azure resources are named using a **project name** (`PROJECT_NAME`) and an **environment name** (`AZURE_ENV_NAME`):

```
{resource-prefix}-{projectName}-{env}
```

For example, with `PROJECT_NAME=myproj` and `AZURE_ENV_NAME=dev`:

| Resource | Name |
|---|---|
| Resource Group | `rg-myproj-dev` |
| AI Services | `ai-myproj-dev` |
| AI Search | `srch-myproj-dev` |
| Cosmos DB | `cosmos-myproj-dev` |
| Storage (staging) | `stmyprojstagingdev` |

`PROJECT_NAME` must be set before provisioning. Constraints:

- **`PROJECT_NAME`**: 2–8 characters (alphanumeric + hyphens). Kept short to fit the 24-char Azure Storage Account limit.
- **`AZURE_ENV_NAME`**: 2–7 characters. Use `dev`, `staging`, or `prod` (not `production`).

Set the project name:

```bash
make set-project name=myproj
```

---

## 1. Local Environment Setup

```bash
# 1. Check that all required tools are installed
make dev-doctor

# 2. Install any missing tools and Python dependencies
make dev-setup

# 3. Provision Azure infrastructure (required even for local runs — CU & Search are cloud services)
make azure-provision

# 4. Populate the local .env file from AZD environment values
make dev-setup-env

# 5. Deploy the CU analyzer and search index definition
make azure-deploy

# 6. Validate that Azure infrastructure is reachable and properly configured
make validate-infra
```

---

## 2. Run Pipeline — Local

In local mode, the pipeline reads source articles from `kb/staging/` on disk, calls Azure AI services for processing, and writes output to `kb/serving/`. The search index is populated in Azure AI Search.

```bash
# Stage 1: Convert HTML articles to Markdown with AI-generated image descriptions
# Choose a conversion backend:
make convert analyzer=content-understanding   # uses Azure Content Understanding
make convert analyzer=mistral-doc-ai          # uses Mistral Document AI + GPT-4.1 vision
make convert analyzer=markitdown              # uses MarkItDown (local) + GPT-4.1 vision

# Stage 2: Chunk Markdown, generate embeddings, and index into Azure AI Search
make index

# Verify: run the test suite
make test

# Optional: inspect the search index contents
make azure-index-summarize
```

**Flow:** `kb/staging/` (HTML + images) → `make convert` → `kb/serving/` (Markdown + images) → `make index` → Azure AI Search index

---

## 3. Run Pipeline — Azure

In Azure mode, articles are uploaded to blob storage and the pipeline runs as deployed Azure Functions. Azure infrastructure and function code must be deployed first (see [Local Environment Setup](#1-local-environment-setup)).

```bash
# 1. Upload local source articles to Azure staging blob storage
make azure-upload-staging

# 2. Trigger fn-convert in Azure (staging blob → serving blob)
# Choose a conversion backend:
make azure-convert analyzer=content-understanding
make azure-convert analyzer=mistral-doc-ai
make azure-convert analyzer=markitdown

# 3. Trigger fn-index in Azure (serving blob → AI Search index)
make azure-index

# 4. Inspect the search index contents
make azure-index-summarize
```

**Flow:** `make azure-upload-staging` → `make azure-convert` → `make azure-index` → Azure AI Search index

### Cleanup

```bash
make azure-clean          # Clean all Azure data (storage + index + analyzer)
# Or selectively:
make azure-clean-storage  # Empty staging and serving blob containers
make azure-clean-index    # Delete the AI Search index
```

---

## 4. Run Agent + Web App — Local

The agent is a standalone Starlette ASGI service (port 8088) built with `from_agent_framework` that exposes an OpenAI-compatible Responses API. The Chainlit web app is a thin client that calls the agent via APIM, handles streaming, renders citations/images, and reads conversation sessions from Cosmos DB.

### Prerequisites

- The ingestion pipeline has been run at least once (articles indexed in AI Search)
- Azure infrastructure provisioned (`make azure-provision`)

### Setup & Run

```bash
# 1. Populate .env files from AZD environment (functions + web app + agent)
make dev-setup-env

# 2. Start the agent (in one terminal)
make agent

# 3. Start the web app (in another terminal)
make app
```

Open `http://localhost:8080` — ask questions like "What is Azure Content Understanding?" or "How does search security work?" and get grounded answers with inline images and source citations.

The web app auto-detects the agent URL scheme: `http://` → no auth (local), `https://` → Entra token auth (deployed).

> **Note:** `make dev-setup` installs dependencies for all projects (functions + web app + agent). No separate setup step is needed.

### Run Tests

```bash
make agent-test   # Agent tests
make app-test     # Web app tests
```

---

## 5. Deploy to Azure

The KB Agent is deployed as an **Azure Container App** (with Foundry integration for tracing and registration), and the Chainlit web app to a separate Container App with Entra ID authentication (Easy Auth). An **APIM AI Gateway** proxies all agent traffic.

### Prerequisites

- Azure infrastructure is provisioned (`make azure-provision` — this also creates the Foundry project, APIM gateway, Cosmos DB, and Entra App Registration)
- The ingestion pipeline has been run at least once (articles indexed in AI Search)

### Deploy Agent + Web App

```bash
# Full deploy: provision + deploy all services + register agent + configure endpoints + auth
make azure-up

# Or deploy individual components:
make azure-deploy       # Deploy all services (azd deploy)
make azure-deploy-app   # Deploy web app only
make azure-agent        # Deploy agent Container App only

# Post-deploy registration (included in azure-up):
make azure-register-agent   # Register agent in Foundry via APIM gateway
make azure-configure-app    # Set web app agent endpoint to APIM proxy URL

# Get the deployed URL
make azure-app-url

# Stream live logs (optional)
make azure-app-logs
make azure-agent-logs
```

The deployed web app is protected by Entra ID — users must sign in with their organizational account. The agent runs as a Container App with a system-assigned managed identity that has least-privilege RBAC access to AI Services, AI Search, Serving Storage, and Cosmos DB. The agent owns conversation history — it persists and loads session state via Cosmos DB using the Agent Framework's session persistence model.

Docker images are built and pushed to Azure Container Registry automatically during `azd deploy` — no local Docker build step is needed.

---

## Makefile Reference

Run `make help` to see all targets. Full list:

| Target | Description |
|---|---|
| **Local** | |
| `make setup` | Install tools + Python dependencies |
| `make setup-azure` | Provision Azure + configure local env |
| `make kb` | Run full local KB pipeline (convert + index + upload serving) |
| `make test` | Run all fast tests (unit + endpoint, no Azure needed) |
| `make agent` | Run KB Agent locally (http://localhost:8088) |
| `make app` | Run web app locally (http://localhost:8080) |
| **Azure** | |
| `make set-project` | Set PROJECT_NAME in AZD env (name=\<your-name\>, 2-8 chars) |
| `make azure-up` | Full Azure deploy (provision + deploy + register + configure + auth) |
| `make azure-kb` | Full Azure KB pipeline (upload + convert + index) |
| `make azure-test` | Run all Azure integration tests |
| `make azure-app-url` | Print the deployed web app URL |
| **Utilities — Local** | |
| `make dev-doctor` | Check if required dev tools are installed |
| `make dev-setup` | Install required dev tools and Python dependencies |
| `make dev-setup-env` | Populate .env files from AZD environment |
| `make validate-infra` | Validate Azure infra is ready for local dev |
| `make dev-enable-storage` | Re-enable public access on storage accounts (disabled nightly) |
| `make dev-enable-cosmos` | Enable public access on Cosmos DB + add developer IP to firewall |
| `make grant-dev-roles` | Grant Cosmos DB native RBAC to current developer |
| `make clean-kb` | Clean local serving output + delete search index |
| `make convert` | Run fn-convert locally (analyzer=\<analyzer\>) |
| `make index` | Run fn-index locally (kb/serving → Azure AI Search) |
| `make upload-serving` | Upload kb/serving/ images to Azure serving blob |
| `make test-agent` | Run agent unit + endpoint tests |
| `make test-app` | Run web app unit tests |
| `make test-functions` | Run functions unit tests |
| `make test-agent-integration` | Run agent integration tests (needs running local agent) |
| `make test-ui` | Interactive UI testing with Playwright CLI (needs running agent + app) |
| `make test-ui-auto` | Run automated Playwright UI tests (needs running agent + app) |
| **Utilities — Azure** | |
| `make azure-provision` | Provision all Azure resources (azd provision) |
| `make azure-provision-clean` | Provision from scratch, ignoring prior state |
| `make azure-deploy` | Deploy all services + CU analyzer |
| `make azure-deploy-app` | Deploy web app only |
| `make azure-register-agent` | Register agent in Foundry portal (idempotent) |
| `make azure-configure-app` | Configure web app agent endpoint (post-registration) |
| `make azure-setup-auth` | Configure Entra redirect URIs (idempotent) |
| `make azure-upload-staging` | Upload kb/staging → Azure staging blob |
| `make azure-convert` | Trigger fn-convert in Azure (analyzer=\<analyzer\>) |
| `make azure-index` | Trigger fn-index in Azure (serving → AI Search) |
| `make azure-index-summarize` | Show AI Search index contents summary |
| `make azure-test-agent` | Agent integration tests (external HTTPS + JWT auth) |
| `make azure-test-app` | Web app integration tests (Cosmos + Blob + Agent) |
| `make azure-app-logs` | Stream live logs from deployed web app |
| `make azure-agent-logs` | Stream agent logs from Container Apps |
| `make azure-clean-orphan-roles` | Delete orphaned role assignments |
| `make azure-clean-storage` | Empty staging + serving blob containers |
| `make azure-clean-index` | Delete the AI Search index |
| `make azure-clean` | Clean all Azure data (storage + index + analyzer) |
| `make azure-down` | DELETE entire Azure resource group + purge all soft-deletes (irreversible!) |

### Interactive UI Testing

The `make test-ui` target opens [Playwright CLI](https://github.com/anthropics/playwright-cli) for interactive browser-based testing of the web app.

**Prerequisites:** Node.js and Playwright CLI (`npm install -g @anthropic-ai/playwright-cli`)

**Workflow:**
1. Start the agent: `make agent` (terminal 1)
2. Start the web app: `make app` (terminal 2)
3. Run: `make test-ui` (terminal 3)

Playwright CLI opens a Chromium browser at http://localhost:8080 and provides a REPL for commands like `snapshot` (page accessibility tree), `click <element>`, `type <element> <text>`, and `screenshot`.

---

## Sample Articles

The `kb/staging/` folder contains sample articles (HTML + images) used for development and testing. After running the pipeline, processed output appears in `kb/serving/` and chunks are searchable in the `kb-articles` AI Search index.
