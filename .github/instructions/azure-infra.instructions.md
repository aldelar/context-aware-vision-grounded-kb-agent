---
name: 'Azure Infrastructure'
description: 'Bicep modules, AZD deployment, resource naming, and safety rules for infra/azure/'
applyTo: "infra/azure/**"
---

# Azure Infrastructure

## Tooling

- **Bicep** for all infrastructure definitions
- **Azure Developer CLI (AZD)** for provisioning and deployment
- `azd -C infra/azure provision` deploys infra; `azd -C infra/azure deploy` deploys app code
- No manual Azure portal changes — everything in code or scripts

## Module Structure

```
infra/
├── azure/
│   ├── azure.yaml               # AZD project definition
│   ├── hooks/                   # AZD pre/post-provision hooks
│   └── infra/
│       ├── main.bicep           # Orchestration — wires all modules + role assignments
│       ├── main.parameters.json # AZD parameter file (env name, location, search SKU)
│       └── modules/
│           ├── apim.bicep               # API Management — AI Gateway (BasicV2)
│           ├── apim-agent-api.bicep     # APIM agent API definition + backend
│           ├── monitoring.bicep         # Log Analytics + Application Insights
│           ├── storage.bicep            # Reusable storage account with containers + RBAC
│           ├── ai-services.bicep        # AI Services account + model deployments + RBAC
│           ├── search.bicep             # AI Search service + RBAC
│           ├── foundry-project.bicep    # Foundry project (tracing + registration)
│           ├── cosmos-db.bicep          # Cosmos DB NoSQL (serverless) — database + 4 containers
│           ├── cosmos-db-role.bicep     # Cosmos DB Built-in Data Contributor role
│           ├── function-app.bicep       # Functions on Container Apps (called 4×, one per function)
│           ├── container-registry.bicep # Azure Container Registry (Basic) + AcrPull RBAC
│           ├── container-apps-env.bicep # Container Apps Environment (shared)
│           ├── container-app.bicep      # Web App Container App + Easy Auth
│           └── agent-container-app.bicep # Agent Container App (HTTPS ingress + JWT auth, port 8088)
└── docker/
    ├── docker-compose.dev-infra.yml
    └── docker-compose.dev-services.yml
```

## Conventions

- **Naming pattern:** `{resource-prefix}-{projectName}-{env}` (e.g., `func-{project}-dev`, `cosmos-{project}-dev`)
- **Region:** East US 2 — selected for availability of all required services
- **Authentication:** Managed identity only — no keys or secrets in app settings
- **RBAC:** Role assignments defined in `infra/azure/infra/main.bicep`, native Cosmos RBAC via `cosmos-db-role.bicep`
- New resources require: Bicep module + wiring in `infra/azure/infra/main.bicep` + doc update in `docs/specs/infrastructure.md`

## Resource Inventory

The canonical resource inventory is in `docs/specs/infrastructure.md`. Always keep it in sync when adding, removing, or modifying resources.

## Deployment Services

Six services defined in `infra/azure/azure.yaml` — see `docs/setup-and-makefile.md` for the full Makefile reference:
- `agent` — KB Agent Container App (`host: containerapp`, Docker, port 8088)
- `func-convert-cu` — CU converter Container App (`host: containerapp`, Docker)
- `func-convert-mistral` — Mistral converter Container App (`host: containerapp`, Docker)
- `func-convert-markitdown` — MarkItDown converter Container App (`host: containerapp`, Docker)
- `func-index` — Index builder Container App (`host: containerapp`, Docker)
- `web-app` — Chainlit web app on Container Apps (`host: containerapp`, Docker)

## Makefile Targets

See `docs/setup-and-makefile.md` for the full Makefile reference. Key deployment targets:

- `make prod-up` — full Azure deploy (provision + deploy + pipeline)
- `make prod-services-up` — deploy all services
- `make prod-pipeline` — run the Azure KB pipeline (upload + convert + index)
- `make prod-ui-url` — print the deployed web app URL
- `az bicep build --file infra/azure/infra/main.bicep` — validate the Bicep entrypoint compiles

## Safety Rules

- Never use `--force` or `--no-verify` flags
- Always validate Bicep compiles before pushing: `az bicep build --file infra/azure/infra/main.bicep`
- Test infra changes in dev environment before staging/prod
- Post-provision hooks in `infra/azure/azure.yaml` must be idempotent
