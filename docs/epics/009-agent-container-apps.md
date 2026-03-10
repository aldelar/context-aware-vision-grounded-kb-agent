# Epic 009 — Agent Container Apps Migration

> **Status:** Draft
> **Created:** March 10, 2026
> **Updated:** March 10, 2026

## Objective

Migrate the KB Agent deployment from **Foundry Hosted Agent** to **Azure Container Apps**, giving us full control over compute, scaling, and runtime while preserving Foundry integration for telemetry tracing and agent registration.

After this epic:

- **Agent runs as a Container App** — same Container Apps Environment as the web app, internal-only ingress, no auth overhead
- **Foundry project is retained (trimmed)** — no ACR connection or capability host; keeps App Insights connection and deployer roles for tracing UI
- **Agent is registered in Foundry** — visible under NewFoundry → Operate → Assets with `agent_id=kb-agent`; registration-only (no hosted deployment)
- **Telemetry flows to Foundry** — `APPLICATIONINSIGHTS_CONNECTION_STRING` + `OTEL_SERVICE_NAME=kb-agent` enable trace correlation in the Foundry portal
- **Web app routes internally** — plain HTTP to the agent's internal FQDN; no Entra token required
- **`azd deploy` handles everything** — no separate ARM publish step; agent deploys like any other Container App service

## Success Criteria

- [ ] Agent Container App deployed: `agent-{project}-{env}` with internal-only ingress in existing CAE
- [ ] Agent Container App has system-assigned managed identity with least-privilege RBAC (AI Services, AI Search, Serving Storage)
- [ ] `from_agent_framework` adapter serves `/responses`, `/liveness`, `/readiness` on port 8088
- [ ] Web app connects to agent via internal FQDN over plain HTTP (no Entra token branch)
- [ ] `azd deploy --service agent` deploys the agent independently (no `publish-agent.sh`)
- [ ] Agent registered in Foundry UI under Operate → Assets with `agent_id=kb-agent`
- [ ] Traces appear in Foundry portal with `OTEL_SERVICE_NAME=kb-agent` correlation
- [ ] Foundry project Bicep trimmed: no ACR connection, no capability host
- [ ] All Makefile targets (`agent-dev`, `azure-deploy`, agent logs) work correctly
- [ ] `make test` passes with zero regressions
- [ ] Architecture and infrastructure docs updated to reflect the new topology

---

## Background

### Current State

The KB Agent is deployed as a **Foundry Hosted Agent** — a managed Container Apps Environment provisioned and operated by the Foundry platform:

| Aspect | Current (Foundry Hosted) |
|--------|--------------------------|
| Hosting | Foundry-managed ACA via capability host |
| Deployment | `scripts/publish-agent.sh` → ARM PUT Application + Deployment |
| Identity | Blueprint identity created by Foundry at deployment time |
| RBAC | 6 role modules: 3 for AI Services MI, 3 for Foundry Project MI |
| Agent Endpoint | `https://…/agents/…/runs` (Foundry URL, set by publish script) |
| Web App Auth | Dual-mode: `http://` → no auth, `https://` → Entra token (`https://ai.azure.com/.default`) |
| Foundry Project | ACR connection + capability host + App Insights connection + deployer roles |
| Telemetry | `configure_azure_monitor()` → App Insights → Foundry tracing |
| azure.yaml | `host: azure.ai.agent`, `docker.remoteBuild: true`, `config` block |
| Dockerfile | Foundry layout: `/app/user_agent/` subdirectory convention |

### Proposed State

The KB Agent runs as a **standard Azure Container App** in the same CAE as the web app, with Foundry used only for tracing and agent registration:

| Aspect | Proposed (Container App) |
|--------|--------------------------|
| Hosting | Self-managed Container App in existing CAE (`cae-{project}-{env}`) |
| Deployment | `azd deploy --service agent` (standard Container App flow) |
| Identity | System-assigned managed identity on the Container App |
| RBAC | 3 role modules: AI Services (Cognitive Services User + OpenAI User), AI Search (Index Data Reader + Service Contributor), Serving Storage (Reader) |
| Agent Endpoint | `http://agent-{project}-{env}.internal.{cae-domain}:8088` |
| Web App Auth | Always plain HTTP (internal-only ingress, no auth needed) |
| Foundry Project | App Insights connection + deployer roles only (no ACR, no capability host) |
| Telemetry | Same: `configure_azure_monitor()` → App Insights → Foundry tracing |
| azure.yaml | `host: containerapp` (standard, no remoteBuild or config block) |
| Dockerfile | Standard layout: `WORKDIR /app`, `COPY . .` |

### Change Impact Summary

| Component | Action |
|-----------|--------|
| `infra/modules/agent-container-app.bicep` | **NEW** — agent Container App module |
| `infra/modules/foundry-project.bicep` | **TRIM** — remove ACR connection + capability host |
| `infra/main.bicep` | **REWIRE** — add agent CA module, remove old Foundry hosting RBAC (~6 modules), add new agent RBAC (~3 modules) |
| `azure.yaml` | **UPDATE** — `host: containerapp`, remove `config` block and `remoteBuild` |
| `src/agent/Dockerfile` | **SIMPLIFY** — standard layout instead of Foundry `/app/user_agent/` convention |
| `src/agent/agent.yaml` | **DELETE** — Foundry agent manifest no longer needed |
| `scripts/publish-agent.sh` | **DELETE** — replaced by `scripts/register-agent.sh` |
| `scripts/register-agent.sh` | **NEW** — registration-only script (no hosted deployment) |
| `src/web-app/app/main.py` | **SIMPLIFY** — `_create_agent_client()` always plain HTTP |
| `infra/modules/container-app.bicep` | **UPDATE** — `agentEndpoint` receives internal FQDN |
| `Makefile` | **UPDATE** — azure-deploy, agent logs, test targets |
| `docs/specs/architecture.md` | **UPDATE** — reflect Container App hosting |
| `docs/specs/infrastructure.md` | **UPDATE** — resource inventory, RBAC table |
| `docs/ards/ARD-009-agent-container-apps.md` | **NEW** — architecture decision record |

### RBAC for Agent Container App (Least Privilege)

| Resource | Role | Why |
|----------|------|-----|
| AI Services | Cognitive Services User + Azure AI User | Agent calls GPT model + tools via AI Services |
| AI Search | Search Index Data Reader + Search Service Contributor | Agent queries the KB index (agentic retrieval) |
| Serving Storage | Storage Blob Data Reader | Agent reads images for vision grounding |

---

## Stories

---

### Story 1 — Agent Container App Infrastructure (Bicep)

> **Status:** Not Started
> **Depends on:** None

Create the `agent-container-app.bicep` module, trim the Foundry project Bicep (remove ACR connection + capability host), and rewire `main.bicep` to deploy the agent as a Container App with its own managed identity and RBAC.

#### Deliverables

- [ ] Create `infra/modules/agent-container-app.bicep`:
  - Container App `agent-{baseName}` in existing CAE (accepts `containerAppsEnvId` param)
  - Internal-only ingress on port 8088
  - System-assigned managed identity
  - `azd-service-name: agent` tag for azure.yaml mapping
  - Environment variables: `AI_SERVICES_ENDPOINT`, `SEARCH_ENDPOINT`, `SEARCH_INDEX_NAME`, `SERVING_BLOB_ENDPOINT`, `SERVING_CONTAINER_NAME`, `PROJECT_ENDPOINT`, `AGENT_MODEL_DEPLOYMENT_NAME`, `EMBEDDING_DEPLOYMENT_NAME`, `APPLICATIONINSIGHTS_CONNECTION_STRING`, `OTEL_SERVICE_NAME=kb-agent`
  - Container resource limits: 1.0 CPU, 2Gi memory (match current Foundry config)
  - Outputs: `agentEndpoint` (internal FQDN with port), `agentPrincipalId` (for RBAC)
- [ ] Trim `infra/modules/foundry-project.bicep`:
  - Remove `acrConnection` resource and `acrLoginServer`/`acrResourceId` parameters
  - Remove `accountCapabilityHost` resource
  - Keep: project resource, `appInsightsConnection`, deployer roles, project AI User role, web app AI User role
- [ ] Update `infra/main.bicep`:
  - Add `agentContainerApp` module call, passing CAE ID from web app module
  - Wire agent RBAC: AI Services (Cognitive Services User + Azure AI User), AI Search (Index Data Reader + Service Contributor), Serving Storage (Blob Data Reader)
  - Remove Foundry-hosted-agent RBAC modules (`searchAgentRole`, `aiServicesAgentRole`, `servingStorageAgentRole` for AI Services MI; `searchFoundryRole`, `aiServicesFoundryRole`, `servingStorageFoundryRole` for Foundry Project MI; `containerRegistryFoundryRole`)
  - Remove `acrLoginServer`/`acrResourceId` params from `foundryProject` module call
  - Update `agentEndpoint` param on web app module: pass agent Container App's internal FQDN instead of external Foundry URL
  - Remove `agentEndpoint` top-level parameter (no longer set by publish script)
  - Remove `agentEndpoint` from `main.parameters.json`
- [ ] Ensure web app Container App module (`container-app.bicep`) still receives `agentEndpoint` — now sourced from agent Container App output
- [ ] `az bicep build` succeeds with 0 errors

#### Implementation Notes

- The existing `infra/modules/container-app.bicep` creates the CAE and outputs `containerAppsEnvId` — the new agent module consumes this output.
- The web app module already has an `agentEndpoint` param that sets `AGENT_ENDPOINT` env var — the value changes from external Foundry URL to internal FQDN but the plumbing stays the same.
- The `from_agent_framework` adapter listens on port 8088 and serves `/liveness` and `/readiness` for probes.

#### Definition of Done

- [ ] `agent-container-app.bicep` creates a Container App with internal ingress, managed identity, and correct env vars
- [ ] `foundry-project.bicep` has no ACR connection or capability host resources
- [ ] `main.bicep` wires agent RBAC (3 role modules) and removes old Foundry hosting RBAC (~7 role modules)
- [ ] `agentEndpoint` flows from agent Container App output → web app module (no external parameter)
- [ ] `az bicep build` succeeds with 0 errors
- [ ] `main.parameters.json` has no `agentEndpoint` entry

---

### Story 2 — Agent Deployment & Container Config

> **Status:** Not Started
> **Depends on:** Story 1

Simplify the agent Dockerfile, update `azure.yaml` to deploy as a standard Container App, delete the Foundry agent manifest, and update Makefile targets.

#### Deliverables

- [ ] Simplify `src/agent/Dockerfile`:
  - Standard layout: `WORKDIR /app`, `COPY . .` (remove `/app/user_agent/` convention)
  - Keep: `python:3.12-slim` base, pip install from `requirements.txt`, `EXPOSE 8088`
  - Add `CMD ["python", "main.py"]` explicitly (Foundry platform injects one; Container Apps does not)
- [ ] Update `azure.yaml` agent service:
  - `host: containerapp` (was `azure.ai.agent`)
  - Remove `docker.remoteBuild: true`
  - Remove `config` block (container resources, scale, model deployments — now in Bicep)
- [ ] Delete `src/agent/agent.yaml` (Foundry agent manifest — no longer needed)
- [ ] Update Makefile:
  - `azure-deploy`: remove `publish-agent.sh` call; just `azd deploy` (agent deploys as Container App)
  - `azure-agent-logs`: update to query Container Apps logs (`az containerapp logs show`)
  - Remove Foundry-specific test targets that depend on the old published endpoint
- [ ] Verify `src/agent/main.py` needs no changes (adapter, telemetry, port all stay the same)

#### Implementation Notes

- The `from_agent_framework` adapter already serves the right endpoints; it doesn't care whether it runs in Foundry or a bare Container App.
- `requirements.txt` is generated by `uv export` (existing pattern); no change needed.
- The `config` block in `azure.yaml` was Foundry-specific (model deployments, container resources). Container resources are now in Bicep; model deployments remain in AI Services (already provisioned).

#### Definition of Done

- [ ] Dockerfile uses standard layout (`COPY . .`, explicit `CMD`)
- [ ] `azure.yaml` agent service uses `host: containerapp` with no `remoteBuild` or `config`
- [ ] `agent.yaml` deleted
- [ ] Makefile `azure-deploy` no longer calls `publish-agent.sh`
- [ ] `make agent-dev` still starts the agent locally (no regression)
- [ ] `make test` passes

---

### Story 3 — Web App Agent Routing (Internal FQDN)

> **Status:** Not Started
> **Depends on:** Story 2

Simplify the web app's agent client to always use plain HTTP, removing the Entra token branch that was needed for the Foundry endpoint. The agent is now internal-only — no authentication required.

#### Deliverables

- [ ] Simplify `src/web-app/app/main.py` — `_create_agent_client()`:
  - Remove the `https://` branch that acquires an Entra bearer token via `DefaultAzureCredential` and `get_bearer_token_provider`
  - Always create the agent client with plain HTTP (no auth header)
  - The `AGENT_ENDPOINT` env var now contains the internal FQDN (set by Bicep)
- [ ] Remove unused imports: `get_bearer_token_provider`, `DefaultAzureCredential` (if only used for agent auth)
- [ ] Update `src/web-app/app/config.py` if the `agent_endpoint` field has any validation tied to the Foundry URL pattern
- [ ] Update `src/web-app/.env.sample` to show the new endpoint format: `http://agent-{project}-{env}.internal.{domain}:8088`

#### Implementation Notes

- Currently `_create_agent_client()` checks if `AGENT_ENDPOINT` starts with `http://` (local dev) or `https://` (Foundry deployed). In the new world, both local and deployed use `http://` — local is `http://localhost:8088`, deployed is the internal FQDN.
- `DefaultAzureCredential` may still be used elsewhere in the web app (e.g., Cosmos DB). Only remove the import if it's exclusively used for agent auth.

#### Definition of Done

- [ ] `_create_agent_client()` has no Entra token logic for the agent endpoint
- [ ] Agent calls work locally (`http://localhost:8088`) and deployed (internal FQDN)
- [ ] No `https://ai.azure.com/.default` scope reference in agent client code
- [ ] `make test` passes (web app tests)

---

### Story 4 — Foundry Agent Registration Script

> **Status:** Not Started
> **Depends on:** Story 2

Create a lightweight `register-agent.sh` script that registers the agent in the Foundry portal (Operate → Assets) without deploying it. Delete the old `publish-agent.sh` that handled full ARM deployment.

#### Deliverables

- [ ] Create `scripts/register-agent.sh`:
  - Registers the agent in Foundry with `agent_id=kb-agent`
  - Uses the Foundry REST API to create/update an agent registration entry
  - Points the registration to the Container App's internal endpoint
  - Idempotent: re-running updates the existing registration
  - Uses `DefaultAzureCredential` (or `az` CLI token) for authentication
- [ ] Delete `scripts/publish-agent.sh` (250-line ARM publish script — no longer needed)
- [ ] Update Makefile:
  - Add `azure-register-agent` target that calls `register-agent.sh`
  - Wire into `azure-deploy` if registration should run automatically after deploy
- [ ] Update `.env.sample` files if the script needs new env vars (e.g., `FOUNDRY_PROJECT_ENDPOINT`)

#### Implementation Notes

- The registration approach has been validated in a separate project. The script creates a lightweight entry in Foundry's agent registry — it does NOT deploy containers or create infrastructure.
- The `publish-agent.sh` script currently: (1) ARM PUT Application, (2) ARM PUT Deployment, (3) waits for blueprint identity, (4) assigns RBAC to blueprint identity, (5) stores endpoint in `azd env`. Steps 1–5 are all replaced by Bicep (Container App) + this registration script.
- `OTEL_SERVICE_NAME=kb-agent` set in the Container App env vars enables trace correlation in Foundry even though the agent isn't hosted by Foundry.

#### Definition of Done

- [ ] `register-agent.sh` successfully registers the agent in Foundry (visible under Operate → Assets)
- [ ] `agent_id=kb-agent` appears in the Foundry UI
- [ ] `publish-agent.sh` deleted
- [ ] Script is idempotent (re-run doesn't fail or create duplicates)
- [ ] Makefile has `azure-register-agent` target

---

### Story 5 — Telemetry & Tracing Validation

> **Status:** Not Started
> **Depends on:** Stories 3 + 4

Validate end-to-end that agent traces flow through App Insights to the Foundry portal, and that `OTEL_SERVICE_NAME=kb-agent` correctly correlates traces with the registered agent.

#### Deliverables

- [ ] Verify `APPLICATIONINSIGHTS_CONNECTION_STRING` is set on the agent Container App (from Bicep)
- [ ] Verify `OTEL_SERVICE_NAME=kb-agent` is set on the agent Container App (from Bicep)
- [ ] Send a test query through the web app → agent pipeline
- [ ] Confirm traces appear in Application Insights with service name `kb-agent`
- [ ] Confirm traces are visible in the Foundry portal (Project → Tracing)
- [ ] Confirm agent tool calls (search, vision) generate child spans
- [ ] Document the tracing validation in this story's DoD (screenshots not required, but confirm in text)

#### Implementation Notes

- The telemetry stack is unchanged: `configure_azure_monitor()` + `enable_instrumentation()` in `main.py`. The key difference is that `APPLICATIONINSIGHTS_CONNECTION_STRING` is now set explicitly as a Container App env var (from Bicep) rather than auto-injected by the Foundry hosting platform.
- The Foundry App Insights connection (`appInsightsConnection` in `foundry-project.bicep`) links the App Insights resource to the Foundry project, enabling traces to surface in the Foundry portal.
- This story is primarily validation — no code changes expected unless issues are found.

#### Definition of Done

- [ ] Traces from agent Container App appear in Application Insights
- [ ] Traces are visible in Foundry portal under the project
- [ ] `OTEL_SERVICE_NAME=kb-agent` correctly labels traces
- [ ] Agent tool call spans (search, vision grounding) appear as child spans
- [ ] No telemetry regressions compared to Foundry hosted agent

---

### Story 6 — Documentation & Cleanup

> **Status:** Not Started
> **Depends on:** Story 5

Update architecture docs, infrastructure docs, and create an ARD for the migration decision. Clean up any remaining Foundry hosting references.

#### Deliverables

- [ ] Update `docs/specs/architecture.md`:
  - Agent hosting: Container App (not Foundry Hosted Agent)
  - Agent endpoint: internal FQDN (not Foundry URL)
  - Web app → agent communication: plain HTTP (no Entra token)
  - Foundry role: tracing + agent registry (not hosting)
- [ ] Update `docs/specs/infrastructure.md`:
  - Resource inventory: add `agent-{project}-{env}` Container App
  - Remove: capability host, ACR connection from Foundry project section
  - RBAC table: agent Container App MI roles (AI Services, AI Search, Serving Storage)
  - Module structure: `agent-container-app.bicep` added, `foundry-project.bicep` trimmed
- [ ] Create `docs/ards/ARD-009-agent-container-apps.md`:
  - Context: Foundry Hosted Agent limitations (opaque compute, limited scaling control, coupled deployment)
  - Decision: Migrate to Container Apps; retain Foundry for tracing + registration
  - Trade-offs: more infra to manage vs. full control; simpler deployment vs. manual registration
  - Status: Accepted
- [ ] Verify no stale references to `publish-agent.sh`, `agent.yaml`, or Foundry hosted deployment in any doc
- [ ] Update `README.md` if it references the Foundry deployment workflow

#### Definition of Done

- [ ] All docs accurately describe Container App hosting for the agent
- [ ] ARD documents the decision and trade-offs
- [ ] No stale references to Foundry hosted agent deployment workflow
- [ ] `make help` output matches actual targets
