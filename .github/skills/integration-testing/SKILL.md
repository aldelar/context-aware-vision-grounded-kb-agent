---
name: integration-testing
description: 'Guide for writing integration tests against local Docker-backed Azure emulators and real Azure services. Use when writing or reviewing tests marked @pytest.mark.integration.'
---

# Integration Testing

Write and review integration tests that exercise real Azure-backed infrastructure — locally via Docker emulators, or against deployed Azure resources.

## When to Use This Skill

- Writing new integration tests for the agent, convert/index functions, or web app data layer
- Reviewing existing integration tests for correctness
- Diagnosing an integration test that fails because of missing infrastructure

## Key Principles

1. **Real infrastructure, not mocks** — integration tests run against the local emulators (Azurite for Blob, the Cosmos DB emulator, the AI Search simulator) brought up by `make dev-infra-up`, or against deployed Azure services.
2. **Marked and excluded by default** — every integration test carries `@pytest.mark.integration`. The agent service excludes them by default via `addopts = "-m 'not integration'"`; `make dev-test` overrides that to run the full suite once infra is up.
3. **Managed identity, not keys** — use `DefaultAzureCredential` for Azure service access, exactly as production code does. Never hardcode keys or connection strings in a test.
4. **Restore infra, don't weaken the test** — if an integration test fails because an emulator, container, seeded KB, env var, or RBAC assignment is missing, restore that dependency (via the Makefile / Docker Compose / AZD), per the project's **No implicit degraded mode** policy. Never make the test pass by mocking the thing it is meant to integrate with.

## Writing an Integration Test

### 1. Mark it
```python
import pytest

@pytest.mark.integration
async def test_search_returns_grounded_results() -> None:
    ...
```

### 2. Read config from the environment
Integration tests need the same environment variables the service reads at runtime — `SEARCH_ENDPOINT`, `COSMOS_ENDPOINT`, `SERVING_BLOB_ENDPOINT`, `AGENT_ENDPOINT`, etc. These are populated by `azd -C infra/azure env get-values` (deployed) or by the dev `.env` for the emulators. Per `testing.instructions.md`, each service's `conftest.py` sets sensible defaults for import-time config.

### 3. Use `DefaultAzureCredential`
```python
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient

credential = DefaultAzureCredential()
client = SearchClient(endpoint=search_endpoint, index_name=index_name, credential=credential)
```

### 4. Seed and clean up deterministically
- Seed the local KB with `make dev-seed-kb` (syncs `kb/staging` into Azurite) before tests that read serving content.
- For data your test writes, clean it up at the end of the test (or use a uniquely-prefixed id you can delete) — the emulators are shared across a run.

## Running Integration Tests

```bash
make dev-infra-up      # start emulators (Azurite, Cosmos, AI Search simulator)
make dev-test          # runs all per-service suites including integration

# or a single service, integration-only:
cd src/agent && uv run pytest tests -o addopts= -m "integration and not uitest"
cd src/functions && uv run pytest tests -o addopts= -m "integration and not uitest"
cd src/web-app && uv run pytest tests -o addopts= -m "integration and not uitest"
```

## Anti-Patterns Checklist

When reviewing integration tests, flag these:

- [ ] No `@pytest.mark.integration` marker → **add it** (otherwise it runs in the unit tier and fails in CI)
- [ ] `MagicMock()` / `AsyncMock()` standing in for the Azure client under test → **use the real client against the emulator**
- [ ] Hardcoded endpoint, key, or connection string → **read from env; use `DefaultAzureCredential`**
- [ ] Test depends on data left behind by another test → **seed its own data, clean up after**
- [ ] Test silently passes when the emulator is down → **it must fail loudly; don't catch-and-skip required infra**

## Reference

- Testing conventions: [testing.instructions.md](../../instructions/testing.instructions.md)
- Local infra targets: [Makefile](../../../Makefile) (`make dev-infra-up`, `make dev-seed-kb`, `make dev-test`)
- Architecture: [docs/specs/architecture.md](../../../docs/specs/architecture.md)
