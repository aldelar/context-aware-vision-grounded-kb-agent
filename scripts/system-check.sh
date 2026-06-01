#!/usr/bin/env bash
# scripts/system-check.sh — Print host setup category and key tool availability.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/system.sh
source "${SCRIPT_DIR}/lib/system.sh"

print_command_status() {
    local command_name="$1"
    local label="$2"

    if system_has_command "${command_name}"; then
        printf '  %-28s found (%s)\n' "${label}" "$(command -v "${command_name}")"
    else
        printf '  %-28s missing\n' "${label}"
    fi
}

print_docker_engine_status() {
    local engine_platform

    if ! system_has_command docker; then
        return
    fi

    engine_platform="$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}' 2>/dev/null || true)"
    if [[ -n "${engine_platform}" ]]; then
        printf '  %-28s %s\n' "Docker engine platform" "${engine_platform}"
    else
        printf '  %-28s unavailable\n' "Docker engine platform"
    fi
}

print_guidance() {
    case "$(system_category)" in
        macos-brew)
            echo "Install strategy: Homebrew formulas/casks where available."
            echo "GPU setup: skip dev-setup-gpu; Apple Silicon acceleration is for native Ollama, not NVIDIA Docker runtime."
            ;;
        macos-no-brew)
            echo "Install strategy: install Homebrew first, then rerun this check."
            echo "GPU setup: skip dev-setup-gpu; Apple Silicon acceleration is for native Ollama, not NVIDIA Docker runtime."
            ;;
        linux-apt)
            echo "Install strategy: apt-managed Linux distribution."
            echo "GPU setup: dev-setup-gpu is applicable only when an NVIDIA GPU is visible to the Linux Docker engine."
            ;;
        linux-pacman)
            echo "Install strategy: pacman-managed Linux distribution."
            echo "GPU setup: dev-setup-gpu is applicable only when an NVIDIA GPU is visible to the Linux Docker engine."
            ;;
        linux-other)
            echo "Install strategy: Linux package manager detected, but some project tools may require manual install guidance."
            echo "GPU setup: dev-setup-gpu is applicable only when an NVIDIA GPU is visible to the Linux Docker engine."
            ;;
        *)
            echo "Install strategy: unsupported host category."
            ;;
    esac
}

main() {
    echo "Host system"
    system_print_summary
    echo ""
    print_guidance
    echo ""
    echo "Tool availability"
    print_command_status docker "Docker CLI"
    print_command_status az "Azure CLI"
    print_command_status azd "Azure Developer CLI"
    print_command_status uv "uv"
    print_command_status func "Azure Functions Core Tools"
    print_command_status npm "npm"
    print_command_status ollama "Ollama CLI"
    print_docker_engine_status
}

main "$@"