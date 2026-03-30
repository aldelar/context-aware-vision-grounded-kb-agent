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

## Agent-Driven Development

This repo uses a **3-agent handoff model** with skills, instructions, and prompts for structured development:

### Agents (`.github/agents/`)

| Agent | Role | Handoffs |
|-------|------|----------|
| **@planner** | Research codebase, produce plans, create scratchpads and TODOs. Never writes code. | → @implementer, → @reviewer |
| **@implementer** | Write code, manage infra (Bicep/AZD), run tests, debug failures, update epic docs. Full edit + terminal access. | → @reviewer, → @planner |
| **@reviewer** | Code review for architecture, security, tests, quality. Never writes code. | → @implementer (fix/rework), → @planner (re-plan) |

### Shared Scratchpad Protocol

Agents persist context across handoffs via append-only scratchpad files in `shared-scratchpads/`:
- **Planner creates** a scratchpad as their first action in every session
- **All agents append** before every handoff — timestamped entries with decisions, constraints, findings
- **Reviewer closes** with `IMPLEMENTATION COMPLETE` marker on final approval
- See [shared-scratchpad.instructions.md](instructions/shared-scratchpad.instructions.md) for the full protocol

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
- `conventional-commit` — Conventional Commits message generation workflow
- `github-issues` — GitHub issue management using MCP tools and `gh api`
- `secret-scanning` — GitHub secret scanning, push protection, and alert management

### Instructions (`.github/instructions/`)

Composable rules auto-applied by file pattern:
- [python-standards.instructions.md](instructions/python-standards.instructions.md) — Python/uv/Azure SDK conventions (`src/**/*.py`)
- [testing.instructions.md](instructions/testing.instructions.md) — pytest three-tier test strategy (`**/tests/**`)
- [security.instructions.md](instructions/security.instructions.md) — Secrets, auth, and validation rules (`**`)
- [epic-tracking.instructions.md](instructions/epic-tracking.instructions.md) — Epic lifecycle and doc-code consistency (`docs/epics/**`)
- [azure-infra.instructions.md](instructions/azure-infra.instructions.md) — Bicep modules and AZD deployment (`infra/azure/**`)
- [shared-scratchpad.instructions.md](instructions/shared-scratchpad.instructions.md) — Cross-agent scratchpad protocol (`shared-scratchpads/**`)
- [docker.instructions.md](instructions/docker.instructions.md) — Docker best practices for building optimized, secure container images (`**/Dockerfile,**/Dockerfile.*,**/*.dockerfile`)
- [shell-scripting.instructions.md](instructions/shell-scripting.instructions.md) — Shell scripting best practices for bash scripts (`**/*.sh`)
- [makefile.instructions.md](instructions/makefile.instructions.md) — Best practices for authoring GNU Make Makefiles (`**/Makefile,**/makefile,**/*.mk`)
- [secure-coding-owasp.instructions.md](instructions/secure-coding-owasp.instructions.md) — Comprehensive secure coding based on OWASP Top 10 (`**`)
- [context-engineering.instructions.md](instructions/context-engineering.instructions.md) — Guidelines for structuring code to maximize Copilot effectiveness (`**`)

### Prompts (`.github/prompts/`)

Reusable workflows for common development tasks:
- `deliver-epic` / `deliver-story` — End-to-end story and epic delivery via handoff workflow
- `write-epic` / `write-story` — Collaborative epic/story authoring
- `test-e2e-local` / `test-e2e-azure` — Full end-to-end validation (local and Azure)
- `pr` — Create a pull request from the current branch to main
- `merge-pr` — Merge the open PR for the current branch, switch to main, and pull