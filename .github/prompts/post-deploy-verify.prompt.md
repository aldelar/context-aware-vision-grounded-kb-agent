---
description: "Post-deployment verification — run integration tests and health checks against deployed services."
mode: "agent"
agent: "deployer"
---

# Post-Deploy Verify

Verify deployment health after deploying to Azure.

## Steps

1. Run integration tests:
   - `make azure-test-agent` — test agent endpoint
   - `make azure-test-app` — test web app (Cosmos + Blob + Agent)
   - Report pass/fail for each test suite
2. Check service health:
   - `make azure-app-url` — verify web app URL is accessible
   - `make azure-index-summarize` — verify search index has content
3. Check logs for errors:
   - `make azure-app-logs` — scan for startup errors or crashes
   - `make azure-agent-logs` — check agent health
4. Produce a deployment health report:
   - Agent: Healthy / Issues
   - Web App: Healthy / Issues
   - Search Index: Populated / Empty / Issues
   - **Overall: HEALTHY / DEGRADED / UNHEALTHY**
5. If issues found, suggest diagnostic steps or hand off to @debugger
