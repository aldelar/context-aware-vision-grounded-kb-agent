---
description: "Full end-to-end Azure validation — clean deployed data, run KB pipeline in Azure, execute integration tests against deployed services."
mode: "agent"
agent: "planner"
---

# End-to-End Azure Test

Run a complete Azure environment validation: clean deployed data → KB pipeline in Azure → integration tests against deployed Functions, Agent, and Web App.

## Delegation Model

You are the **orchestrator**. You do NOT run commands, write code, or fix bugs yourself.

For every step that names an agent (@deployer, @debugger, @coder, @reviewer, @tester), you MUST delegate by calling the `runSubagent` tool with:
- `agentName` — the agent name (e.g., `"deployer"`, `"debugger"`, `"coder"`, `"tester"`, `"reviewer"`)
- `prompt` — a self-contained task description with all context the agent needs

After each `runSubagent` call, report:
1. **Agent called:** which agent was invoked
2. **Summary returned:** the key points from the agent's response
3. **Next action:** what happens next based on the result

### Error Recovery

If any step fails:
1. Delegate to @debugger with the full error output, relevant logs, and context
2. @debugger traces the root cause (deployment config, infra issue, code bug, permissions)
3. If it's a code fix: delegate to @coder, then @reviewer to validate
4. If it's an infra/deployment fix: delegate to @deployer
5. Re-run the failed step
6. If the same step fails twice after fixes, escalate to the user

## Phase 0: Discover Available Targets

Delegate to @deployer with this prompt:

> Read the project `Makefile` (in the workspace root). Extract and return:
>
> 1. **Azure section** — all targets between `## AZURE-START` and `## AZURE-END`, with their help comments
> 2. **Utilities — Azure section** — all targets between `## UTIL-AZURE-START` and `## UTIL-AZURE-END`, with their help comments
> 3. **Utilities — Local section** — all targets between `## UTIL-LOCAL-START` and `## UTIL-LOCAL-END` (some local utilities are needed for Azure validation)
>
> For each target, return: `target-name` — description (from the `## ` help comment).
>
> Also read `docs/specs/architecture.md` and `docs/specs/infrastructure.md` for context on what the project does and what Azure services are deployed.
>
> Return the full categorized target list plus a brief summary of the deployed architecture.

Use the returned target list to drive all subsequent phases. Do NOT hardcode target names — always reference the discovered targets.

## Phase 1: Plan

Using the discovered targets, build an execution plan by mapping targets to these logical steps:

1. **Validate Deployment Exists** — identify targets to check deployed app URL, AZD env status
2. **Clean Azure Data** — identify targets that clean Azure storage containers, search index, and any deployed analyzers
3. **KB Pipeline (Azure)** — identify targets that upload staging data, trigger convert Function, trigger index Function
4. **Verify Index** — identify targets that summarize or display the search index contents
5. **Integration Tests** — identify targets that run integration tests against deployed agent and web app
6. **Health Checks** — identify targets for service logs, app URL, agent logs
7. **Cosmos DB cleanup** — note if there are targets to clean Cosmos data, or if that must be done via integration tests

Present the plan with the exact `make` commands discovered, in order, and confirm with the user before proceeding.

## Phase 2: Validate Deployment

Delegate to @deployer:

> Confirm that Azure services are deployed and accessible before running the E2E test.
>
> 1. Run `azd env get-values` to confirm environment is configured
> 2. Run the target that prints the deployed web app URL — verify it returns a URL
> 3. Verify Bicep compiles: `az bicep build --file infra/main.bicep`
> 4. Run `make validate-infra` if that target exists
>
> Targets: [insert discovered targets for app-url and validate-infra]
>
> Report: deployment status (deployed / not deployed / partially deployed), URLs found, any issues.

If deployment is missing or broken, ask the user whether to run the full deploy target (e.g., `azure-up`) before continuing.

## Phase 3: Clean Azure Data

Delegate to @deployer:

> Clean all Azure data to start from a known-empty state.
>
> Run the Azure clean targets that:
> - Empty staging and serving blob containers
> - Delete the AI Search index
> - Delete any deployed analyzers
>
> Targets: [insert discovered azure-clean targets]
>
> Report: which targets succeeded, any errors (e.g., containers already empty, index didn't exist — these are OK).

## Phase 4: KB Pipeline in Azure

### Step 4a — Upload Staging Data

Delegate to @deployer:

> Upload the local `kb/staging/` articles to the Azure staging blob container.
>
> Target: [insert discovered azure-upload-staging target]
>
> Report: success/failure, number of articles uploaded.

### Step 4b — Trigger Convert Function

Delegate to @deployer:

> Trigger the convert Azure Function to process staged articles (HTML → Markdown).
>
> Target: [insert discovered azure-convert target]
>
> This may take several minutes. Report: success/failure, function response, any errors.

### Step 4c — Trigger Index Function

Delegate to @deployer:

> Trigger the index Azure Function to index converted articles into AI Search.
>
> Target: [insert discovered azure-index target]
>
> Report: success/failure, function response, any errors.

### Step 4d — Verify Index Contents

Delegate to @deployer:

> Verify the search index was populated correctly.
>
> Target: [insert discovered azure-index-summarize target, if any]
>
> Report: number of documents in index, article names found, any issues.

## Phase 5: Integration Tests

Delegate to @tester:

> Run all Azure integration tests against the deployed services.
>
> Composite target: [insert discovered azure-test target]
>
> Also run each individual Azure test target for granular results:
> - Agent integration tests (against published Foundry endpoint): [insert discovered azure-test-agent target]
> - Agent dev tests (against unpublished endpoint, if target exists): [insert discovered azure-test-agent-dev target, if any]
> - Web app integration tests (Cosmos + Blob + Agent): [insert discovered azure-test-app target]
>
> For each target, report:
> - Target name
> - Pass/fail
> - Number of tests run
> - Any failures with full error output
>
> If tests fail, return the full traceback for each failure.

If any tests fail, trigger the Error Recovery flow (see above).

## Phase 6: Health Checks

Delegate to @deployer:

> Run health checks against deployed services to verify they're operating correctly.
>
> 1. Verify the web app URL is accessible (HTTP 200 or redirect to auth): [insert discovered app-url target]
> 2. Check app logs for errors (scan recent logs for exceptions/crashes): [insert discovered azure-app-logs target, if any]
> 3. Check agent logs: [insert discovered azure-agent-logs target, if any]
>
> Report:
> - Web App: accessible / unreachable / errors in logs
> - Agent: healthy / errors in logs
> - Any warnings or anomalies

## Phase 7: Final Report

Summarize the full E2E Azure test run:

| Phase | Status | Details |
|-------|--------|---------|
| Deployment Check | ✅/❌ | Services deployed, URLs accessible |
| Clean Azure Data | ✅/❌ | Storage + index cleaned |
| Upload Staging | ✅/❌ | N articles uploaded |
| Convert Function | ✅/❌ | Function response |
| Index Function | ✅/❌ | Function response |
| Index Verification | ✅/❌ | N documents indexed |
| Agent Tests | ✅/❌ | X passed, Y failed |
| App Tests | ✅/❌ | X passed, Y failed |
| Health Checks | ✅/❌ | Services healthy/degraded |

**Overall: PASS / FAIL** with any issues or follow-ups noted.

## Rules

- **Always use `runSubagent`** — never run commands or write code yourself
- **Discover targets dynamically** — read the Makefile; never hardcode target names
- **Stop on blockers** — if the same error persists after two fix attempts, escalate to the user
- **No secrets in output** — never print API keys, connection strings, or tokens
- **Transparency** — after every delegation, report which agent was called and summarize the result
- **Azure Functions may be slow** — convert and index triggers can take minutes; instruct agents to use generous timeouts
- **Permissions matter** — if a step fails with 403/401, check that RBAC roles and managed identity are configured; delegate to @deployer to fix
