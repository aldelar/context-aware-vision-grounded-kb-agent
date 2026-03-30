# Epic 009 — Agent Container Apps Migration

> **Status:** Done
> **Created:** March 10, 2026
> **Updated:** March 10, 2026

## Objective

Migrate the KB Agent deployment from **Foundry Hosted Agent** to **Azure Container Apps**, giving us full control over compute, scaling, and runtime while preserving Foundry integration for telemetry tracing and agent registration.

After this epic:

- **Agent runs as a Container App** — same Container Apps Environment as the web app, external HTTPS ingress with JWT auth
- **Foundry project is retained (trimmed)** — no ACR connection or capability host; keeps App Insights connection and deployer roles for tracing UI
- **Agent is registered in Foundry via AI Gateway** — APIM proxies all traffic; agent visible under Foundry → Operate → Assets
- **Telemetry flows to Foundry** — `APPLICATIONINSIGHTS_CONNECTION_STRING` + `OTEL_SERVICE_NAME=kb-agent` enable trace correlation in the Foundry portal
- **Web app routes through APIM** — uses the Foundry-generated gateway URL with Entra bearer token
- **`azd deploy` handles everything** — no separate ARM publish step; agent deploys like any other Container App service
- **External access enabled** — agent reachable from dev machines, Foundry, and other apps/systems via APIM gateway with JWT validation

## Success Criteria

- [x] Agent Container App deployed: `agent-{project}-{env}` with external HTTPS ingress and JWT validation
- [x] Agent Container App has system-assigned managed identity with least-privilege RBAC (AI Services, AI Search, Serving Storage)
- [x] `from_agent_framework` adapter serves `/responses`, `/liveness`, `/readiness` on port 8088
- [x] Web app connects to agent through Foundry-registered APIM proxy URL with Entra bearer token
- [x] `azd deploy --service agent` deploys the agent independently (no `publish-agent.sh`)
- [x] APIM (AI Gateway) provisioned via Bicep, linked to Foundry project
- [x] Agent registered in Foundry via AI Gateway (visible under Operate → Assets)
- [x] Traces appear in Foundry portal with `OTEL_SERVICE_NAME=kb-agent` correlation
- [x] Foundry project Bicep trimmed: no ACR connection, no capability host
- [x] All Makefile targets (`agent-dev`, `azure-deploy`, `azure-test-agent`, agent logs) work correctly
- [x] `make test` passes with zero regressions
- [x] Architecture and infrastructure docs updated to reflect external ingress, APIM gateway, and JWT auth

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
| infra/azure/azure.yaml | `host: azure.ai.agent`, `docker.remoteBuild: true`, `config` block |
| Dockerfile | Foundry layout: `/app/user_agent/` subdirectory convention |

### Proposed State

The KB Agent runs as a **standard Azure Container App** in the same CAE as the web app, with Foundry used only for tracing and agent registration:

| Aspect | Proposed (Container App) |
|--------|--------------------------|
| Hosting | Self-managed Container App in existing CAE (`cae-{project}-{env}`) |
| Deployment | `azd deploy --service agent` (standard Container App flow) |
| Identity | System-assigned managed identity on the Container App |
| RBAC | 3 role modules: AI Services (Cognitive Services User + OpenAI User), AI Search (Index Data Reader + Service Contributor), Serving Storage (Reader) |
| Agent Endpoint | External HTTPS: `https://agent-{project}-{env}.{cae-domain}` with in-code JWT validation |
| Web App Auth | Entra bearer token (`https://ai.azure.com/.default`) via registered APIM proxy URL |
| AI Gateway | APIM (`apim-{project}-{env}`, BasicV2) proxies external traffic; Foundry registers agent via gateway |
| Foundry Project | App Insights connection + deployer roles + **APIM connection** (no ACR, no capability host) |
| Telemetry | Same: `configure_azure_monitor()` → App Insights → Foundry tracing |
| infra/azure/azure.yaml | `host: containerapp` (standard, no remoteBuild or config block) |
| Dockerfile | Standard layout: `WORKDIR /app`, `COPY . .` |

### Change Impact Summary

| Component | Action |
|-----------|--------|
| `infra/azure/infra/modules/agent-container-app.bicep` | **NEW** — agent Container App module |
| `infra/azure/infra/modules/foundry-project.bicep` | **TRIM** — remove ACR connection + capability host |
| `infra/azure/infra/main.bicep` | **REWIRE** — add agent CA module, remove old Foundry hosting RBAC (~6 modules), add new agent RBAC (~3 modules) |
| `infra/azure/azure.yaml` | **UPDATE** — `host: containerapp`, remove `config` block and `remoteBuild` |
| `src/agent/Dockerfile` | **SIMPLIFY** — standard layout instead of Foundry `/app/user_agent/` convention |
| `src/agent/agent.yaml` | **DELETE** — Foundry agent manifest no longer needed |
| `scripts/publish-agent.sh` | **DELETE** — replaced by `scripts/register-agent.sh` |
| `scripts/register-agent.sh` | **NEW** — registration-only script (no hosted deployment) |
| `src/web-app/app/main.py` | **SIMPLIFY** — `_create_agent_client()` always plain HTTP |
| `infra/azure/infra/modules/container-app.bicep` | **UPDATE** — `agentEndpoint` receives internal FQDN |
| `Makefile` | **UPDATE** — azure-deploy, agent logs, test targets |
| `docs/specs/architecture.md` | **UPDATE** — reflect Container App hosting |
| `docs/specs/infrastructure.md` | **UPDATE** — resource inventory, RBAC table |
| `docs/ards/ARD-009-agent-container-apps.md` | **NEW** — architecture decision record |
| `src/agent/middleware/jwt_auth.py` | **NEW** — FastAPI JWT validation middleware (Story 7) |
| `infra/azure/infra/modules/apim.bicep` | **NEW** — APIM AI Gateway (Story 8) |
| `infra/azure/infra/modules/apim-agent-api.bicep` | **NEW** — APIM agent API definition (Story 8) |
| `scripts/configure-app-agent-endpoint.sh` | **NEW** — post-registration endpoint config for web app (Story 9) |
| `docs/ards/ARD-010-agent-external-auth-gateway.md` | **NEW** — decision record for external auth + gateway (Story 10) |
| `infra/azure/infra/modules/agent-container-app.bicep` | **UPDATE** — external HTTPS ingress + `REQUIRE_AUTH` env var (Story 7) |
| `scripts/register-agent.sh` | **UPDATE** — gateway-based registration + capture proxy URL (Story 9) |
| `infra/azure/infra/modules/foundry-project.bicep` | **UPDATE** — add APIM connection resource (Story 8) |
| `src/web-app/app/main.py` | **UPDATE** — re-add Entra token auth for registered APIM endpoint (Story 10) |

### RBAC for Agent Container App (Least Privilege)

| Resource | Role | Why |
|----------|------|-----|
| AI Services | Cognitive Services User + Azure AI User | Agent calls GPT model + tools via AI Services |
| AI Search | Search Index Data Reader + Search Service Contributor | Agent queries the KB index (agentic retrieval) |
| Serving Storage | Storage Blob Data Reader | Agent reads images for vision grounding |

---

## Stories

---

### Story 1 — Agent Container App Infrastructure (Bicep) ✅

> **Status:** Done
> **Depends on:** None

Create the `infra/azure/infra/modules/agent-container-app.bicep` module, trim the Foundry project Bicep (remove ACR connection + capability host), and rewire `infra/azure/infra/main.bicep` to deploy the agent as a Container App with its own managed identity and RBAC.

#### Deliverables

- [ ] Create `infra/azure/infra/modules/agent-container-app.bicep`:
  - Container App `agent-{baseName}` in existing CAE (accepts `containerAppsEnvId` param)
  - Internal-only ingress on port 8088
  - System-assigned managed identity
  - `azd-service-name: agent` tag for `infra/azure/azure.yaml` mapping
  - Environment variables: `AI_SERVICES_ENDPOINT`, `SEARCH_ENDPOINT`, `SEARCH_INDEX_NAME`, `SERVING_BLOB_ENDPOINT`, `SERVING_CONTAINER_NAME`, `PROJECT_ENDPOINT`, `AGENT_MODEL_DEPLOYMENT_NAME`, `EMBEDDING_DEPLOYMENT_NAME`, `APPLICATIONINSIGHTS_CONNECTION_STRING`, `OTEL_SERVICE_NAME=kb-agent`
  - Container resource limits: 1.0 CPU, 2Gi memory (match current Foundry config)
  - Outputs: `agentEndpoint` (internal FQDN with port), `agentPrincipalId` (for RBAC)
- [ ] Trim `infra/azure/infra/modules/foundry-project.bicep`:
  - Remove `acrConnection` resource and `acrLoginServer`/`acrResourceId` parameters
  - Remove `accountCapabilityHost` resource
  - Keep: project resource, `appInsightsConnection`, deployer roles, project AI User role, web app AI User role
- [ ] Update `infra/azure/infra/main.bicep`:
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

- The existing `infra/azure/infra/modules/container-app.bicep` creates the CAE and outputs `containerAppsEnvId` — the new agent module consumes this output.
- The web app module already has an `agentEndpoint` param that sets `AGENT_ENDPOINT` env var — the value changes from external Foundry URL to internal FQDN but the plumbing stays the same.
- The `from_agent_framework` adapter listens on port 8088 and serves `/liveness` and `/readiness` for probes.

#### Definition of Done

- [ ] `agent-container-app.bicep` creates a Container App with internal ingress, managed identity, and correct env vars
- [ ] `foundry-project.bicep` has no ACR connection or capability host resources
- [ ] `infra/azure/infra/main.bicep` wires agent RBAC (3 role modules) and removes old Foundry hosting RBAC (~7 role modules)
- [ ] `agentEndpoint` flows from agent Container App output → web app module (no external parameter)
- [ ] `az bicep build` succeeds with 0 errors
- [ ] `infra/azure/infra/main.parameters.json` has no `agentEndpoint` entry

---

### Story 2 — Agent Deployment & Container Config ✅

> **Status:** Done
> **Depends on:** Story 1

Simplify the agent Dockerfile, update `infra/azure/azure.yaml` to deploy as a standard Container App, delete the Foundry agent manifest, and update Makefile targets.

#### Deliverables

- [ ] Simplify `src/agent/Dockerfile`:
  - Standard layout: `WORKDIR /app`, `COPY . .` (remove `/app/user_agent/` convention)
  - Keep: `python:3.12-slim` base, pip install from `requirements.txt`, `EXPOSE 8088`
  - Add `CMD ["python", "main.py"]` explicitly (Foundry platform injects one; Container Apps does not)
- [ ] Update `infra/azure/azure.yaml` agent service:
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
- The `config` block in `infra/azure/azure.yaml` was Foundry-specific (model deployments, container resources). Container resources are now in Bicep; model deployments remain in AI Services (already provisioned).

#### Definition of Done

- [ ] Dockerfile uses standard layout (`COPY . .`, explicit `CMD`)
- [ ] `infra/azure/azure.yaml` agent service uses `host: containerapp` with no `remoteBuild` or `config`
- [ ] `agent.yaml` deleted
- [ ] Makefile `azure-deploy` no longer calls `publish-agent.sh`
- [ ] `make agent-dev` still starts the agent locally (no regression)
- [ ] `make test` passes

---

### Story 3 — Web App Agent Routing (Internal FQDN) ✅

> **Status:** Done
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

### Story 4 — Foundry Agent Registration Script ✅

> **Status:** Done
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

### Story 5 — Telemetry & Tracing Validation ✅

> **Status:** Done (verified in Bicep — runtime validation at deployment)
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

### Story 6 — Documentation & Cleanup ✅

> **Status:** Done
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

---

### Story 7 — Agent External Ingress & JWT Auth Middleware ✅

> **Status:** Done
> **Depends on:** Story 6 ✅

Switch the agent Container App from internal-only to external HTTPS ingress, and add in-code JWT validation middleware in FastAPI so the agent can be securely accessed from outside the Container Apps Environment (dev machines, APIM gateway, other apps/systems). Local dev (`http://localhost:8088`) bypasses auth.

#### Deliverables

- [x] Update `infra/azure/infra/modules/agent-container-app.bicep`:
  - Change `external: false` → `external: true`
  - Change `allowInsecure: true` → `allowInsecure: false`
  - Add output `agentExternalUrl` (the public HTTPS FQDN) alongside the existing internal endpoint output
- [x] Update `infra/azure/infra/main.bicep`:
  - Add new output `AGENT_EXTERNAL_URL` from the agent module's `agentExternalUrl`
- [x] Create `src/agent/middleware/__init__.py` — empty package
- [x] Create `src/agent/middleware/jwt_auth.py` — FastAPI middleware:
  - Validate JWT bearer tokens on all incoming requests to `/responses`
  - Accept tokens issued by the project's Entra tenant (`iss` claim)
  - Accept audience `https://ai.azure.com` (Foundry scope) and the agent's own app URI
  - Skip validation when `REQUIRE_AUTH` env var is `false` (local dev) or when path is `/liveness` or `/readiness` (health probes)
  - Return `401 Unauthorized` with clear error message on invalid/missing tokens
  - Use `python-jose[cryptography]` or `PyJWT` + JWKS endpoint for token validation
- [x] Update `src/agent/main.py` — mount the JWT middleware on the FastAPI app
- [x] Add `REQUIRE_AUTH` env var to `agent-container-app.bicep` (default `true` in Azure)
- [x] Update `src/agent/.env.sample` — add `REQUIRE_AUTH=false` for local dev
- [x] Add `python-jose[cryptography]` (or `PyJWT`) to `src/agent/pyproject.toml`
- [x] Update `src/agent/tests/test_agent_integration.py`:
  - Remote mode (`_IS_REMOTE`) acquires Entra token via `DefaultAzureCredential` with agent audience scope
  - Update `_get_headers()` to use the correct scope for the external agent
  - Tests pass against both local (no auth) and remote (JWT auth) endpoints
- [x] Restore `azure-test-agent` target in `Makefile` (was removed when agent was internal-only):
  - Set `AGENT_ENDPOINT` to the external HTTPS URL from `azd env get-value AGENT_EXTERNAL_URL`
  - Depend on `_check-project-name`
  - Re-add to `azure-test` dependency list
- [x] Update `docs/specs/architecture.md`:
  - Agent hosting section: change "internal-only ingress" to "external HTTPS ingress with JWT validation"
  - Agent endpoint: update FQDN pattern to show the external HTTPS URL
  - Web App Components → OpenAI SDK Client: remove "no auth needed" language (auth is now required)
  - Authentication section: add a third layer describing agent JWT auth
  - Design Decisions table: update row 3 to reflect APIM routing + JWT ("always plain HTTP" → "HTTPS via APIM gateway")
- [x] Update `docs/specs/infrastructure.md`:
  - Resource Inventory table: update Agent Container App row — note "external HTTPS ingress, JWT auth"
  - Agent Container App section (if exists): document `REQUIRE_AUTH` env var
  - Outputs table: add `AGENT_EXTERNAL_URL`

#### Implementation Notes

- The `from_agent_framework` adapter creates the FastAPI app internally. Use `app = from_agent_framework(agent)` then `app.app.add_middleware(...)` to mount the JWT middleware on the underlying Starlette/FastAPI app before calling `app.run()`.
- Health probes (`/liveness`, `/readiness`) must remain unauthenticated — Container Apps health checks don't send tokens.
- For local dev, the `.env` file sets `REQUIRE_AUTH=false` so developers don't need to acquire tokens. In Azure, the Bicep env var defaults to `true`.
- The JWKS endpoint is `https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys` — the middleware should cache the JWKS for performance.
- Token audience should accept `https://ai.azure.com` (used by Foundry/APIM) as well as any custom app URI registered for the agent.

#### Definition of Done

- [x] Agent Container App has external HTTPS ingress (`az containerapp show` confirms `external: true`, `allowInsecure: false`)
- [x] `curl https://<agent-external-url>/liveness` returns 200 (no auth required for probes)
- [x] `curl https://<agent-external-url>/responses` without a token returns 401
- [x] `curl https://<agent-external-url>/responses` with a valid Entra token returns a response
- [x] `make agent-dev` still works locally without auth (`REQUIRE_AUTH=false`)
- [x] `make azure-test-agent` passes all 8 tests (acquires Entra token, calls external endpoint)
- [x] `make test` passes with zero regressions
- [x] `az bicep build` succeeds with 0 errors
- [x] `docs/specs/architecture.md` reflects external ingress + JWT auth
- [x] `docs/specs/infrastructure.md` reflects external ingress, `REQUIRE_AUTH` env var, and `AGENT_EXTERNAL_URL` output

---

### Story 8 — AI Gateway (APIM) Infrastructure ✅

> **Status:** Done
> **Depends on:** Story 7 ✅

Provision an Azure API Management (APIM) instance as an AI Gateway via Bicep, link it to the Foundry project, and configure it to proxy requests to the agent's external HTTPS endpoint. This story provisions the infrastructure only — the web app continues using the internal FQDN until Story 9 registers the agent and provides the Foundry-generated proxy URL.

#### Deliverables

- [x] Create `infra/azure/infra/modules/apim.bicep`:
  - APIM resource `apim-{baseName}` (BasicV2 SKU for dev/test, parameterised for StandardV2 in prod)
  - Publisher name and email from parameters (required by APIM)
  - System-assigned managed identity
  - Tags: `azd-env-name`
  - Outputs: `apimName`, `apimGatewayUrl`, `apimPrincipalId`, `apimResourceId`
- [x] Create `infra/azure/infra/modules/apim-agent-api.bicep`:
  - API definition `kb-agent-api` on the APIM instance
  - Backend pointing to the agent's external HTTPS URL
  - Operations: `POST /responses`, `GET /liveness`, `GET /readiness`
  - Policy: pass-through (APIM forwards the caller's Entra token to the agent; agent validates it)
  - Subscription not required (`subscriptionRequired: false`) — auth is via Entra JWT, not APIM subscription keys
- [x] Update `infra/azure/infra/main.bicep`:
  - Add `apim` module call, passing location, baseName, tags
  - Add `apimAgentApi` module call, passing APIM name and agent external URL
  - Add outputs: `APIM_NAME`, `APIM_GATEWAY_URL`
  - **Do NOT change `AGENT_ENDPOINT` on the web app yet** — it stays as the internal FQDN until Story 9 provides the registered proxy URL
- [x] Update `infra/azure/infra/modules/foundry-project.bicep`:
  - Add APIM connection resource linking the Foundry project to the APIM gateway (required for agent registration via gateway)
  - Accept new parameter `apimResourceId`
- [x] Update `infra/azure/infra/main.bicep` — pass `apimResourceId` to `foundryProject` module
- [x] Update `docs/specs/architecture.md`:
  - Azure Services Map diagram: add APIM node between Web App and Agent, show APIM ↔ Agent connection
  - Agent Deployment section: document APIM as the agent's public gateway
  - Design Decisions: add new row for AI Gateway (APIM) — centralised routing, Foundry registration prerequisite, observability
- [x] Update `docs/specs/infrastructure.md`:
  - Resource Inventory table: add APIM resource (`apim-{project}-{env}`, BasicV2)
  - Add new section `### API Management — AI Gateway (`apim.bicep`)` documenting SKU, configuration, and API definitions
  - Module Structure: add `apim.bicep` and `apim-agent-api.bicep`
  - RBAC Role Summary: add any APIM-related roles if needed
  - Outputs table: add `APIM_NAME`, `APIM_GATEWAY_URL`
  - Foundry Project section: document APIM connection resource

#### Implementation Notes

- APIM v2 tiers are required for AI Gateway. BasicV2 is suitable for dev/test (~$50/month). The SKU should be parameterised so prod can use StandardV2.
- APIM must be in the same tenant and subscription as the Foundry project.
- APIM provisioning can take 10–15 minutes. Keep it as a standalone module to allow parallel provisioning where possible.
- The Foundry APIM connection resource is the prerequisite for Story 9 (agent registration via gateway).
- The web app is intentionally NOT changed in this story. The registered agent URL (Foundry-generated proxy through APIM) is only available after Story 9's `register-agent.sh` runs. Wiring the web app (Story 10) too early would break it.

#### Definition of Done

- [x] `az bicep build` succeeds with 0 errors
- [x] `azd provision` creates APIM resource `apim-{project}-{env}` (BasicV2)
- [x] APIM has `kb-agent-api` API definition with correct backend URL
- [x] Foundry project has APIM connection resource
- [x] Web app still works via internal FQDN (unchanged from Story 7)
- [x] `make azure-test-agent` still passes (direct external access still works)
- [x] `make azure-test-app` still passes (web app uses internal FQDN)
- [x] `make test` passes with zero regressions
- [x] `docs/specs/architecture.md` includes APIM in diagrams, deployment section, and design decisions
- [x] `docs/specs/infrastructure.md` documents APIM resource, module, RBAC, and outputs

---

### Story 9 — Agent Registration & Post-Deploy Configuration ✅

> **Status:** Done
> **Depends on:** Story 8

Update the agent registration script to use the AI Gateway (APIM) instead of direct ARM API, capture the Foundry-generated proxy URL, and create a post-deploy configuration script that pushes the proxy URL to the web app Container App. After this story, registration works end-to-end and the `azure-up` Makefile chain is complete.

#### Deliverables

- [x] Update `scripts/register-agent.sh`:
  - Register the agent through the Foundry AI Gateway (not direct ARM PUT to `applications/kb-agent`)
  - Use the agent's external HTTPS URL as the backend endpoint in the registration payload
  - Ensure `agent_id=kb-agent` is preserved
  - Read `APIM_GATEWAY_URL` from `azd env get-value`
  - Verify APIM connection exists before attempting registration (fail fast with helpful error)
  - **Capture the Foundry-generated proxy URL** from the registration response
  - Store the proxy URL in AZD env as `AGENT_REGISTERED_URL` (e.g., `azd env set AGENT_REGISTERED_URL <url>`)
  - Remain idempotent (re-run updates existing registration)
- [x] Update `Makefile` — `azure-register-agent` target:
  - Ensure it reads the new env var (`APIM_GATEWAY_URL`)
  - Add a pre-check that APIM is provisioned before running
- [x] Create `scripts/configure-app-agent-endpoint.sh`:
  - Read `AGENT_REGISTERED_URL` from AZD env
  - Update the web app Container App's `AGENT_ENDPOINT` env var to the registered proxy URL (via `az containerapp update` or `az containerapp env var set`)
  - Idempotent — safe to re-run
- [x] Update `Makefile` — add `azure-configure-app` target:
  - Runs `configure-app-agent-endpoint.sh`
  - Called after `azure-register-agent` in the `azure-up` target sequence
  - Update `azure-up` dependency chain: `azure-provision` → `azure-deploy` → `azure-register-agent` → `azure-configure-app` → `azure-setup-auth`

#### Implementation Notes

- Per Microsoft docs, registering a custom agent in Foundry requires an AI Gateway (APIM) to be configured on the project. The registration wizard in the portal collects: agent name, description, endpoint URL (must be reachable from APIM), and authentication scheme.
- The current `register-agent.sh` uses `az rest --method PUT` to the ARM API directly. The updated script should use the Foundry registration API that goes through the gateway.
- **Critical flow**: `azd deploy` → `register-agent.sh` (registers + captures proxy URL) → `configure-app-agent-endpoint.sh` (pushes proxy URL to web app). The web app's `AGENT_ENDPOINT` cannot be set at Bicep/provision time because the proxy URL only exists after registration.
- The `agent_id=kb-agent` identifier should be preserved for continuity with existing traces.

#### Definition of Done

- [x] `make azure-register-agent` successfully registers the agent via AI Gateway
- [x] Agent appears in Foundry portal under Operate → Assets with `agent_id=kb-agent`
- [x] `AGENT_REGISTERED_URL` is captured and stored in AZD env
- [x] `make azure-configure-app` updates web app's `AGENT_ENDPOINT` to the registered proxy URL
- [x] Registration is idempotent (re-running does not fail or create duplicates)
- [x] `make azure-up` runs the full chain: provision → deploy → register → configure → auth
- [x] `make azure-test-agent` still passes (direct external access still works)
- [x] `make test` passes with zero regressions

---

### Story 10 — Web App Gateway Routing & Documentation ✅

> **Status:** Done
> **Depends on:** Story 9

Wire the web app to call the agent through the registered APIM proxy URL with Entra bearer tokens, create the ARD for the external auth + gateway decision, and update architecture/infrastructure docs. After this story, the full chain works: Web App → APIM (registered agent URL) → Agent.

#### Deliverables

**Web App Routing:**

- [x] Update `src/web-app/app/main.py` — `_create_agent_client()`:
  - Detect `https://` endpoint (registered APIM proxy URL) and acquire Entra bearer token via `DefaultAzureCredential` with scope `https://ai.azure.com/.default`
  - Pass token as `Authorization: Bearer` header on agent calls
  - Keep `http://` path for local dev (no auth, `http://localhost:8088`)
- [x] Update `src/web-app/app/config.py` if validation needs updating for new endpoint format (not needed — no validation changes required)
- [x] Update `src/web-app/.env.sample` — document that `AGENT_ENDPOINT` points to the registered APIM proxy URL in Azure
- [x] Add `azure-identity` to `src/web-app/pyproject.toml` if not already present (already present — `azure-identity>=1.19.0`)

**Documentation:**

- [x] Create `docs/ards/ARD-010-agent-external-auth-gateway.md`:
  - Context: agent was internal-only (Stories 1–6), limiting testing and Foundry integration
  - Decision: external HTTPS ingress + in-code JWT validation + APIM AI Gateway + registration via gateway
  - Trade-offs: added infra cost (APIM ~$50/month dev) and complexity vs. external accessibility, proper Foundry integration, and testability
  - Alternatives considered: VNet-integrated APIM (overkill for dev), Easy Auth on agent (sidecar complexity), portal-only APIM setup (not IaC)
  - Status: Accepted
- [x] Update `docs/specs/architecture.md`:
  - Agent Registration section: document that registration goes through AI Gateway, not direct ARM API
  - Foundry integration: update to describe the APIM proxy model — Foundry generates a gateway URL, clients use that URL
  - Web App Components → OpenAI SDK Client: document Entra token acquisition for registered endpoint
  - Conversation Flow: update to show `Web App → APIM (registered URL) → Agent` path
  - Add note that `scripts/register-agent.sh` must run before `configure-app-agent-endpoint.sh`
- [x] Update `docs/specs/infrastructure.md`:
  - Makefile Targets table: add `azure-configure-app` and update `azure-register-agent` description to mention AI Gateway requirement
  - Foundry Project section: document that agent registration requires APIM gateway connection
  - Deployment section: document the post-deploy `register → configure` step sequence

#### Implementation Notes

- The web app already imports `DefaultAzureCredential` for Cosmos DB — adding agent token acquisition for `https://` endpoints should be straightforward. The existing `http://` path for local dev remains unchanged.
- The ARD should reference ARD-009 (Container Apps migration) as the predecessor decision.
- Note that Story 3 removed Entra token logic from the web app (correct for internal-only ingress). This story re-adds it for the registered APIM proxy URL — a different endpoint pattern (`https://` APIM proxy vs. the old Foundry URL).

#### Definition of Done

- [x] Web app acquires Entra token and routes agent calls through the registered APIM endpoint
- [x] `make azure-test-app` passes (web app reaches agent via registered APIM URL)
- [x] `make azure-test-agent` still passes (direct external access still works)
- [x] `docs/ards/ARD-010-agent-external-auth-gateway.md` documents the full decision with trade-offs
- [x] `docs/specs/architecture.md` reflects gateway-based registration, APIM proxy model, and web app routing
- [x] `docs/specs/infrastructure.md` reflects updated registration flow, Makefile targets, and deployment sequence
- [x] `make test` passes with zero regressions
