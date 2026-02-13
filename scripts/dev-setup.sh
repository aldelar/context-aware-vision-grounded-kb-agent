#!/usr/bin/env bash
# scripts/dev-setup.sh — Install development prerequisites
# Run via: make dev-setup
set -euo pipefail

echo "Installing development prerequisites..."
echo ""

# ---------------------------------------------------------------------------
# Azure CLI
# ---------------------------------------------------------------------------
if command -v az &>/dev/null; then
    echo "  az          already installed ($(az --version 2>&1 | head -1))"
else
    echo "  az          installing..."
    curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
fi

# ---------------------------------------------------------------------------
# Azure Developer CLI (azd)
# ---------------------------------------------------------------------------
if command -v azd &>/dev/null; then
    echo "  azd         already installed ($(azd version 2>&1 | head -1))"
else
    echo "  azd         installing..."
    curl -fsSL https://aka.ms/install-azd.sh | bash
fi

# ---------------------------------------------------------------------------
# UV (Python package manager)
# ---------------------------------------------------------------------------
if command -v uv &>/dev/null; then
    echo "  uv          already installed ($(uv --version 2>&1 | head -1))"
else
    echo "  uv          installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# ---------------------------------------------------------------------------
# Azure Functions Core Tools
# ---------------------------------------------------------------------------
if command -v func &>/dev/null; then
    echo "  func        already installed ($(func --version 2>&1 | head -1))"
else
    echo "  func        installing..."
    npm install -g azure-functions-core-tools@4 --unsafe-perm true
fi

echo ""
echo "Done. Run 'make dev-doctor' to verify."
