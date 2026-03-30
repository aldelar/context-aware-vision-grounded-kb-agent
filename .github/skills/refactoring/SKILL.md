---
name: refactoring
description: 'Guides safe refactoring operations across the KB Agent service-based architecture. Use when restructuring code, extracting modules, or moving files across services.'
---

# Safe Refactoring

## Pre-Refactoring Checklist

1. Run `make dev-test` — establish green baseline. Do not start refactoring with failing tests.
2. Identify all callers/importers of the code being moved (use grep/search)
3. Plan the move: old path → new path, old imports → new imports
4. Determine if this is a within-service or cross-service refactor

## Within-Service Refactoring

Moving code within the same service (e.g., within `src/agent/`):

1. Create new file at destination
2. Move code (don't copy — move)
3. Update ALL imports within the service
4. Run the affected service's tests directly from that service directory with `uv run pytest`
5. Delete old file only after all imports are updated and tests pass

## Cross-Service Refactoring

Moving code between services (e.g., `src/functions/` → `src/agent/`) is a **significant change**:

1. **Question whether it's the right move** — services are intentionally isolated
2. If code is needed by multiple services, consider:
   - Is it truly shared? Should it be duplicated instead of shared?
   - Can it be a utility that each service vendors independently?
3. Update `pyproject.toml` for both services if dependencies change
4. Run `uv sync --extra dev` in both service directories
5. Run the repo-wide test suite with `make dev-test` (not just the affected service)

## Import Update Patterns

When renaming or moving a module:
1. Search for all import variations:
   - `from old.path import Symbol`
   - `from old import path`
   - `import old.path`
2. Update test imports — tests often import directly from deep paths
3. Check config modules — they may reference the moved code at import time
4. Check `conftest.py` files — fixtures may reference the moved code

## Service-Specific Paths

| Service | Source | Tests | Config |
|---------|--------|-------|--------|
| Agent | `src/agent/agent/` | `src/agent/tests/` | `src/agent/agent/config.py` |
| Functions | `src/functions/` | `src/functions/tests/` | `src/functions/shared/config.py` |
| Web App | `src/web-app/app/` | `src/web-app/tests/` | `src/web-app/app/config.py` |

## Common Pitfalls

- **Circular imports**: check that the destination doesn't already import the source
- **Test imports**: tests often import from deep paths — search test files too
- **Config at import time**: config modules evaluate environment variables at import — moving code can change import order
- **conftest.py env setup**: test conftest files set `os.environ.setdefault` — if your code moves to a different service, ensure the new service's conftest covers the needed env vars

## Verification

After refactoring is complete:
```bash
make dev-test    # current repo-wide test suite — catches broken imports and runtime breakage
```

Must pass before the refactoring is considered done.
