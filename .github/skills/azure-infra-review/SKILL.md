---
name: azure-infra-review
description: 'Reviews Bicep modules, azure.yaml, and infrastructure changes for the KB Agent project. Checks naming, RBAC, module wiring, and doc sync. Use when working on infra/ or reviewing infrastructure PRs.'
---

# Azure Infrastructure Review

Review infrastructure changes for correctness, convention compliance, and documentation sync.

## Module Structure

```
infra/
├── azure/
│   ├── azure.yaml               # AZD project definition
│   ├── hooks/                   # AZD pre/post-provision hooks
│   └── infra/
│       ├── main.bicep           # Orchestration — wires all modules + role assignments
│       ├── main.parameters.json # AZD parameter file
│       └── modules/
│           ├── monitoring.bicep         # Log Analytics + Application Insights
│           ├── storage.bicep            # Storage account with containers + RBAC
│           ├── ai-services.bicep        # AI Services + model deployments + RBAC
│           ├── search.bicep             # AI Search service + RBAC
│           ├── foundry-project.bicep    # Foundry project
│           ├── cosmos-db.bicep          # Cosmos DB NoSQL (serverless)
│           ├── cosmos-db-role.bicep     # Cosmos DB native RBAC role
│           ├── function-app.bicep       # Functions on Container Apps (Docker)
│           ├── container-registry.bicep # Azure Container Registry
│           ├── container-app.bicep      # Container Apps Environment + web app
│           ├── container-apps-env.bicep # Container Apps Environment
│           ├── agent-container-app.bicep # Agent Container App
│           ├── apim.bicep               # API Management
│           └── apim-agent-api.bicep     # APIM agent API definition
└── docker/
  ├── docker-compose.dev-infra.yml
  └── docker-compose.dev-services.yml
```

## Review Checklist

### Naming & Conventions
- [ ] Resource names follow `{type}-{projectName}-{env}` pattern
- [ ] Module file names are descriptive and kebab-case
- [ ] Parameters have descriptions and appropriate defaults
- [ ] Region: East US 2 (unless specific service requires otherwise)

### RBAC & Security
- [ ] All role assignments defined in `infra/azure/infra/main.bicep` — not in individual modules
- [ ] Cosmos DB uses native RBAC via `cosmos-db-role.bicep` — no connection strings
- [ ] Managed identity used for all service-to-service auth
- [ ] No secrets or keys in module outputs
- [ ] No secrets in app settings — use managed identity references

### Module Wiring
- [ ] New modules called from `infra/azure/infra/main.bicep`
- [ ] Module outputs consumed by dependent modules
- [ ] Role assignments connect the right identities to the right resources
- [ ] Dependencies expressed via module references (not `dependsOn` strings)

### Service Definitions
- [ ] `infra/azure/azure.yaml` lists all 6 services with correct paths and hosts:
  - `agent` → Container App (Docker, port 8088)
  - `func-convert-cu` → Container App (Docker)
  - `func-convert-mistral` → Container App (Docker)
  - `func-convert-markitdown` → Container App (Docker)
  - `func-index` → Container App (Docker)
  - `web-app` → Container App (Docker)
- [ ] Docker contexts and Dockerfiles referenced correctly

### Documentation Sync
- [ ] `docs/specs/infrastructure.md` updated to reflect any resource changes
- [ ] New resources documented with their purpose, SKU, and connectivity

### Validation
- [ ] Bicep compiles: `az bicep build --file infra/azure/infra/main.bicep`
- [ ] Parameters file is valid JSON with correct structure
- [ ] No hardcoded subscription IDs, resource group names, or tenant IDs

## Reference

- [Infrastructure spec](docs/specs/infrastructure.md)
- [Azure infra instructions](.github/instructions/azure-infra.instructions.md)
