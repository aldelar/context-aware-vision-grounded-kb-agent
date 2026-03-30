---
name: 'Python Standards'
description: 'Python 3.12+, uv, Azure SDK, and code style conventions for all backend services'
applyTo: "src/**/*.py"
---

# Python Standards

## Runtime & Tooling

- Python 3.12+ required
- **uv** for dependency management — never use `pip install` directly
- **hatchling** build backend for all packages
- Each service is an independent package with its own `pyproject.toml`:
  - `src/agent/` — KB Agent (FastAPI + Agent Framework)
  - `src/functions/` — Azure Functions (convert + index pipeline)
  - `src/web-app/` — Chainlit thin client
- Spike code lives under `src/spikes/` — each spike has its own `pyproject.toml`

## Dependencies

- Add new dependencies to the correct service's `pyproject.toml`
- Dev dependencies go under `[project.optional-dependencies] dev = [...]`
- After modifying dependencies: `cd src/<service> && uv sync --extra dev`
- Use `uv run` to execute commands within the service's virtual environment

## Azure SDK Patterns

- **Always** use `DefaultAzureCredential` — never hardcode keys or connection strings
- Use `get_bearer_token_provider()` for OpenAI-style token auth
- Async clients where available (especially for blob, search, cosmos)
- All Azure service endpoints come from environment variables (populated by `azd -C infra/azure env get-values`)

## Code Style

- Use `from __future__ import annotations` for modern type hints
- Standard library `logging` module — no print statements in production code
- Dataclasses for structured data; avoid raw dicts for domain objects
- Prefer `pathlib.Path` over `os.path`
- Imports: stdlib → third-party → local, separated by blank lines
- Use `noqa` comments only with specific codes (e.g., `# noqa: E402`)

## Error Handling

- Validate at system boundaries only (HTTP handlers, function triggers, CLI entry points)
- Trust internal code and framework guarantees — don't defensively catch everything
- Use specific exception types, never bare `except:`
- Log errors with structured context: `logger.error("msg", exc_info=True, extra={...})`

## Environment Variables

- Load via `python-dotenv` in local dev (`.env` files per service)
- Config modules (e.g., `agent/config.py`, `shared/config.py`) evaluate at import time
- Test conftest.py sets `os.environ.setdefault(...)` before imports to avoid config failures
