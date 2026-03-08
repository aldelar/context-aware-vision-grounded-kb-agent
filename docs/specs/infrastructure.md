# Infrastructure

> **Status:** Updated — June 26, 2026

## Overview

All infrastructure is defined as **Bicep IaC** under `/infra/` and deployed via **Azure Developer CLI (AZD)**. The design follows zero-trust principles: all inter-service authentication is via **managed identity** with RBAC — no keys, secrets, or connection strings are stored in application settings.

**Region:** East US 2 — selected for availability of all required services: Content Understanding, text-embedding-3-small, gpt-5-mini, Azure AI Search, and Azure Functions Flex Consumption.

**Resource naming** is parameterized via two values set during `azd provision`:

- **`PROJECT_NAME`** (2–8 chars) — short project identifier, default `{project}`
- **`AZURE_ENV_NAME`** (2–7 chars) — environment name (`dev`, `staging`, `prod`)

All resources follow the pattern `{prefix}-{projectName}-{env}` (e.g., `func-{project}-dev`). Storage accounts drop hyphens to meet Azure's alphanumeric constraint (e.g., `st{project}staging dev`). The 8-char project name limit ensures storage accounts stay within the 24-character Azure maximum.

## Resource Inventory

| Resource | Bicep Module | Name Pattern | SKU / Tier |
|----------|-------------|--------------|------------|
| Resource Group | _(AZD-managed)_ | `rg-{project}-{env}` | — |
| Log Analytics Workspace | `monitoring.bicep` | `log-{project}-{env}` | PerGB2018, 30-day retention |
| Application Insights | `monitoring.bicep` | `appi-{project}-{env}` | Workspace-based |
| Storage — Staging | `storage.bicep` | `st{project}staging{env}` | Standard_LRS, Hot |
| Storage — Serving | `storage.bicep` | `st{project}serving{env}` | Standard_LRS, Hot |
| Storage — Functions Runtime | `function-app.bicep` | `st{project}func{env}` | Standard_LRS |
| Azure AI Services (Foundry) | `ai-services.bicep` | `ai-{project}-{env}` | S0 (AIServices kind) |
| → Embedding Deployment | `ai-services.bicep` | `text-embedding-3-small` | GlobalStandard, 120K TPM |
| → Agent Deployment | `ai-services.bicep` | `gpt-5-mini` | GlobalStandard, 30K TPM |
| → CU Completion Deployment | `ai-services.bicep` | `gpt-4.1` | GlobalStandard, 30K TPM |
| → CU Internal: Embedding † | `ai-services.bicep` | `text-embedding-3-large` | GlobalStandard, 120K TPM |
| → CU Internal: Analysis † | `ai-services.bicep` | `gpt-4.1-mini` | GlobalStandard, 30K TPM |
| → Mistral OCR Deployment | `ai-services.bicep` | `mistral-document-ai-2512` | GlobalStandard, capacity 1 |
| Azure AI Search | `search.bicep` | `srch-{project}-{env}` | Free, 1 partition, 1 replica |
| Function App (Container App) | `function-app.bicep` | `func-{project}-{env}` | Container App, 1.0 vCPU / 2 GiB, Python 3.11 custom Docker |
| Container Registry | `container-registry.bicep` | `cr{project}{env}` | Basic |
| Container Apps Environment | `container-app.bicep` | `cae-{project}-{env}` | Consumption |
| Container App (Web App) | `container-app.bicep` | `webapp-{project}-{env}` | 0.5 vCPU, 1 GiB |
| Foundry Project | `foundry-project.bicep` | `proj-{project}-{env}` | — (child of AI Services) |
| Cosmos DB (NoSQL) | `cosmos-db.bicep` | `cosmos-{project}-{env}` | Serverless |
| → Database | `cosmos-db.bicep` | `kb-agent` | — |
| → Container | `cosmos-db.bicep` | `conversations` | Partition key `/userId` |
| Entra App Registration | Pre-provision hook | `webapp-{project}-{env}` | — |

> `{project}` is the `PROJECT_NAME` (default `{project}`). `{env}` is the `AZURE_ENV_NAME` (e.g., `dev`, `staging`, `prod`).

## Module Structure

```
infra/
├── main.bicep                  # Orchestration — wires all modules + role assignments
├── main.parameters.json        # AZD parameter file (env name, location, search SKU)
└── modules/
    ├── monitoring.bicep         # Log Analytics + Application Insights
    ├── storage.bicep            # Reusable storage account with containers + RBAC
    ├── ai-services.bicep        # AI Services account + model deployments + RBAC
    ├── search.bicep             # AI Search service + RBAC
    ├── foundry-project.bicep    # Foundry project (child of AI Services) for hosted agent
    ├── cosmos-db.bicep           # Cosmos DB NoSQL (serverless) — database + conversations container
    ├── cosmos-db-role.bicep      # Cosmos DB Built-in Data Contributor role assignment
    ├── function-app.bicep       # Functions on Container Apps (custom Docker) + runtime storage + AcrPull RBAC
    ├── container-registry.bicep # Azure Container Registry (Basic) + AcrPull RBAC (web app + Foundry project)
    └── container-app.bicep      # Container Apps Environment + Container App + Easy Auth
```

---

## Service Details

### Monitoring (`monitoring.bicep`)

Provides centralized logging and telemetry for all services.

| Resource | Configuration |
|----------|--------------|
| **Log Analytics Workspace** | SKU `PerGB2018`, 30-day retention |
| **Application Insights** | Workspace-based (linked to Log Analytics), type `web` |

The Application Insights connection string is passed to the Function App as an app setting for automatic telemetry collection.

### Storage (`storage.bicep`)

A reusable module deployed three times — once each for staging, serving, and functions runtime.

| Setting | Value |
|---------|-------|
| Kind | StorageV2 |
| SKU | Standard_LRS |
| Access Tier | Hot |
| Public Blob Access | Disabled |
| Shared Key Access | Disabled (managed identity only) |
| Minimum TLS | 1.2 |
| HTTPS Only | Yes |

**Containers created:**

| Account | Container | Purpose |
|---------|-----------|---------|
| Staging | `staging` | Source HTML articles + images uploaded for processing |
| Serving | `serving` | Processed Markdown articles + PNG images consumed by fn-index and agents |
| Functions | `deployments` | Function App deployment packages (auto-managed) |

The module accepts an optional `contributorPrincipalId` parameter. When provided, it grants the **Storage Blob Data Contributor** role to that principal (used to give the Function App access to staging and serving accounts).

### Azure AI Services (`ai-services.bicep`)

A single **AIServices** (Foundry) resource hosting Content Understanding and six model deployments.

| Setting | Value |
|---------|-------|
| Kind | `AIServices` |
| SKU | S0 |
| Custom Subdomain | `ai-{project}-{env}` |
| Local Auth | Disabled (`disableLocalAuth: true`) |
| Public Network | Enabled |

**Model Deployments:**

| Deployment | Model | SKU | Capacity | Purpose |
|-----------|-------|-----|----------|---------|
| `text-embedding-3-small` | OpenAI `text-embedding-3-small` v1 | GlobalStandard | 120K TPM | Vector embeddings for fn-index (1536 dimensions) |
| `text-embedding-3-large` | OpenAI `text-embedding-3-large` v1 | GlobalStandard | 120K TPM | CU-internal † — required by `prebuilt-documentSearch` for field extraction |
| `gpt-5-mini` | OpenAI `gpt-5-mini` v2025-08-07 | GlobalStandard | 30K TPM | Future agent chat/reasoning |
| `gpt-4.1` | OpenAI `gpt-4.1` v2025-04-14 | GlobalStandard | 30K TPM | CU custom analyzer completion + Mistral pipeline image descriptions (GPT-4.1 vision) |
| `gpt-4.1-mini` | OpenAI `gpt-4.1-mini` v2025-04-14 | GlobalStandard | 30K TPM | CU-internal † — required by `prebuilt-documentSearch` for document analysis |
| `mistral-document-ai-2512` | Mistral AI `mistral-document-ai-2512` | GlobalStandard | 1 | Mistral Document AI OCR for `fn_convert_mistral` pipeline |

> **†** `text-embedding-3-large` and `gpt-4.1-mini` are **not called by application code** — they are internal dependencies of CU's `prebuilt-documentSearch`. Without either deployed, CU silently returns 0 contents. These models are only needed when using the Content Understanding backend (`fn_convert_cu`).

Model deployments are serialized (`dependsOn`) to avoid Azure API conflicts.

**RBAC Roles (granted to Function App):**

| Role | Role ID | Purpose |
|------|---------|---------|
| Cognitive Services OpenAI User | `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` | Call embedding and agent model endpoints |
| Cognitive Services User | `a97b65f3-24c7-4388-baec-2e87135dc908` | Access Content Understanding APIs |

### Azure AI Search (`search.bicep`)

| Setting | Value |
|---------|-------|
| SKU | Free |
| Partitions | 1 |
| Replicas | 1 |
| Semantic Search | Free tier |
| Auth | AAD or API Key (`aadOrApiKey`) with `http401WithBearerChallenge` |
| Public Network | Enabled |

The search index (`kb-articles`) is created by application code at runtime, not in Bicep. See the [Architecture spec](architecture.md) for the full index schema.

**RBAC Roles (granted to Function App):**

| Role | Role ID | Purpose |
|------|---------|---------|
| Search Index Data Contributor | `8ebe5a00-799e-43f5-93ac-243d3dce84a7` | Push documents to the search index |
| Search Service Contributor | `7ca78c08-252a-4471-8644-bb5ff32d4ba0` | Create and manage indexes |

### Function App (`function-app.bicep`)

| Setting | Value |
|---------|-------|
| Plan | Flex Consumption (FC1) |
| Runtime | Python 3.11 |
| OS | Linux |
| Max Instance Count | 40 |
| Instance Memory | 2048 MB |
| Identity | System-assigned managed identity |
| Deployment Storage | Blob container (`deployments`) on dedicated functions storage account, authenticated via system identity |

**Application Settings:**

| Setting | Source | Purpose |
|---------|--------|---------|
| `AzureWebJobsStorage__accountName` | Functions storage account name | Functions runtime storage (identity-based) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights output | Telemetry |
| `STAGING_BLOB_ENDPOINT` | Staging storage blob endpoint | Read source articles |
| `SERVING_BLOB_ENDPOINT` | Serving storage blob endpoint | Write processed articles |
| `AI_SERVICES_ENDPOINT` | AI Services endpoint | Content Understanding + embeddings |
| `EMBEDDING_DEPLOYMENT_NAME` | `text-embedding-3-small` | Model deployment name for embeddings |
| `SEARCH_ENDPOINT` | AI Search endpoint | Push chunks to search index |
| `SEARCH_INDEX_NAME` | `kb-articles` (hardcoded default) | Target search index |
| `MISTRAL_DEPLOYMENT_NAME` | `mistral-document-ai-2512` | Mistral Document AI OCR model for `fn_convert_mistral` |

The Function App's own storage account gets **Storage Blob Data Owner** (role `b7e6dc6d-f1e8-4753-8033-0f276bb0955b`) granted to the Function App identity — required for Flex Consumption deployment and `AzureWebJobsStorage` access.

### Container Registry (`container-registry.bicep`)

Hosts Docker images for the Context Aware & Vision Grounded KB Agent container.

| Setting | Value |
|---------|-------|
| SKU | Basic |
| Admin User | Disabled (managed identity pull) |
| Public Network | Enabled |

The module accepts an optional `acrPullPrincipalId` parameter. When provided, it grants the **AcrPull** role to that principal (used to give the web app Container App and Foundry project identity access to pull images). The Function App's AcrPull role is managed separately in `function-app.bicep` — see [Technical Brief](#technical-brief-bicep-dependency-ordering-for-container-apps) for why.

### Foundry Project (`foundry-project.bicep`)

Creates a Foundry project as a child resource of the AI Services account. The project provides the hosting context for the published agent.

| Setting | Value |
|---------|-------|
| Parent | AI Services resource (`ai-{project}-{env}`) |
| Name | `proj-{project}-{env}` |
| Display Name | `KB Agent (proj-{project}-{env})` |

The project endpoint is output for use by agent deployment (AZD `azure.ai.agents` extension) and by the web app client.

The project is tagged with `azd-service-name: agent` so the AZD extension can discover it during deployment.

**Hosted Agent Identities:**

The Foundry hosted agent runtime uses **two different identities** depending on context:

| Context | Identity Used | Notes |
|---------|--------------|-------|
| **Unpublished agent** (testing in Foundry UI) | Foundry Project system-assigned MI | Project-level identity |
| **Published agent** (production `/applications/` endpoint) | AI Services Account system-assigned MI | Account-level identity |

Both identities require RBAC on the same set of dependent resources (AI Search, AI Services for embeddings, Serving Storage for images). The Bicep modules grant roles to both identities via separate role-assignment module invocations in `main.bicep`.

**AZD Environment Variables** (set during `azd ai agent init` or manually):

| Variable | Value | Purpose |
|----------|-------|---------|
| `AZURE_AI_PROJECT_ID` | Full ARM resource ID of the Foundry project | AZD extension uses this to target deployments |
| `AZURE_AI_PROJECT_ENDPOINT` | `https://ai-{project}-{env}.services.ai.azure.com/api/projects/proj-{project}-{env}` | Agent runtime config |
| `AZURE_AI_ACCOUNT_NAME` | `ai-{project}-{env}` | AZD extension uses this for account lookups |
| `AZURE_AI_PROJECT_NAME` | `proj-{project}-{env}` | AZD extension uses this for project lookups |
| `AZURE_OPENAI_ENDPOINT` | `https://ai-{project}-{env}.openai.azure.com/` | OpenAI-compatible endpoint |

### Cosmos DB (`cosmos-db.bicep`)

Serverless NoSQL database for conversation persistence. The web app stores all conversation history here (threads, messages, user metadata).

| Setting | Value |
|---------|-------|
| Kind | `GlobalDocumentDB` |
| Capability | `EnableServerless` |
| Consistency | Session |
| Database | `kb-agent` |
| Container | `conversations` (partition key: `/userId`) |
| Public Network | Enabled |

The `cosmos-db-role.bicep` module assigns the **Cosmos DB Built-in Data Contributor** role (role ID `00000000-0000-0000-0000-000000000002`) to a specified principal (the web app Container App identity).

### Container App (`container-app.bicep`)

Hosts the web app as a containerized Chainlit application with Entra ID Easy Auth.

#### Container Apps Environment

| Setting | Value |
|---------|-------|
| Type | Consumption (Consumption + Dedicated plan) |
| Logging | Linked to Log Analytics workspace |

#### Container App

| Setting | Value |
|---------|-------|
| Identity | System-assigned managed identity |
| Container | Single container from ACR |
| CPU / Memory | 0.5 vCPU / 1 GiB |
| Ingress | External, port 8080, HTTPS-only |
| Scale | Min 0, Max 1 (scale-to-zero for cost savings) |

**Application Settings:**

| Setting | Source | Purpose |
|---------|--------|---------|
| `AGENT_ENDPOINT` | Foundry agent endpoint (from publish script) | Agent Responses API base URL |
| `AI_SERVICES_ENDPOINT` | AI Services endpoint | Azure AI Foundry (token auth) |
| `SERVING_BLOB_ENDPOINT` | Serving storage blob endpoint | Article images for proxy |
| `SERVING_CONTAINER_NAME` | `serving` | Blob container name |
| `COSMOS_ENDPOINT` | Cosmos DB endpoint | Conversation persistence |
| `COSMOS_DATABASE_NAME` | `kb-agent` | Cosmos DB database name |
| `OAUTH_AZURE_AD_CLIENT_ID` | Entra App Registration client ID | Chainlit OAuth — Azure AD login |
| `OAUTH_AZURE_AD_CLIENT_SECRET` | Entra App Registration client secret | Chainlit OAuth — token exchange |
| `OAUTH_AZURE_AD_TENANT_ID` | Azure AD tenant ID | Chainlit OAuth — tenant scope |
| `CHAINLIT_AUTH_SECRET` | Random hex (generated by setup script) | JWT signing for Chainlit sessions |

#### Entra ID Authentication (Dual-Layer)

Authentication uses two complementary layers:

1. **Easy Auth (platform-level sidecar)** — Intercepts all HTTP requests. Unauthenticated requests are redirected to Microsoft login. Configured via `Microsoft.App/containerApps/authConfigs`.

2. **Chainlit OAuth (application-level)** — When `OAUTH_AZURE_AD_CLIENT_ID` is set, the Chainlit app registers an OAuth callback that extracts the user's OID from the Azure AD token. This identity flows to Cosmos DB as the `userId` partition key for per-user conversation isolation.

| Setting | Value |
|---------|-------|
| Provider | Microsoft Entra ID (v2) |
| Tenant Mode | Single-tenant |
| Unauthenticated Action | Redirect to login (return HTTP 302) |
| App Registration | Created via AZD pre-provision hook |
| Redirect URIs | `https://<fqdn>/.auth/login/aad/callback` (Easy Auth) + `https://<fqdn>/auth/oauth/azure-ad/callback` (Chainlit OAuth) |

The Entra App Registration is created by the AZD `preprovision` hook script (`scripts/setup-entra-auth.sh`). The client ID, secret, and tenant ID are stored as AZD environment variables and passed to the Bicep template as parameters. The `postprovision` hook adds both redirect URIs to the app registration.

---

## Security Model

### Zero-Secret Architecture

No keys, connection strings, or secrets appear in application settings or configuration. All service-to-service communication is authenticated via **system-assigned managed identity** — both the Function App and the Container App use this pattern.

```mermaid
flowchart LR
    FA["Function App<br/><i>System Managed Identity</i>"]
    CA["Container App (Web App)<br/><i>System Managed Identity</i>"]
    PA["Published Agent<br/><i>AI Services Account MI</i>"]
    FP["Unpublished Agent<br/><i>Foundry Project MI</i>"]

    FA -->|"Storage Blob Data<br/>Contributor"| ST["Staging Storage"]
    FA -->|"Storage Blob Data<br/>Contributor"| SV["Serving Storage"]
    FA -->|"Storage Blob Data<br/>Owner"| SF["Functions Storage"]
    FA -->|"AcrPull"| ACR
    FA -->|"Cognitive Services<br/>OpenAI User"| AI["AI Services"]
    FA -->|"Cognitive Services<br/>User"| AI
    FA -->|"Search Index Data<br/>Contributor"| SR["AI Search"]
    FA -->|"Search Service<br/>Contributor"| SR

    PA -->|"Cognitive Services<br/>OpenAI User"| AI
    PA -->|"Search Index Data<br/>Reader"| SR
    PA -->|"Storage Blob Data<br/>Reader"| SV

    FP -->|"Cognitive Services<br/>OpenAI User"| AI
    FP -->|"Search Index Data<br/>Reader"| SR
    FP -->|"Storage Blob Data<br/>Reader"| SV
    FP -->|"AcrPull"| ACR

    CA -->|"Cognitive Services<br/>OpenAI User"| AI
    CA -->|"Storage Blob Data<br/>Reader"| SV
    CA -->|"Cosmos DB Built-in<br/>Data Contributor"| CD["Cosmos DB"]
    CA -->|"AcrPull"| ACR["Container Registry"]
```

### Entra ID Authentication

The Container App uses a **dual-layer auth model**: **Easy Auth** (platform-level sidecar) for gateway enforcement + **Chainlit OAuth callback** (application-level) for user identity extraction. The **Entra App Registration** (single-tenant) is created via an AZD pre-provision hook script (`scripts/setup-entra-auth.sh`). Both redirect URIs (`/.auth/login/aad/callback` for Easy Auth and `/auth/oauth/azure-ad/callback` for Chainlit OAuth) are added via the post-provision hook. Only users in the Azure AD tenant can access the web app. Unauthenticated requests are automatically redirected to the Microsoft login page.

### Key Security Settings

| Resource | Setting | Value |
|----------|---------|-------|
| Storage (Staging, Serving) | `allowSharedKeyAccess` | `false` |
| Storage (all) | `allowBlobPublicAccess` | `false` |
| Storage (all) | `minimumTlsVersion` | `TLS1_2` |
| AI Services | `disableLocalAuth` | `true` |
| AI Search | Auth mode | `aadOrApiKey` (AAD preferred, API key fallback) |

### RBAC Role Summary

| Principal | Resource | Role |
|-----------|----------|------|
| Function App | Staging Storage | Storage Blob Data Contributor |
| Function App | Serving Storage | Storage Blob Data Contributor |
| Function App | Functions Storage | Storage Blob Data Owner |
| Function App | Container Registry | AcrPull |
| Function App | AI Services | Cognitive Services OpenAI User |
| Function App | AI Services | Cognitive Services User |
| Function App | AI Search | Search Index Data Contributor |
| Function App | AI Search | Search Service Contributor |
| Foundry Project MI (unpublished agent — Foundry UI) | Container Registry | AcrPull |
| Foundry Project MI (unpublished agent — Foundry UI) | AI Services | Cognitive Services OpenAI User |
| Foundry Project MI (unpublished agent — Foundry UI) | AI Search | Search Index Data Reader |
| Foundry Project MI (unpublished agent — Foundry UI) | Serving Storage | Storage Blob Data Reader |
| AI Services Account MI (published agent) | AI Services | Cognitive Services OpenAI User |
| AI Services Account MI (published agent) | AI Search | Search Index Data Reader |
| AI Services Account MI (published agent) | Serving Storage | Storage Blob Data Reader |
| Container App (Web App) | AI Services | Cognitive Services OpenAI User |
| Container App (Web App) | Serving Storage | Storage Blob Data Reader |
| Container App (Web App) | Cosmos DB | Cosmos DB Built-in Data Contributor |
| Container App (Web App) | Container Registry | AcrPull |

---

## Deployment

### Prerequisites

- Azure CLI with Bicep (`az bicep version`)
- Azure Developer CLI (`azd version`)
- An Azure subscription with sufficient quota in East US 2

### Commands

```bash
# Initialize AZD environment (first time only)
azd init

# Provision all infrastructure
azd provision

# Deploy application code
azd deploy

# Or provision + deploy in one step
azd up
```

AZD reads `azure.yaml` (project root) and `infra/main.parameters.json` to resolve environment-specific values:

| Parameter | Source | Default |
|-----------|--------|---------|
| `environmentName` | `${AZURE_ENV_NAME}` | — (set during `azd init`) |
| `location` | `${AZURE_LOCATION}` | `eastus2` |
| `searchSkuName` | Hardcoded in parameters file | `free` |

### Makefile Targets

| Target | Command |
|--------|---------|
| `make azure-provision` | `azd provision` |
| `make azure-deploy` | `azd deploy` |
| `make azure-agent-deploy` | `azd deploy --service agent` (builds in ACR, deploys to Foundry) |
| `make azure-agent-capability-host` | Ensures account capability host exists with `enablePublicHostingEnvironment=true` |
| `make azure-agent-publish` | `bash scripts/publish-agent.sh` (publish + RBAC) |
| `make azure-agent` | Deploy + publish agent |
| `make azure-deploy-app` | `azd deploy --service web-app` |

---

## Outputs

The following values are exported by `main.bicep` and available as AZD environment variables after provisioning:

| Output | Example Value |
|--------|--------------|
| `AZURE_LOCATION` | `eastus2` |
| `RESOURCE_GROUP` | `rg-{project}-dev` |
| `STAGING_STORAGE_ACCOUNT` | `st{project}stagingdev` |
| `STAGING_BLOB_ENDPOINT` | `https://st{project}stagingdev.blob.core.windows.net/` |
| `SERVING_STORAGE_ACCOUNT` | `st{project}servingdev` |
| `SERVING_BLOB_ENDPOINT` | `https://st{project}servingdev.blob.core.windows.net/` |
| `AI_SERVICES_NAME` | `ai-{project}-dev` |
| `AI_SERVICES_ENDPOINT` | `https://ai-{project}-dev.cognitiveservices.azure.com/` |
| `EMBEDDING_DEPLOYMENT_NAME` | `text-embedding-3-small` |
| `AGENT_DEPLOYMENT_NAME` | `gpt-5-mini` |
| `CU_COMPLETION_DEPLOYMENT_NAME` | `gpt-4.1` |
| `MISTRAL_DEPLOYMENT_NAME` | `mistral-document-ai-2512` |
| `SEARCH_SERVICE_NAME` | `srch-{project}-dev` |
| `SEARCH_ENDPOINT` | `https://srch-{project}-dev.search.windows.net` |
| `FUNCTION_APP_NAME` | `func-{project}-dev` |
| `FUNCTION_APP_URL` | `https://func-{project}-dev.<hash>.<region>.azurecontainerapps.io` |
| `APPINSIGHTS_NAME` | `appi-{project}-dev` |
| `CONTAINER_REGISTRY_NAME` | `cr{project}dev` |
| `CONTAINER_REGISTRY_LOGIN_SERVER` | `cr{project}dev.azurecr.io` |
| `WEBAPP_NAME` | `webapp-{project}-dev` |
| `WEBAPP_URL` | `https://webapp-{project}-dev.<region>.azurecontainerapps.io` |
| `FOUNDRY_PROJECT_NAME` | `proj-{project}-dev` |
| `FOUNDRY_PROJECT_ENDPOINT` | `https://ai-{project}-dev.services.ai.azure.com/api/projects/proj-{project}-dev` |
| `AZURE_AI_PROJECT_ID` | `/subscriptions/.../providers/Microsoft.CognitiveServices/accounts/ai-{project}-dev/projects/proj-{project}-dev` |
| `AZURE_AI_PROJECT_ENDPOINT` | `https://ai-{project}-dev.services.ai.azure.com/api/projects/proj-{project}-dev` |
| `AZURE_AI_ACCOUNT_NAME` | `ai-{project}-dev` |
| `AZURE_AI_PROJECT_NAME` | `proj-{project}-dev` |
| `AZURE_OPENAI_ENDPOINT` | `https://ai-{project}-dev.openai.azure.com/` |
| `COSMOS_ENDPOINT` | `https://cosmos-{project}-dev.documents.azure.com:443/` |
| `COSMOS_DATABASE_NAME` | `kb-agent` |

---

## Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Functions on Container Apps** over Flex Consumption | Flex Consumption (FC1) does not support custom Docker containers, which are required for Playwright + headless Chromium (used by the Mistral converter for HTML → PDF rendering). Elastic Premium (EP1) was considered first but unavailable by a zero-VM quota in the subscription. Container Apps provides custom container support, scale-to-zero, and reuses the existing Container Apps Environment already hosting the web app. |
| 2 | **Three separate storage accounts** | Staging, serving, and functions runtime are isolated for security, lifecycle management, and independent scaling. Shared key access is disabled on staging/serving. |
| 3 | **AIServices kind** (Foundry) | Single resource hosts Content Understanding, OpenAI models (embeddings + agent), and Mistral models, avoiding multiple Cognitive Services accounts. |
| 4 | **Free search tier** | Supports up to 3 indexes, 50 MB storage, vector search, and semantic search — sufficient for dev. Upgrade path to Basic/Standard is straightforward. |
| 5 | **System-assigned managed identity** | Simplest identity model — lifecycle tied to the Function App. No credential rotation or secret management required. |
| 6 | **East US 2 region** | Broadest model availability for the required services: Content Understanding (GA), text-embedding-3-small, gpt-5-mini, Flex Consumption, and AI Search. |
| 7 | **Modular Bicep structure** | Each service is a self-contained module with optional RBAC parameters. Modules are re-deployed with role assignments after the Function App identity is available. |
| 8 | **GlobalStandard model SKU** | Provides highest availability and regional flexibility for OpenAI model deployments. Uses Microsoft-managed capacity across Azure regions. |
| 9 | **Mistral Document AI deployment** | `mistral-document-ai-2512` (format `Mistral AI`) is deployed alongside OpenAI models in the same AIServices resource. The `fn_convert_mistral` pipeline depends on this model plus GPT-4.1 for vision. Requires Playwright (headless Chromium) at runtime for HTML → PDF rendering. |
| 10 | **Anonymous function auth** | Container Apps does not support Azure Functions host keys. All three HTTP-triggered functions (`fn_convert`, `fn_convert_mistral`, `fn_index`) use `AuthLevel.ANONYMOUS`. Access control relies on the Container App's built-in ingress authentication and network-level controls instead. |
| 11 | **AcrPull role in function-app module** | The Function App's AcrPull role assignment is co-located in `function-app.bicep` (not in `container-registry.bicep`) to avoid a circular dependency between the Container App resource and the ACR role assignment. See [Technical Brief](#technical-brief-bicep-dependency-ordering-for-container-apps) below. |

---

## Technical Brief: Bicep Dependency Ordering for Container Apps with ACR

When a Container App pulls images from ACR using its **system-assigned managed identity**, three things must happen in the right order:

1. **Container App** is created with a system-assigned managed identity → produces a `principalId`
2. **AcrPull role** is assigned to that `principalId` on the Container Registry
3. **Container App** uses the ACR registry config (`identity: 'system'`) to authenticate image pulls

Steps 1 and 3 are defined on the **same resource** — the Container App includes both the identity declaration and the `registries` configuration. The `registries` block with `identity: 'system'` requires the AcrPull role (step 2) to already be in place, but step 2 requires the `principalId` that only exists after step 1.

### Why the AcrPull Role Lives in `function-app.bicep`

If the AcrPull role assignment is placed in a **separate Bicep module** (e.g., `container-registry.bicep`), ARM cannot resolve the dependencies:

- The Container App module outputs its `principalId` → passed to the ACR module for the role assignment
- But the Container App's `registries` config needs ACR access _during creation_, before the role module runs
- ARM evaluates the `registries` config as part of creating the Container App, not as a post-creation step

This creates a **cross-module circular dependency** that ARM cannot resolve. The deployment hangs indefinitely in `InProgress` rather than failing with a clear error.

The solution is to keep the AcrPull role assignment **in the same module** as the Container App. Using an `existing` resource reference to the ACR:

```bicep
// In function-app.bicep:

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: split(acrResourceId, '/')[8]
}

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrResourceId, functionApp.id, acrPullRoleId)
  scope: containerRegistry
  properties: {
    principalId: functionApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalType: 'ServicePrincipal'
  }
}
```

Within a single module, ARM resolves the implicit dependency via `functionApp.identity.principalId` and orders the operations correctly:

1. Create the Container App (with identity) → `principalId` is known
2. Assign AcrPull role using that `principalId`
3. Registry config is evaluated — ACR pull succeeds

### General Rule

Whenever a resource's configuration depends on a role that requires that resource's own identity, the role assignment must be **co-located in the same Bicep module**. Splitting them across modules creates a circular dependency that ARM cannot resolve.
