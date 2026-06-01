#!/usr/bin/env bash
# scripts/prod-setup.sh — Install user-scoped Azure deployment prerequisites.
# Run via: make prod-setup

set -euo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=lib/system.sh
source "${REPO_ROOT}/scripts/lib/system.sh"

ensure_non_root() {
    if [[ ${EUID} -eq 0 || -n "${SUDO_USER:-}" ]]; then
        echo "Run 'make prod-setup' as your normal user." >&2
        exit 1
    fi
}

install_azure_cli() {
    system_install_tool az azure-cli "az" "az --version" "make prod-setup"
}

install_azd() {
    system_install_tool azd azd "azd" "azd version" "make prod-setup"
}

main() {
    ensure_non_root

    echo "Installing Azure deployment prerequisites..."
    echo ""

    install_azure_cli
    install_azd

    echo ""
    echo "Done."
}

main "$@"