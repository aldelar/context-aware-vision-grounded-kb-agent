# ARD-008: Per-Function Container Apps

> **Status:** Accepted
> **Date:** 2026-03-09
> **Epic:** [008 — Per-Function Container Split](../epics/008-per-function-container-split.md)

## Context

The ingestion pipeline originally ran as a single Azure Function App on Container Apps, with all four functions (fn_convert_cu, fn_convert_mistral, fn_convert_markitdown, fn_index) sharing one Docker image, one managed identity, and one set of environment variables and RBAC roles.

This monolithic approach had several drawbacks:
- **Over-privileged identity** — the single managed identity had Cognitive Services User (CU access) even though only fn_convert_cu and fn_convert_mistral need it. fn_index had blob Contributor access even though it only needs Reader on serving storage.
- **Bloated image** — all containers included Playwright + headless Chromium (~500 MB), even though only fn_convert_mistral requires it.
- **Blast radius** — a vulnerability in any function could access all connected services.
- **Coupled deployment** — changing one function required redeploying all four.
- **Environment variable leakage** — all functions received all env vars, including ones they don't use.

## Decision

Split the monolithic Function App into **4 independent Container Apps**, one per function, each with its own:
- Docker image (only fn_convert_mistral includes Playwright)
- System-assigned managed identity
- Least-privilege RBAC role assignments
- Scoped environment variables

## Consequences

### Benefits
- **Least-privilege RBAC** — each identity gets only the roles its function actually needs
- **Smaller images** — 3 of 4 images skip Playwright/Chromium (~500 MB savings)
- **Reduced blast radius** — compromising one function limits exposure to that function's services
- **Independent deployment** — `azd deploy --service func-convert-cu` deploys one function without touching others
- **Independent scaling** — each Container App scales independently based on its own load

### Trade-offs
- **More Azure resources** — 4 Container Apps, 4 managed identities, ~12 RBAC role assignments instead of ~4
- **Bicep complexity** — `main.bicep` calls `function-app.bicep` 4 times with per-function parameters
- **Deployment time** — 4 Docker builds instead of 1 (partially offset by smaller per-image size)

## Alternatives Considered

1. **Keep monolith** — simpler to manage, but violates least-privilege and wastes resources
2. **Two Container Apps** (converters + indexer) — partial improvement, but converters still share one identity with CU access that fn_convert_markitdown doesn't need
3. **Azure Functions Flex Consumption** — would provide per-function scaling, but doesn't support custom Docker containers (needed for Playwright)
