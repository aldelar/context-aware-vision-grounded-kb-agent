# ---------------------------------------------------------------------------
# Dockerfile — MCP Web Search Server (Azure Container App)
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Install uv for fast, deterministic dependency resolution.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies from pyproject.toml + uv.lock (frozen, no editable install)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . .

EXPOSE 8089

# Put the venv on PATH so `python` finds the installed packages
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "mcp_web_search"]
