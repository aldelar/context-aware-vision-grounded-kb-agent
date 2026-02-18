# ==============================================================================
# Dockerfile — Vision-Grounded Knowledge Agent (Chainlit + Agent Framework)
# ==============================================================================
# Uses UV for fast, reproducible dependency installation.
# ==============================================================================

FROM python:3.11-slim

# Install UV (official installer)
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy only pyproject.toml for dependency layer caching
COPY pyproject.toml ./

# Install production dependencies only (project installed after code copy)
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY app/ ./app/
COPY public/ ./public/
COPY .chainlit/ ./.chainlit/
COPY chainlit.md ./chainlit.md

# Install the project itself so the 'app' package is importable
RUN uv sync --no-dev

# Ensure the venv is on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Chainlit listens on 8080
EXPOSE 8080

# Run Chainlit in production mode (no --watch)
CMD ["chainlit", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8080"]
