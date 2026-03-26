---
name: 'Azure Infrastructure'
description: 'Bicep modules, AZD deployment, resource naming, and safety rules for infra/'
applyTo: "infra/**"
---

# Azure Infrastructure

## Tooling

- **Bicep** for all infrastructure definitions
- **Azure Developer CLI (AZD)** for provisioning and deployment
- `azd provision` deploys infra; `azd deploy` deploys app code
- No manual Azure portal changes — everything in code or scripts

## Module Structure

```
infra/
├── main.bicep                  # Orchestration — wires all modules + role assignments
├── main.parameters.json        # AZD parameter file (env name, location, search SKU)
└── modules/
    ├── apim.bicep               # API Management — AI Gateway (BasicV2)
    ├── apim-agent-api.bicep     # APIM agent API definition + backend
    ├── monitoring.bicep         # Log Analytics + Application Insights
    ├── storage.bicep            # Reusable storage account with containers + RBAC
    ├── ai-services.bicep        # AI Services account + model deployments + RBAC
    ├── search.bicep             # AI Search service + RBAC
    ├── foundry-project.bicep    # Foundry project (tracing + registration)
    ├── cosmos-db.bicep          # Cosmos DB NoSQL (serverless) — database + 4 containers
    ├── cosmos-db-role.bicep     # Cosmos DB Built-in Data Contributor role
    ├── function-app.bicep       # Functions on Container Apps (called 4×, one per function)
    ├── container-registry.bicep # Azure Container Registry (Basic) + AcrPull RBAC
    ├── container-apps-env.bicep # Container Apps Environment (shared)
    ├── container-app.bicep      # Web App Container App + Easy Auth
    └── agent-container-app.bicep # Agent Container App (HTTPS ingress + JWT auth, port 8088)
```

## Conventions

- **Naming pattern:** `{resource-prefix}-{projectName}-{env}` (e.g., `func-{project}-dev`, `cosmos-{project}-dev`)
- **Region:** East US 2 — selected for availability of all required services
- **Authentication:** Managed identity only — no keys or secrets in app settings
- **RBAC:** Role assignments defined in `main.bicep`, native Cosmos RBAC via `cosmos-db-role.bicep`
- New resources require: Bicep module + wiring in `main.bicep` + doc update in `docs/specs/infrastructure.md`

## Resource Inventory

The canonical resource inventory is in `docs/specs/infrastructure.md`. Always keep it in sync when adding, removing, or modifying resources.

## Deployment Services

Six services defined in `azure.yaml` — see `docs/setup-and-makefile.md` for the full Makefile reference:
- `agent` — KB Agent Container App (`host: containerapp`, Docker, port 8088)
- `func-convert-cu` — CU converter Container App (`host: containerapp`, Docker)
- `func-convert-mistral` — Mistral converter Container App (`host: containerapp`, Docker)
- `func-convert-markitdown` — MarkItDown converter Container App (`host: containerapp`, Docker)
- `func-index` — Index builder Container App (`host: containerapp`, Docker)
- `web-app` — Chainlit web app on Container Apps (`host: containerapp`, Docker)

## Makefile Targets

See `docs/setup-and-makefile.md` for the full Makefile reference. Key deployment targets:

- `make azure-up` — full Azure deploy (provision + deploy + register + configure + auth)
- `make azure-deploy` — deploy all services + CU analyzer
- `make azure-kb` — full Azure KB pipeline (upload + convert + index)
- `make azure-test` — run integration tests against deployed services
- `make validate-infra` — validate Azure infra is ready for local dev

## Safety Rules

- Never use `--force` or `--no-verify` flags
- Always validate Bicep compiles before pushing: `az bicep build --file infra/main.bicep`
- Test infra changes in dev environment before staging/prod
- Post-provision hooks in `azure.yaml` must be idempotent
