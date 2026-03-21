# ---------------------------------------------------------------------------
# Dockerfile — KB Agent (Azure Container App)
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Install uv for fast, deterministic dependency resolution.
# uv respects [tool.uv] override-dependencies in pyproject.toml,
# so the same resolution works locally and in Docker.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies from pyproject.toml + uv.lock (frozen, no editable install)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . .

EXPOSE 8088

# Put the venv on PATH so `python` finds the installed packages
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "main.py"]
