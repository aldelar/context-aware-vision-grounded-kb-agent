---
description: "Full end-to-end local validation — clean data, setup environment, run KB pipeline, execute all tests, verify the app works locally."
mode: "agent"
agent: "planner"
---

# End-to-End Local Test

Run a complete local environment validation: clean slate → setup → KB pipeline → tests → app verification.

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
1. Delegate to @debugger with the full error output and context
2. @debugger traces the root cause and returns a diagnosis
3. Delegate to @coder with the diagnosis to apply the fix
4. Delegate to @reviewer to validate the fix is correct and minimal
5. Re-run the failed step via @deployer
6. If the same step fails twice after fixes, escalate to the user

## Phase 0: Discover Available Targets

Delegate to @deployer with this prompt:

> Read the project `Makefile` (in the workspace root). Extract and return:
>
> 1. **Local section** — all targets between `## LOCAL-START` and `## LOCAL-END`, with their help comments
> 2. **Utilities — Local section** — all targets between `## UTIL-LOCAL-START` and `## UTIL-LOCAL-END`, with their help comments
> 3. **Azure section** — all targets between `## AZURE-START` and `## AZURE-END` (some Azure setup is needed for local dev)
> 4. **Utilities — Azure section** — all targets between `## UTIL-AZURE-START` and `## UTIL-AZURE-END`
>
> For each target, return: `target-name` — description (from the `## ` help comment).
>
> Also read `docs/specs/architecture.md` and `docs/specs/infrastructure.md` for context on what the project does.
>
> Return the full categorized target list plus a brief summary of the project architecture.

Use the returned target list to drive all subsequent phases. Do NOT hardcode target names — always reference the discovered targets.

## Phase 1: Plan

Using the discovered targets, build an execution plan by mapping targets to these logical steps:

1. **Clean** — identify targets that clean local KB data (serving outputs, search index)
2. **Setup** — identify the local setup target that installs tools + Python dependencies
3. **Azure Setup** — identify the target that provisions Azure resources needed for local dev (AI Services, Search, Storage) and configures `.env` files
4. **Enable Access** — identify utility targets that re-enable public access on storage/Cosmos (they may be disabled nightly)
5. **KB Pipeline** — identify the target that runs the full local KB pipeline (convert + index + upload)
6. **Unit Tests** — identify the target that runs all fast tests (unit + endpoint, no Azure needed)
7. **App Verification** — identify targets that start the agent and web app locally for manual smoke testing

Present the plan with the exact `make` commands discovered, in order, and confirm with the user before proceeding.

## Phase 2: Clean Slate

Delegate to @deployer:

> Run the clean targets identified in Phase 0 to remove all local KB outputs and delete the search index. This ensures we start from a known-empty state.
>
> Targets to run: [insert discovered clean targets]
>
> Report: which targets succeeded, any errors encountered.

## Phase 3: Setup Environment

### Step 3a — Local Tools & Dependencies

Delegate to @deployer:

> Run the local setup target to install dev tools and Python dependencies.
>
> Target: [insert discovered setup target]
>
> Report: success/failure, any missing tools or dependency errors.

### Step 3b — Azure Resources for Local Dev

Delegate to @deployer:

> Local development requires some Azure resources (AI Services, Search, Storage).
> Run the Azure setup target that provisions these and configures `.env` files.
>
> Target: [insert discovered azure-setup target]
>
> Prerequisites: `az login` and `azd init` must have been run previously.
> If the target fails because PROJECT_NAME is not set, check for a `set-project` target and ask the user for a project name.
>
> Report: success/failure, any provisioning errors, whether `.env` files were created.

### Step 3c — Enable Access (if targets exist)

Delegate to @deployer:

> Run any utility targets that re-enable public access on storage and Cosmos DB (these may be disabled by nightly security policies).
>
> Targets: [insert discovered enable-access targets, if any]
>
> Report: success/failure for each.

### Step 3d — Validate Infrastructure

Delegate to @deployer:

> Run any infrastructure validation target to confirm Azure resources are ready for local dev.
>
> Target: [insert discovered validate-infra target, if any]
>
> Report: validation result — ready or issues found.

## Phase 4: KB Pipeline

Delegate to @deployer:

> Run the full local KB pipeline target to process knowledge base articles (convert HTML → Markdown, index into AI Search, upload serving assets).
>
> Target: [insert discovered kb pipeline target]
>
> Report: success/failure, number of articles processed, any conversion or indexing errors.

## Phase 5: Run All Tests

Delegate to @tester:

> Run the full local test suite using the discovered test target.
>
> Target: [insert discovered test target]
>
> Also run any individual test targets (agent tests, app tests, functions tests) separately to get granular results.
>
> Individual targets: [insert discovered individual test targets]
>
> Report for each:
> - Target name
> - Pass/fail
> - Number of tests run
> - Any failures with full error output

If any tests fail, trigger the Error Recovery flow (see above).

## Phase 6: App Smoke Test

Delegate to @deployer:

> Start the local agent and web app for manual verification.
>
> Agent target: [insert discovered agent target] — note the URL it serves on
> App target: [insert discovered app target] — note the URL it serves on
>
> Report: both services started successfully, URLs to access them.

Present the URLs to the user and ask them to confirm the app is working.

## Phase 7: Final Report

Summarize the full E2E local test run:

| Phase | Status | Details |
|-------|--------|---------|
| Clean | ✅/❌ | ... |
| Setup (local) | ✅/❌ | ... |
| Setup (Azure) | ✅/❌ | ... |
| KB Pipeline | ✅/❌ | ... |
| Tests | ✅/❌ | X passed, Y failed |
| App Smoke | ✅/❌ | URLs verified |

**Overall: PASS / FAIL** with any issues or follow-ups noted.

## Rules

- **Always use `runSubagent`** — never run commands or write code yourself
- **Discover targets dynamically** — read the Makefile; never hardcode target names
- **Stop on blockers** — if the same error persists after two fix attempts, escalate to the user
- **No secrets in output** — never print API keys, connection strings, or tokens
- **Transparency** — after every delegation, report which agent was called and summarize the result
