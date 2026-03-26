---
description: 'Docker best practices for building optimized, secure, and efficient container images'
applyTo: '**/Dockerfile,**/Dockerfile.*,**/*.dockerfile'
---

# Docker Best Practices

## Core Principles

- **Immutability**: Once built, images should not change. Any changes → new image.
- **Portability**: Containers should run consistently across environments without modification.
- **Isolation**: Each container runs its own process namespace with isolated resources.
- **Small Images**: Smaller images build faster, transfer faster, and have less attack surface.

## Dockerfile Standards

### Multi-Stage Builds

Always use multi-stage builds to separate build dependencies from runtime:

```dockerfile
# Stage 1: Build
FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY src/ ./src/
USER appuser
```

### Base Image Selection

- Use `python:3.12-slim` for Python services (consistent with this project)
- Avoid `latest` tag — use specific version tags for reproducibility
- Prefer slim/alpine variants over full distributions

### Layer Optimization

- Place rarely changing instructions first (dependencies before source code)
- Combine `RUN` commands to minimize layers
- Clean up in the same `RUN` command

```dockerfile
# GOOD: Copy dependency files first, then source
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY src/ ./src/
```

### .dockerignore

Maintain comprehensive `.dockerignore` to exclude:
- `.git`, `__pycache__`, `.venv`, `node_modules`
- Build artifacts, test files, documentation
- `.env` files (secrets)
- IDE files (`.vscode`, `.idea`)

### Security

- **Non-root user**: Always use `USER <non-root-user>` in production images
- **No secrets in layers**: Never `COPY` secrets into images — use runtime environment variables
- **Minimal packages**: Don't include debug tools in production images
- **HEALTHCHECK**: Define health checks for orchestration systems

```dockerfile
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
RUN chown -R appuser:appgroup /app
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD curl --fail http://localhost:8080/health || exit 1
```

### CMD and ENTRYPOINT

- Use exec form (`["command", "arg1"]`) for proper signal handling
- Use `ENTRYPOINT` for the executable, `CMD` for default arguments
- For simple cases, `CMD ["executable", "param1"]` is sufficient

### Environment Variables

- Use `ENV` for defaults, allow runtime overrides
- Never hardcode secrets — use `DefaultAzureCredential` and managed identity
- Validate required env vars at application startup

## Project-Specific Conventions

This project has 6 Dockerfiles in `src/`:
- `src/agent/Dockerfile` — KB Agent (FastAPI)
- `src/web-app/Dockerfile` — Chainlit web app
- `src/functions/fn_index/Dockerfile` — Index function
- `src/functions/fn_convert_*/Dockerfile` — Convert functions (3 analyzer backends)

All use Python 3.12-slim with `uv` for dependency management. Follow the existing patterns when creating or modifying Dockerfiles.

## Review Checklist

- [ ] Multi-stage build used
- [ ] Specific, minimal base image (python:3.12-slim)
- [ ] Layers optimized (dependencies before source)
- [ ] `.dockerignore` is comprehensive
- [ ] Non-root `USER` defined
- [ ] No secrets in image layers
- [ ] `HEALTHCHECK` instruction defined
- [ ] `CMD`/`ENTRYPOINT` uses exec form
