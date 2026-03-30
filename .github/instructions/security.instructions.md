---
name: 'Security Standards'
description: 'Secrets, auth, network, input validation, and code review security rules'
applyTo: "**"
---

# Security Standards

## Secrets & Credentials

- **Never** commit secrets, connection strings, API keys, or tokens
- Use Azure Managed Identity for all service-to-service auth
- Use Key Vault references where managed identity isn't available
- `.env` files are gitignored — they contain local dev credentials populated by `azd -C infra/azure env get-values`
- `.env.sample` files document required variables without values

## Authentication & Authorization

- Azure Entra ID for user authentication (Easy Auth on Container Apps)
- `DefaultAzureCredential` in all application code — supports both local dev and deployed identity
- RBAC role assignments defined in Bicep (`main.bicep`) — never assign roles manually
- Cosmos DB uses native RBAC (Built-in Data Contributor) — no connection strings

## Network & Transport

- HTTPS everywhere — no HTTP endpoints in production
- Container Apps ingress configured with TLS
- Storage accounts: public access disabled nightly (re-enable for dev via `make dev-enable-storage`)

## Input Validation

- Validate all external input at API boundaries (HTTP handlers, function triggers)
- Sanitize file paths and blob names to prevent path traversal
- Image URLs must match known patterns (`/api/images/...`)
- Follow OWASP Top 10 guidelines

## Code Review Checks

- Scan for hardcoded URLs with credentials
- Verify no `os.getenv()` calls return secrets into logs
- Confirm new endpoints have appropriate auth
- Check that new Azure resources use managed identity
