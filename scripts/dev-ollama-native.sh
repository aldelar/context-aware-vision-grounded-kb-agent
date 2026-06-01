#!/usr/bin/env bash
# scripts/dev-ollama-native.sh — Manage native Ollama for macOS local development.

set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly LOG_FILE="${ROOT_DIR}/.tmp/logs/ollama-native.log"
readonly OLLAMA_HOST_URL="${OLLAMA_HOST_URL:-http://localhost:11434}"

# shellcheck source=lib/system.sh
source "${ROOT_DIR}/scripts/lib/system.sh"

usage() {
    echo "Usage: $0 {start|stop|status}" >&2
    exit 1
}

ollama_server_ready() {
    curl -fsS "${OLLAMA_HOST_URL}/api/version" >/dev/null 2>&1
}

ensure_native_ollama_available() {
    if ! system_is_macos; then
        echo "Native Ollama target is intended for macOS. Use the default Docker Ollama path on Linux." >&2
        exit 1
    fi

    if ! system_has_command ollama; then
        system_install_tool ollama ollama "ollama" "ollama --version" "make dev-ollama-native-up"
    fi
}

wait_for_ollama() {
    local attempts=${1:-30}

    for ((i=1; i<=attempts; i++)); do
        if ollama_server_ready; then
            return 0
        fi
        sleep 1
    done

    echo "Native Ollama did not become ready on ${OLLAMA_HOST_URL}." >&2
    echo "Check ${LOG_FILE} or run 'ollama serve' in another terminal." >&2
    exit 1
}

start_brew_service() {
    if ! system_has_command brew || ! brew list --versions ollama >/dev/null 2>&1; then
        return 1
    fi

    brew services start ollama >/dev/null
}

start_background_server() {
    mkdir -p "$(dirname "${LOG_FILE}")"
    nohup ollama serve > "${LOG_FILE}" 2>&1 &
}

start_native_ollama() {
    ensure_native_ollama_available

    if ollama_server_ready; then
        echo "Native Ollama is already running on ${OLLAMA_HOST_URL}."
        ollama ps || true
        return
    fi

    if start_brew_service; then
        wait_for_ollama 45
    else
        start_background_server
        wait_for_ollama 30
    fi

    echo "Native Ollama is running on ${OLLAMA_HOST_URL}."
    ollama ps || true
}

stop_native_ollama() {
    if system_has_command brew && brew list --versions ollama >/dev/null 2>&1; then
        brew services stop ollama >/dev/null || true
        echo "Requested Homebrew service stop for native Ollama."
        return
    fi

    echo "No Homebrew-managed Ollama service found. Stop any manual 'ollama serve' process yourself."
}

print_native_ollama_status() {
    if ! system_has_command ollama; then
        echo "Ollama CLI is not installed. Run 'make dev-ollama-native-up' on macOS."
        exit 1
    fi

    if ! ollama_server_ready; then
        echo "Ollama is not responding on ${OLLAMA_HOST_URL}."
        exit 1
    fi

    ollama --version
    ollama ps
}

main() {
    [[ $# -eq 1 ]] || usage

    case "$1" in
        start)
            start_native_ollama
            ;;
        stop)
            stop_native_ollama
            ;;
        status)
            print_native_ollama_status
            ;;
        *)
            usage
            ;;
    esac
}

main "$@"