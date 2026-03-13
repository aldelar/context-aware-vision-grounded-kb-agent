# Copilot Instructions

## Project

**Context Aware & Vision Grounded KB Agent** — an Azure-hosted two-stage pipeline that transforms HTML knowledge base articles into an AI-searchable index with image support, fronted by a conversational agent.

- **Stack:** Python 3.11+, Azure (Bicep + AZD), pytest, uv
- **Architecture:** See `docs/specs/architecture.md`
- **Infrastructure:** See `docs/specs/infrastructure.md`
- **Setup & Automation:** See `docs/setup-and-makefile.md` or run `make help`

## Solution Structure

- `src/agent/` — Foundry hosted KB Agent (FastAPI + Agent Framework)
- `src/functions/` — Azure Functions: `fn-convert` (HTML→Markdown) + `fn-index` (Markdown→AI Search)
- `src/web-app/` — Chainlit thin client (OpenAI SDK + Cosmos DB data layer)
- `infra/` — Bicep modules for all Azure resources
- `docs/epics/` — Epic and story tracking (source of truth for work status)
- `scripts/` — Automation and setup scripts

## Key Conventions

- **Infrastructure as Code only** — no manual Azure portal changes
- **Managed identity everywhere** — no keys or secrets in code or config
- **Environment-driven config** — `.env` files from `azd env get-values`, never hardcoded
- **uv** for Python dependency management — each service has its own `pyproject.toml`
- **Tests before commit** — run `make test` to validate all services
- **Docs match code** — epic docs must always reflect the actual implementation state

## Agent-Driven Development

This repo uses specialized agents, instructions, and prompts for structured development:

- **Agents** (`.github/agents/`): @planner, @coder, @reviewer, @tester, @deployer, @debugger
- **Instructions** (`.github/instructions/`): Composable rules for Python, Azure infra, testing, epics, and security
- **Prompts** (`.github/prompts/`): Reusable workflows for story planning, implementation, testing, review, and deployment

See individual agent files for their roles and usage.