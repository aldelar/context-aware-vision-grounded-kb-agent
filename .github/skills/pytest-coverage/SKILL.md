---
name: pytest-coverage
description: |
  Run pytest tests with coverage, discover lines missing coverage, and increase
  coverage to 100%. Use when:
  - Measuring test coverage for a module
  - Finding untested code paths
  - Improving coverage for a specific service
---

# Pytest Coverage Analysis

The goal is for tests to cover all lines of code.

## Workflow

### 1. Generate Coverage Report

```bash
pytest --cov --cov-report=annotate:cov_annotate
```

For a specific module:

```bash
pytest --cov=your_module_name --cov-report=annotate:cov_annotate
```

For specific tests:

```bash
pytest tests/test_your_module.py --cov=your_module_name --cov-report=annotate:cov_annotate
```

### 2. Review Annotated Files

Open the `cov_annotate` directory. There will be one file per source file.

- Files with 100% coverage → skip
- Files with <100% coverage → open and review

### 3. Find Uncovered Lines

Lines starting with `!` (exclamation mark) are **not covered by tests**. Add tests to cover these lines.

### 4. Iterate

Keep running the tests and improving coverage until all lines are covered.

## Project Context

This project has three services with independent test suites:

| Service | Test Command | Source |
|---------|-------------|--------|
| Agent | `cd src/agent && pytest` | `src/agent/` |
| Functions | `cd src/functions && pytest` | `src/functions/` |
| Web App | `cd src/web-app && pytest` | `src/web-app/` |

Run all: `make dev-test`

Example for agent coverage:
```bash
cd src/agent
pytest --cov=agent --cov-report=annotate:cov_annotate tests/
```
