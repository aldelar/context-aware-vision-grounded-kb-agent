# ARD-009 — Agent Container Apps Migration

> **Status:** Accepted
> **Date:** March 10, 2026
> **Deciders:** aldelar
> **Epic:** [009-agent-container-apps](../epics/009-agent-container-apps.md)

## Context

The KB Agent was deployed as a **Foundry Hosted Agent** — a managed Container Apps Environment provisioned and operated by the Foundry platform. While this provided a low-friction deployment experience, several limitations became apparent:

1. **Opaque compute** — Foundry manages the Container App and its environment; we have no visibility into scaling, resource allocation, or runtime configuration.
2. **Coupled deployment** — Deployment requires a multi-step ARM PUT sequence (Application → Deployment → wait for identity → assign RBAC) via a 250-line `publish-agent.sh` script.
3. **Dual identity complexity** — Foundry uses different managed identities for unpublished (project MI) and published (account MI) agents, requiring redundant RBAC assignments.
4. **Limited scaling control** — No ability to configure custom scaling rules, health probes, or resource limits beyond what the Foundry config block allows.
5. **ACR coupling** — Foundry requires an ACR connection on the project and a capability host on the AI Services account.

## Decision

Migrate the KB Agent to a **standard Azure Container App** in the same Container Apps Environment as the web app. Retain the Foundry project for **tracing** (App Insights connection) and **agent registration** (Operate → Assets visibility) only.

## Consequences

### Positive

- **Full control** — We manage the Container App directly: scaling rules, resource limits, health probes, environment variables, all defined in Bicep.
- **Simplified deployment** — `azd deploy --service agent` deploys like any other Container App. No ARM publish script.
- **Single identity** — System-assigned managed identity on the Container App. One set of RBAC assignments.
- **Internal-only networking** — Agent uses internal ingress (no external endpoint). Web app connects via plain HTTP — no Entra token authentication needed.
- **Simpler Foundry project** — No ACR connection or capability host. Just App Insights tracing and optional agent registration.

### Negative

- **More infrastructure to manage** — We own the Container App definition (Bicep module, RBAC, env vars). Previously Foundry handled this.
- **Manual registration** — Agent must be registered in Foundry separately (`scripts/register-agent.sh`) for portal visibility. Previously automatic with hosted deployment.
- **No automatic model association** — Foundry hosted agents could declare model deployments in `infra/azure/azure.yaml`. Now model deployments are managed independently in `infra/azure/infra/modules/ai-services.bicep`.

## Alternatives Considered

| Alternative | Why Rejected |
|------------|--------------|
| Keep Foundry Hosted Agent | Opaque compute, dual-identity RBAC complexity, coupled ARM deployment |
| Azure Kubernetes Service | Over-engineered for a single containerized agent; AKS adds cluster management overhead |
| Azure App Service | Doesn't share the Container Apps Environment; would require separate networking |

## Implementation

See [Epic 009](../epics/009-agent-container-apps.md) for the full story breakdown and implementation details.
