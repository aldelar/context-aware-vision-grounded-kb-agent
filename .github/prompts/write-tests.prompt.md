---
description: "Generate tests for a module — identify gaps and write comprehensive tests."
mode: "agent"
agent: "tester"
---

# Write Tests

Generate tests for a specific module or function.

## Variables

- `module` — path to the module to test (e.g., `src/agent/agent/search_tool.py`)

## Steps

1. Read the module at `${module}` — understand its public API and dependencies
2. Read existing tests for this module (check `tests/` in the same service)
3. Read `conftest.py` for available fixtures
4. Identify test gaps:
   - Happy path scenarios
   - Edge cases (empty inputs, None, boundary values)
   - Error paths (invalid inputs, service failures)
   - Async behavior (if applicable)
5. Write tests following project conventions:
   - File: `test_{module_name}.py` in the service's `tests/` directory
   - Use existing fixtures from `conftest.py`
   - Mock external services for unit tests
   - Mark integration tests with `@pytest.mark.integration`
6. Run the tests and confirm they pass
7. Report what was tested and any coverage notes
