# Copilot Instructions

## Project

**Context Aware & Vision Grounded KB Agent** — an Azure-hosted two-stage pipeline that transforms HTML knowledge base articles into an AI-searchable index with image support, fronted by a conversational agent.

- **Stack:** Python 3.12+, Azure (Bicep + AZD), pytest, uv
- **Architecture:** See `docs/specs/architecture.md`
- **Infrastructure:** See `docs/specs/infrastructure.md`
- **Setup & Automation:** See `docs/setup-and-makefile.md` or run `make help`

## Solution Structure

- `src/agent/` — Foundry hosted KB Agent (Starlette + Agent Framework)
- `src/functions/` — Azure Functions: `fn-convert` (HTML→Markdown) + `fn-index` (Markdown→AI Search)
- `src/web-app/` — Chainlit thin client (OpenAI SDK + Cosmos DB data layer)
- `infra/azure/` — AZD project, hooks, and Bicep modules for Azure resources
- `infra/docker/` — Docker Compose topology for local dev infra and services
- `docs/epics/` — Epic and story tracking (source of truth for work status)
- `scripts/` — Automation and setup scripts

## Key Conventions

- **Infrastructure as Code only** — no manual Azure portal changes
- **Managed identity everywhere** — no keys or secrets in code or config
- **Environment-driven config** — `.env` files from `azd -C infra/azure env get-values`, never hardcoded
- **uv** for Python dependency management — each service has its own `pyproject.toml`
- **Tests before commit** — run `make dev-test` to validate the current repo test suite
- **Docs match code** — epic docs must always reflect the actual implementation state

## Failure Policy

- **No implicit degraded mode** — orchestrator, persistence, auth, search, storage, MCP backends, and other spec-required capabilities are required unless an epic, spec, or ARD explicitly says otherwise.
- **Fix missing dependencies at the source** — if tests fail because a required service, emulator, deployment, role assignment, or environment variable is missing, restore that dependency or report the blocker. Do not change application code to make the required dependency optional just to get tests green.
- **Fallbacks require an explicit source of truth** — any new fallback, stub path, or feature-disable branch must cite the governing epic, spec, or ARD and include tests for both the primary and degraded paths.
- **Hidden fallback paths are regressions** — silent startup downgrade, swallowing required-service failures, or returning empty-success results for broken dependencies should be treated as bugs, not resilience improvements.

## Agent-Driven Development

This repo uses a **6-agent hierarchy** that delegates top-down from product intent to implementation, with skills, instructions, and prompts for structured development:

### Agents (`.github/agents/`)

| Agent | Role | Delegates to |
|-------|------|--------------|
| **@release-manager** | Owns user value, release narrative, scope/non-goals, sequencing, and issue triage. Never writes code. | → @technical-pm |
| **@technical-pm** | Owns requirements, architecture decisions (ARDs/specs), decomposition, and epics. Creates and owns the Agents Workbench. Never writes code. | → @tech-lead, → @archivist |
| **@tech-lead** | Drives a single lane (discovery / delivery / convergence): sequences work, sets the quality bar, integrates results. Delegates implementation and review. | → @implementer, → @reviewer |
| **@implementer** | Writes code, manages infra (Bicep/AZD), runs tests, debugs failures, updates epic docs. Full edit + terminal access. | (leaf) |
| **@reviewer** | Reviews for architecture, security, tests, performance, and quality. Never writes code. | (leaf) |
| **@archivist** | Files durable follow-ups as GitHub issues at workbench closure (GitHub MCP only). Never writes code. | (leaf) |

### Agents Workbench Protocol

Agents coordinate through a shared **Agents Workbench** — a temporary, file-based working area under `.agents-workbench/<epic-NN>-<suffix>/`:
- **TechnicalPM creates and owns** the workbench (plan ledger, lanes, decisions) for a piece of work.
- **Each lane** is driven by a TechLead; Implementer and Reviewer subagents record results back into the lane.
- **Results are messages** — subagents return findings to their caller; durable decisions and spec drift are written into the workbench.
- **Archivist closes** the workbench by filing any deferred follow-ups as GitHub issues; the workbench is then disposable.
- See [agents-workbench.instructions.md](instructions/agents-workbench.instructions.md) for the full protocol

### Skills (`.github/skills/`)

Domain-specific knowledge loaded on demand by agents:
- `debugging` — Structured first-pass debugging for test failures and runtime errors
- `architecture-check` — Service boundary validation (agent/functions/web-app/infra isolation)
- `security-review` — Azure-specific security checklist (managed identity, RBAC, secrets, input validation)
- `epic-workflow` — Epic/story lifecycle management with project-specific make targets
- `azure-infra-review` — Bicep module review (naming, RBAC, wiring, doc sync)
- `refactoring` — Safe refactoring across the service-based architecture
- `agent-governance` — Governance patterns using Microsoft Foundry + APIM AI Gateway (rate limiting, content safety, audit)
- `eval-driven-dev` — Evaluation-driven development using Microsoft Evaluations SDK + Foundry
- `microsoft-agent-framework` — Microsoft Agent Framework guidance for Python agent development
- `context-map` — Pre-change codebase analysis and impact mapping template
- `cloud-design-patterns` — 42 cloud design patterns for distributed systems architecture
- `technical-spike-research` — Systematic research methodology for technical spikes
- `github-actions` — GitHub Actions CI/CD workflow design with security-first practices
- `cosmosdb-datamodeling` — Cosmos DB NoSQL data modeling (access patterns, aggregates, partition strategies)
- `azure-deployment-preflight` — Bicep deployment preflight validation (syntax, what-if, permissions)
- `pytest-coverage` — pytest coverage analysis and improvement workflow
- `conventional-commit` — Conventional Commits message generation, commit, and push workflow
- `github-issues` — GitHub issue management using the GitHub MCP server only
- `github-pull-requests` — Pull request creation and merge workflow using the GitHub MCP server only
- `secret-scanning` — GitHub secret scanning, push protection, and alert management
- `ci-readiness` — CI-readiness checklist (per-service unit tests, Bicep build, managed identity, env-driven config)
- `integration-testing` — Integration tests against local Docker-backed Azure emulators (`@pytest.mark.integration`)
- `performance-review` — Performance/cost review (AI Search queries, Cosmos RU/partitions, async I/O, LLM token usage)

### Instructions (`.github/instructions/`)

Composable rules auto-applied by file pattern:
- [python-standards.instructions.md](instructions/python-standards.instructions.md) — Python/uv/Azure SDK conventions (`src/**/*.py`)
- [testing.instructions.md](instructions/testing.instructions.md) — pytest three-tier test strategy (`**/tests/**`)
- [security.instructions.md](instructions/security.instructions.md) — Secrets, auth, and validation rules (`**`)
- [epic-tracking.instructions.md](instructions/epic-tracking.instructions.md) — Epic lifecycle and doc-code consistency (`docs/epics/**`)
- [azure-infra.instructions.md](instructions/azure-infra.instructions.md) — Bicep modules and AZD deployment (`infra/azure/**`)
- [agents-workbench.instructions.md](instructions/agents-workbench.instructions.md) — Cross-agent Agents Workbench protocol (`.agents-workbench/**`)
- [docker.instructions.md](instructions/docker.instructions.md) — Docker best practices for building optimized, secure container images (`**/Dockerfile,**/Dockerfile.*,**/*.dockerfile`)
- [shell-scripting.instructions.md](instructions/shell-scripting.instructions.md) — Shell scripting best practices for bash scripts (`**/*.sh`)
- [makefile.instructions.md](instructions/makefile.instructions.md) — Best practices for authoring GNU Make Makefiles (`**/Makefile,**/makefile,**/*.mk`)
- [secure-coding-owasp.instructions.md](instructions/secure-coding-owasp.instructions.md) — Comprehensive secure coding based on OWASP Top 10 (`**`)
- [context-engineering.instructions.md](instructions/context-engineering.instructions.md) — Guidelines for structuring code to maximize Copilot effectiveness (`**`)
- [web-app.instructions.md](instructions/web-app.instructions.md) — Next.js + CopilotKit web app conventions, dependency rules, and testing patterns (`src/web-app/**`)

### Prompts (`.github/prompts/`)

This repo keeps reusable development workflows as skills rather than prompts. Use `conventional-commit` for commit/push workflows and `github-pull-requests` for PR creation and merge workflows.