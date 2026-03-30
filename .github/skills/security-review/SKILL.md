---
name: security-review
description: 'Security analysis for Azure-hosted Python services. Checks for managed identity, secret exposure, input validation, RBAC, and OWASP-style vulnerabilities. Use when reviewing endpoints, auth code, infra changes, or any user-input handling.'
---

# Security Review

Perform a security-focused review adapted to the KB Agent project — an Azure-hosted pipeline with managed identity everywhere.

## Risk Context

This project processes knowledge base content and serves it via a conversational agent. Security issues can lead to:
- Unauthorized access to Azure resources (AI Search, Storage, Cosmos DB)
- Data leakage from the knowledge base
- Prompt injection via user queries to the agent
- Path traversal via blob storage operations

## Checklist

### Authentication & Authorization
- [ ] `DefaultAzureCredential` used for all Azure SDK clients — no keys or connection strings
- [ ] Entra ID Easy Auth configured on Container Apps for user-facing endpoints
- [ ] RBAC role assignments defined in `infra/azure/infra/main.bicep` — never assigned manually
- [ ] Cosmos DB uses native RBAC (Built-in Data Contributor via `cosmos-db-role.bicep`) — no connection strings
- [ ] No hardcoded API keys, tokens, or secrets in source code
- [ ] `.env` files are gitignored — they contain local dev credentials from `azd -C infra/azure env get-values`

### Input Validation
- [ ] All external input validated at API boundaries (HTTP handlers, function triggers)
- [ ] Blob paths and names sanitized to prevent path traversal
- [ ] Image URLs match known patterns (`/api/images/...`)
- [ ] User queries to the agent are not used to construct raw API calls without validation
- [ ] No raw string interpolation in Azure SDK calls (search queries, blob paths)

### Secrets & Configuration
- [ ] No `os.getenv()` calls that return secrets into logs
- [ ] No secrets in Bicep `outputs` (outputs are visible in deployment logs)
- [ ] App settings in Container Apps do not contain keys — use managed identity references
- [ ] `.env.sample` files document required variables without values

### Infrastructure Security
- [ ] HTTPS everywhere — no HTTP endpoints in production
- [ ] Container Apps ingress configured with TLS
- [ ] Storage accounts: public access disabled (re-enabled for dev via `make dev-enable-storage`)
- [ ] New Azure resources use managed identity — no keys in app settings
- [ ] RBAC follows least-privilege principle

### Dependencies
- [ ] No known vulnerable dependencies
- [ ] Third-party packages pinned (not using `*` ranges)
- [ ] Dependencies added to the correct service's `pyproject.toml`

## Output Format

Rate each finding:
- **CRITICAL** — Exploitable vulnerability, must fix immediately
- **HIGH** — Significant risk, fix before merge
- **MEDIUM** — Defense-in-depth issue, should address
- **LOW** — Best practice suggestion

Include specific file + line references, the vulnerability type, and a concrete fix.
