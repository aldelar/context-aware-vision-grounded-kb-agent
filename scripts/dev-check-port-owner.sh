#!/usr/bin/env bash

set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=lib/system.sh
source "${ROOT_DIR}/scripts/lib/system.sh"

usage() {
    echo "Usage: $0 <port> <service-label>" >&2
    exit 1
}

main() {
    [[ $# -eq 2 ]] || usage

    local port="$1"
    local label="$2"
    local pid
    local cmd

    pid="$(system_port_owner_pid "${port}")"
    if [[ -z "${pid}" ]]; then
        exit 0
    fi

    cmd="$(ps -wwp "${pid}" -o cmd= 2>/dev/null || true)"
    echo "Port ${port} required for ${label} is already in use." >&2
    if [[ -n "${cmd}" ]]; then
        echo "Conflicting process: PID ${pid} — ${cmd}" >&2
    else
        echo "Conflicting process: PID ${pid}" >&2
    fi
    echo "Stop the conflicting process or free the port, then rerun the target." >&2
    exit 1
}

main "$@"