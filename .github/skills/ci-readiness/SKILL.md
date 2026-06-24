---
name: ci-readiness
description: 'Validates that code changes are CI-ready. Checks for hardcoded values, proper test markers, managed-identity usage, environment-driven config, and GitHub Actions compatibility. Use before submitting a PR or after major changes.'
---

# CI Readiness Check

Verify that changes will pass the GitHub Actions CI pipeline defined in [.github/workflows/ci.yml](../../workflows/ci.yml).

For local verification, prefer the Makefile targets over replaying CI commands directly. `make dev-test` runs the same per-service suites CI runs, against the local Docker-backed emulators when they are up.

## CI Pipeline Overview

CI runs **per-service jobs** on every PR to `main`. It exercises the **unit tier only** (`-m "not integration and not uitest"`) because integration tests require Azure-backed emulators or real Azure services that CI does not provision.

| Job | Command | What it checks |
|-----|---------|----------------|
| `functions-tests` | `cd src/functions && uv run pytest tests -o addopts= -m "not integration and not uitest"` | Convert + index function logic (fn_convert_*, fn_index, shared) |
| `agent-tests` | `cd src/agent && uv run pytest tests -o addopts= -m "not integration and not uitest"` | KB Agent logic and HTTP endpoints |
| `web-app-tests` | `cd src/web-app && npm ci && npm test` | Next.js + CopilotKit web app |
| `bicep-validate` | `az bicep build --file infra/azure/infra/main.bicep` | Infrastructure compiles |

## Pre-submission Checklist

### Python services (agent, functions, mcp-web-search)
- [ ] `make dev-test` passes locally (or the relevant per-service `uv run pytest`)
- [ ] No hardcoded URLs, endpoints, or ports — read config from environment variables (populated by `azd -C infra/azure env get-values`)
- [ ] No hardcoded file paths — use `pathlib` and repo-relative or env-driven paths
- [ ] `DefaultAzureCredential` for all Azure service access — no keys, connection strings, or secrets in source
- [ ] New environment variables documented in the service's `.env.sample` (if present) and in `docs/specs/`
- [ ] New runtime dependencies added to the correct service `pyproject.toml`, then `uv sync --extra dev` (never `pip install` ad-hoc)

### Test compatibility
- [ ] Unit tests run with no Azure credentials and no live services — mock Azure SDK clients
- [ ] Integration tests carry `@pytest.mark.integration` so CI's unit tier excludes them
- [ ] Browser tests carry the `uitest` marker so they are excluded from `make dev-test`/CI unit runs
- [ ] No test depends on execution order — each test is independent
- [ ] Tests don't assume a service is reachable on a fixed host/port — CI has no emulators
- [ ] A unit test that needs real I/O is a defect: fix the test or the code, don't loosen the gate

### Web app (`src/web-app`)
- [ ] `npm test` passes
- [ ] New npm packages added to `src/web-app/package.json`, not installed ad-hoc
- [ ] Dependency rules in `web-app.instructions.md` respected

### Infrastructure (`infra/azure`)
- [ ] `az bicep build --file infra/azure/infra/main.bicep` succeeds
- [ ] New resources wired in `main.bicep` with RBAC role assignments (managed identity, no keys)
- [ ] `docs/specs/infrastructure.md` updated to reflect the change

### Quick validation
Run before pushing:
```bash
make dev-test                                  # all per-service suites (emulators up)
az bicep build --file infra/azure/infra/main.bicep   # infra compiles
```

For epics that touch the browser UI, also validate:
```bash
make dev-test-ui    # requires the web app dev server
```

## Reference

- CI workflow: [.github/workflows/ci.yml](../../workflows/ci.yml)
- Makefile targets: [Makefile](../../../Makefile) (`make help`)
- Testing conventions: [testing.instructions.md](../../instructions/testing.instructions.md)
