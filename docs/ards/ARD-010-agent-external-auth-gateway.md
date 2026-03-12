# ARD-010 — Agent External Auth & AI Gateway

> **Status:** Accepted
> **Date:** March 10, 2026
> **Deciders:** aldelar
> **Epic:** [009-agent-container-apps](../epics/009-agent-container-apps.md)

## Context

After migrating the KB Agent to a standard Azure Container App (ARD-009), the agent used internal-only ingress. While functional, this created several limitations:

1. **No external testing** — the agent could only be tested from within the Container Apps Environment (web app → internal FQDN). No way to run integration tests from a developer machine.
2. **No Foundry registration** — Foundry agent registration requires an externally-reachable endpoint and an APIM AI Gateway connection on the project.
3. **No gateway observability** — internal-only traffic bypasses any centralised API management, losing request logging, throttling, and future analytics.

## Decision

Three complementary changes:

1. **External HTTPS ingress** — Switch the agent Container App from internal to external ingress with `allowInsecure: false` (HTTPS-only).
2. **In-code JWT validation** — Add FastAPI middleware (`jwt_auth.py`) that validates Azure Entra ID JWTs on every request (RS256, JWKS-based), bypassing only health probes. Controlled by `REQUIRE_AUTH` env var.
3. **APIM AI Gateway** — Provision an API Management instance (BasicV2) as an AI Gateway, configured as a pass-through proxy to the agent. Connect APIM to the Foundry project to enable agent registration via the gateway.

The web app detects `https://` endpoints and acquires Entra bearer tokens via `DefaultAzureCredential` with scope `https://ai.azure.com/.default`. Local dev continues with plain HTTP — no auth.

## Consequences

### Positive

- **External testability** — `make azure-test-agent` can hit the agent directly from any machine
- **Foundry integration** — Agent registered via AI Gateway, visible in Foundry portal (Operate → Assets) with tracing
- **Gateway security** — APIM provides a stable proxy URL; future rate limiting, monitoring, and access control
- **Flexible routing** — Web app uses registered proxy URL (set by `configure-app-agent-endpoint.sh`); can be switched back to internal FQDN by re-setting `AGENT_ENDPOINT`
- **Zero-trust auth** — JWT validation at the application layer, not at the network layer

### Negative

- **Added infrastructure cost** — APIM BasicV2 adds ~$50/month in dev environments
- **Token refresh complexity** — Web app acquires tokens per-session; for long-running sessions the token may expire (1 hour). Mitigation: `_create_agent_client()` is called per chat start/resume.
- **More moving parts** — External ingress + JWT middleware + APIM + registration script + configure script = 5 components in the auth chain

## Alternatives Considered

| Alternative | Why Rejected |
|------------|--------------|
| Keep internal-only ingress | Cannot test externally, cannot register in Foundry |
| VNet-integrated APIM | Overkill for dev/test; Standard v2 adds $300+/month |
| Easy Auth on agent Container App | Sidecar complexity; doesn't work for plain API clients |
| Portal-only APIM setup | Not IaC; manual config drift |
| API key auth on agent | Less secure than JWT; requires secret management |

## Implementation

See [Epic 009](../epics/009-agent-container-apps.md) Stories 7–10 for the full implementation breakdown.
