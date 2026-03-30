---
name: 'Testing Standards'
description: 'pytest conventions, three-tier test strategy, and service-specific test patterns'
applyTo: "**/tests/**"
---

# Testing Standards

## Framework

- **pytest** for all tests
- Each service has its own `tests/` directory with `conftest.py`
- Run the current repo test suite: `make dev-test`

## Three-Tier Test Strategy

### Unit Tests (default — no Azure credentials needed)

Run with direct service-local pytest commands, for example:

- `cd src/agent && uv run pytest tests -o addopts= -m "not integration and not uitest"`
- `cd src/functions && uv run pytest tests -o addopts= -m "not integration and not uitest"`
- `cd src/web-app && uv run pytest tests -o addopts= -m "not integration and not uitest"`

- Mock all external services (Azure SDK clients, HTTP calls)
- Fast, deterministic, run on every change
- conftest.py sets `os.environ.setdefault(...)` for config modules that load at import time
- Tests that pass `test $$? -eq 5` on exit code 5 means "no tests collected" is OK (not a failure)

### Endpoint Tests (no Azure credentials needed)

- Use `httpx` async test client for FastAPI endpoints
- Test request/response contracts, status codes, headers
- Mock the agent/service layer, test the HTTP layer
- Located alongside unit tests (same `tests/` directory)

### Integration Tests (require running services + Azure credentials)

Run with `make dev-test` once the appropriate environment is configured, or use direct pytest filters such as:

- `cd src/agent && uv run pytest tests -o addopts= -m "integration and not uitest"`
- `cd src/web-app && uv run pytest tests -o addopts= -m "integration and not uitest"`
- `cd src/functions && uv run pytest tests -o addopts= -m "integration and not uitest"`

- Marked with `@pytest.mark.integration`
- Excluded by default via `addopts = "-m 'not integration'"` in `pyproject.toml`
- Require environment variables: `AGENT_ENDPOINT`, `COSMOS_ENDPOINT`, `SERVING_BLOB_ENDPOINT`, etc.
- Test against real deployed Azure services

## Test Conventions

- File naming: `test_{module_name}.py`
- Use existing `conftest.py` fixtures — extend them, don't duplicate
- Test functions: `test_{behavior_being_tested}` or `test_{method}_{scenario}_{expected}`
- Use `pytest.fixture` for shared setup, keep tests independent
- Use `pytest.mark.parametrize` for data-driven tests

## Service-Specific Notes

### Agent (`src/agent/tests/`)
- conftest.py sets: `AI_SERVICES_ENDPOINT`, `SEARCH_ENDPOINT`, `SERVING_BLOB_ENDPOINT`, `PROJECT_ENDPOINT`
- Integration tests use `AGENT_ENDPOINT` env var for the deployed agent URL

### Functions (`src/functions/tests/`)
- Fixtures provide `project_root`, `staging_path`, `serving_path`, `sample_article_ids`
- Subdirectories: `test_convert/`, `test_convert_mistral/`, `test_index/`

### Web App (`src/web-app/tests/`)
- conftest.py sets: `AGENT_ENDPOINT`, `SERVING_BLOB_ENDPOINT`
- Integration tests need `COSMOS_ENDPOINT`, `COSMOS_DATABASE_NAME`

## Writing New Tests

1. Read the code under test and its existing tests first
2. Identify untested paths: happy path, edge cases, error boundaries
3. Write the test, run it, confirm it passes
4. Run the full suite (`make dev-test`) to check for regressions
