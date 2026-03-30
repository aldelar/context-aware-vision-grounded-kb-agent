---
name: github-actions
description: 'Design and optimize GitHub Actions workflows with security-first practices, efficient resource usage, and reliable automation. Use when creating or reviewing CI/CD workflows, action pinning, OIDC auth, and supply-chain security.'
---

# GitHub Actions

Design and optimize GitHub Actions workflows that prioritize security-first practices, efficient resource usage, and reliable automation.

## Security-First Principles

### Permissions
- Default to `contents: read` at workflow level
- Override only at job level when needed
- Grant minimal necessary permissions

### Action Pinning
- **Always pin actions to a full-length commit SHA** (e.g., `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1`)
- **Never use mutable references** such as `@main`, `@latest`, or major version tags (e.g., `@v4`)
- Add a version comment next to the SHA for human readability
- Use Dependabot or Renovate to automate SHA updates

### Secrets
- Access via environment variables only
- Never log or expose in outputs
- Use environment-specific secrets for production
- Prefer OIDC over long-lived credentials

## OIDC Authentication

Eliminate long-lived credentials:
- **Azure**: Use workload identity federation (preferred for this project)
- **AWS**: Configure IAM role with trust policy for GitHub OIDC provider
- **GCP**: Use workload identity provider
- Requires `id-token: write` permission

## Concurrency Control

- Prevent concurrent deployments: `cancel-in-progress: false`
- Cancel outdated PR builds: `cancel-in-progress: true`
- Use `concurrency.group` to control parallel execution

## Security Hardening

- **Dependency Review**: Scan for vulnerable dependencies on PRs
- **CodeQL Analysis**: SAST scanning on push, PR, and schedule
- **Container Scanning**: Scan images with Trivy or similar (relevant for this project's 6 Dockerfiles)
- **SBOM Generation**: Create software bill of materials
- **Secret Scanning**: Enable with push protection

## Caching & Optimization

- Use built-in caching when available (setup-python)
- Cache dependencies with `actions/cache` (uv cache for this project)
- Use effective cache keys (hash of lock files)
- Implement restore-keys for fallback

## Workflow Validation

- Use actionlint for workflow linting
- Validate YAML syntax
- Test in forks before enabling on main repo

## Workflow Security Checklist

- [ ] Actions pinned to full commit SHAs with version comments
- [ ] Permissions: least privilege (default `contents: read`)
- [ ] Secrets via environment variables only
- [ ] OIDC for Azure authentication (workload identity federation)
- [ ] Concurrency control configured
- [ ] Caching implemented (uv/pip cache)
- [ ] Artifact retention set appropriately
- [ ] Dependency review on PRs
- [ ] Security scanning (CodeQL, container, dependencies)
- [ ] Workflow validated with actionlint
- [ ] Environment protection for production
- [ ] No hardcoded credentials
- [ ] Third-party actions from trusted sources

## Project-Specific Notes

- This project uses `azd` for deployment — integrate with `azd -C infra/azure provision` and `azd -C infra/azure deploy`
- 6 Dockerfiles in `src/` — consider container scanning in CI
- Python 3.12+ with `uv` — use `uv sync` for dependency installation in CI
- Tests: `make dev-test` runs the current repo-wide test suite
- Multiple services: agent, web-app, fn-convert (3 analyzers), fn-index
