---
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
    ├── monitoring.bicep         # Log Analytics + Application Insights
    ├── storage.bicep            # Reusable storage account with containers + RBAC
    ├── ai-services.bicep        # AI Services account + model deployments + RBAC
    ├── search.bicep             # AI Search service + RBAC
    ├── foundry-project.bicep    # Foundry project (child of AI Services)
    ├── cosmos-db.bicep          # Cosmos DB NoSQL (serverless)
    ├── cosmos-db-role.bicep     # Cosmos DB Built-in Data Contributor role
    ├── function-app.bicep       # Functions on Container Apps (custom Docker)
    ├── container-registry.bicep # Azure Container Registry (Basic)
    └── container-app.bicep      # Container Apps Environment + web app + Easy Auth
```

## Conventions

- **Naming pattern:** `{resource-prefix}-kbidx-{env}` (e.g., `func-kbidx-dev`, `cosmos-kbidx-dev`)
- **Region:** East US 2 — selected for availability of all required services
- **Authentication:** Managed identity only — no keys or secrets in app settings
- **RBAC:** Role assignments defined in `main.bicep`, native Cosmos RBAC via `cosmos-db-role.bicep`
- New resources require: Bicep module + wiring in `main.bicep` + doc update in `docs/specs/infrastructure.md`

## Resource Inventory

The canonical resource inventory is in `docs/specs/infrastructure.md`. Always keep it in sync when adding, removing, or modifying resources.

## Deployment Services

Three services defined in `azure.yaml`:
- `agent` — Foundry hosted agent (`host: azure.ai.agent`, Docker)
- `functions` — Azure Functions on Container Apps (`host: containerapp`, Docker)
- `web-app` — Chainlit web app on Container Apps (`host: containerapp`, Docker)

## Makefile Targets

- `make azure-up` — full Azure deploy (provision + deploy + auth)
- `make azure-deploy` — deploy all services + CU analyzer + publish agent
- `make azure-kb` — full Azure KB pipeline (upload + convert + index)
- `make azure-test` — run integration tests against deployed services
- `make validate-infra` — validate Azure infra is ready for local dev

## Safety Rules

- Never use `--force` or `--no-verify` flags
- Always validate Bicep compiles before pushing: `az bicep build --file infra/main.bicep`
- Test infra changes in dev environment before staging/prod
- Post-provision hooks in `azure.yaml` must be idempotent
