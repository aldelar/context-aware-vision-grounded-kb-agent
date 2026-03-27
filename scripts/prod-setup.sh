#!/usr/bin/env bash
# scripts/prod-setup.sh — Install user-scoped Azure deployment prerequisites.
# Run via: make prod-setup

set -euo pipefail

ensure_non_root() {
    if [[ ${EUID} -eq 0 || -n "${SUDO_USER:-}" ]]; then
        echo "Run 'make prod-setup' as your normal user." >&2
        exit 1
    fi
}

has_command() {
    command -v "$1" >/dev/null 2>&1
}

install_azure_cli() {
    if has_command az; then
        echo "  az          already installed ($(az --version 2>&1 | head -1))"
        return
    fi

    echo "  az          installing..."
    curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
}

install_azd() {
    if has_command azd; then
        echo "  azd         already installed ($(azd version 2>&1 | head -1))"
        return
    fi

    echo "  azd         installing..."
    curl -fsSL https://aka.ms/install-azd.sh | bash
}

main() {
    ensure_non_root

    echo "Installing Azure deployment prerequisites..."
    echo ""

    install_azure_cli
    install_azd

    echo ""
    echo "Done. Next: run make set-project name=<id> and then your prod-* target."
}

main "$@"