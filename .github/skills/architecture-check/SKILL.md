---
name: architecture-check
description: 'Validates service boundary compliance in the KB Agent project. Use when working on cross-service imports, restructuring modules, or reviewing code that crosses service boundaries.'
---

# Architecture Boundary Check

Verify that the KB Agent service-based architecture is respected. Each service is an independent package — cross-service imports break the isolation contract.

## Service Boundaries

```
┌─────────────────────────────────────────────────┐
│  src/agent/          (KB Agent)                  │
│  - Starlette + Microsoft Agent Framework         │
│  - Hosted on Foundry / Container App             │
│  - Own pyproject.toml + .env                     │
├─────────────────────────────────────────────────┤
│  src/functions/      (Pipeline Functions)         │
│  - fn_convert_cu/    (Content Understanding)      │
│  - fn_convert_mistral/ (Mistral Document AI)      │
│  - fn_convert_markitdown/ (MarkItDown)            │
│  - fn_index/         (Markdown → AI Search)       │
│  - shared/           (cross-function utilities)   │
│  - Own pyproject.toml + .env                     │
├─────────────────────────────────────────────────┤
│  src/web-app/        (Chainlit Client)            │
│  - OpenAI SDK thin client                        │
│  - Cosmos DB data layer                          │
│  - Own pyproject.toml + .env                     │
├─────────────────────────────────────────────────┤
│  infra/              (Azure + local runtime)      │
│  - azure/infra/      (Bicep IaC)                  │
│  - docker/           (Docker Compose)             │
│  - No application code                           │
└─────────────────────────────────────────────────┘
```

## Forbidden Import Patterns

Check these **must-never-happen** patterns:

1. **Agent importing from functions or web-app:**
   ```python
   # FORBIDDEN in src/agent/**/*.py
   from shared import ...
   from fn_convert_cu import ...
   from app import ...  # web-app
   ```

2. **Functions importing from agent or web-app:**
   ```python
   # FORBIDDEN in src/functions/**/*.py
   from agent import ...
   from app import ...  # web-app
   ```

3. **Web-app importing from agent or functions:**
   ```python
   # FORBIDDEN in src/web-app/**/*.py
   from agent import ...
   from shared import ...
   from fn_index import ...
   ```

4. **Shared utilities used outside functions:**
   ```python
   # FORBIDDEN in src/agent/**/*.py or src/web-app/**/*.py
   from shared import ...  # shared/ is for functions only
   ```

## Config Patterns

All services must follow these configuration rules:

- [ ] Azure service endpoints come from environment variables
- [ ] `DefaultAzureCredential` for all Azure SDK clients
- [ ] `.env` files populated by `azd -C infra/azure env get-values` — never hardcoded
- [ ] Config modules evaluate at import time (`config.py` per service)
- [ ] Test `conftest.py` sets `os.environ.setdefault(...)` for config safety

## How to Check

1. Search for imports in `src/agent/` — should not reference `shared`, `fn_*`, or `app`
2. Search for imports in `src/functions/` — should not reference `agent` or `app`
3. Search for imports in `src/web-app/` — should not reference `agent`, `shared`, or `fn_*`
4. Verify each service has its own `pyproject.toml` with independent dependencies
5. Check that `infra/azure/infra/` contains only Bicep files and parameters — no Python

## Reference

- [Architecture spec](docs/specs/architecture.md)
- [Infrastructure spec](docs/specs/infrastructure.md)
