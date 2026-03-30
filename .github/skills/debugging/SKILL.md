---
name: debugging
description: 'Structured first-pass debugging for test failures, runtime errors, and unexpected behavior. USE FOR: test failure, assertion error, ImportError, traceback, debug failing test, fix broken test, diagnose error, runtime exception, mock error, config error. DO NOT USE FOR: complex multi-system design issues (escalate to @planner for re-planning).'
---

# Debugging

Structured approach for diagnosing and fixing failures during implementation or testing. Use this skill when you encounter a test failure, runtime error, or unexpected behavior — diagnose and fix in-context before escalating.

## First-Pass Debugging Workflow

When a test fails or an error occurs, follow these steps **before** giving up or asking for help:

### 1. Read the Error

- Parse the full traceback — identify the exact file, line, and assertion that failed
- Distinguish between: test bug, code bug, import error, or environment issue

### 2. Trace the Execution Path

- Read the failing test and the code under test
- Follow the call chain from the error back to the root cause
- Check recent changes — did something you just modified cause this?

### 3. Check Common Causes

| Symptom | Likely Cause | Fix |
|---|---|---|
| `ImportError` / `ModuleNotFoundError` | Wrong import path, missing dependency | Fix import or add to `pyproject.toml` + `uv sync` |
| `AttributeError` on mock | Mock not configured for the called method | Add `return_value` or `side_effect` to mock |
| `KeyError` in config | Missing env var | Check `conftest.py` `os.environ.setdefault` calls |
| Assertion mismatch | Code changed but test expectations didn't update | Update test expectation or fix the code |
| `TypeError` on function call | Wrong argument count or types after refactor | Check function signature matches all callers |
| `DefaultAzureCredential` failure | Missing `az login` or wrong subscription | Run `az account show`, `az login` |
| 403 from Azure service | Missing RBAC role assignment | Check `infra/azure/infra/main.bicep` role assignments |
| Container fails to start | Dockerfile issue or missing env var | Check Container App logs with Azure CLI (`az containerapp logs show`) or the portal |

### 4. Apply the Minimal Fix

- Fix exactly one thing at a time — don't shotgun-fix multiple changes hoping one works
- If it's a test bug: fix the test (wrong mock, wrong assertion, missing setup)
- If it's a code bug: fix the code, then re-run the test
- If it's an environment issue: fix the config/env, document what was missing

### 5. Validate

- Re-run the failing test (not just the full suite — target the specific test first)
- Then run `make dev-test` to confirm no regressions
- If the fix introduces new failures, repeat from Step 1

## When to Escalate

If you cannot resolve the issue after **one full debugging pass** (Steps 1–5), report what you found and escalate to @planner for re-planning. Include:
- The error traceback
- What you investigated
- Your hypothesis for the root cause
- What you tried and why it didn't work

## Anti-Patterns

- **Don't shotgun-fix** — changing multiple things hoping one works is not debugging
- **Don't skip reproduction** — confirm the error exists and is deterministic before fixing
- **Don't add broad try/except** — suppressing errors hides bugs
- **Don't disable tests** — fix the test or the code, never `@pytest.mark.skip` to make the suite green
- **Don't refactor while debugging** — fix the bug, nothing more
