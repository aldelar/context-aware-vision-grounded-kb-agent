---
description: "Pre-deployment validation — verify infra, tests, and configuration before deploying to Azure."
agent: "implementer"
---

# Deploy Check

Validate deployment readiness before pushing to Azure.

## Steps

1. Validate infrastructure:
   - Run `make validate-infra` — check Azure resources exist and are configured
   - Verify Bicep compiles: `az bicep build --file infra/main.bicep`
   - Cross-reference `infra/modules/` against `docs/specs/infrastructure.md`
2. Validate configuration:
   - Check AZD environment is set: `azd env list`
   - Verify required values exist: `azd env get-values`
   - Confirm `azure.yaml` service definitions match actual project structure
3. Validate code:
   - Run `make test` — all unit tests must pass
   - Check for uncommitted changes that could cause drift
4. Produce a deployment readiness report:
   - Infrastructure: Ready / Issues found
   - Configuration: Complete / Missing values
   - Tests: All passing / Failures
   - **Verdict: READY TO DEPLOY / NOT READY** with specific blockers
5. If ready, provide the deployment command sequence:
   ```
   make azure-up           # provision + deploy + auth (or individual steps)
   make azure-kb           # upload + convert + index
   make azure-test         # verify deployment
   ```
