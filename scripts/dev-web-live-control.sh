#!/usr/bin/env bash

set -euo pipefail

readonly COMMAND="${1:-status}"
readonly PORT="${2:-3001}"
readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=lib/system.sh
source "${ROOT_DIR}/scripts/lib/system.sh"

describe_pid() {
    local pid="$1"

    ps -wwp "${pid}" -o cmd= 2>/dev/null || true
}

describe_tty() {
    local pid="$1"

    ps -wwp "${pid}" -o tty= 2>/dev/null | awk '{$1=$1; print}'
}

is_next_dev_server() {
    local cmd="$1"

    [[ "${cmd}" == *"next-server"* || "${cmd}" == *"next dev"* ]]
}

print_server_details() {
    local pid="$1"
    local cmd tty

    cmd="$(describe_pid "${pid}")"
    tty="$(describe_tty "${pid}")"

    echo "Next.js hot-reload server is running on http://localhost:${PORT}"
    echo "PID: ${pid}"
    if [[ -n "${tty}" && "${tty}" != "?" ]]; then
        echo "Terminal: ${tty}"
    fi
    if [[ -n "${cmd}" ]]; then
        echo "Command: ${cmd}"
    fi
}

status() {
    local pid cmd

    pid="$(system_port_owner_pid "${PORT}")"
    if [[ -z "${pid}" ]]; then
        echo "No Next.js hot-reload server is running on http://localhost:${PORT}"
        return 0
    fi

    cmd="$(describe_pid "${pid}")"
    if ! is_next_dev_server "${cmd}"; then
        echo "Port ${PORT} is occupied by a different process." >&2
        echo "PID: ${pid}" >&2
        if [[ -n "${cmd}" ]]; then
            echo "Command: ${cmd}" >&2
        fi
        return 1
    fi

    print_server_details "${pid}"
}

stop() {
    local pid cmd

    pid="$(system_port_owner_pid "${PORT}")"
    if [[ -z "${pid}" ]]; then
        echo "No Next.js hot-reload server is running on http://localhost:${PORT}"
        return 0
    fi

    cmd="$(describe_pid "${pid}")"
    if ! is_next_dev_server "${cmd}"; then
        echo "Port ${PORT} is occupied by a different process; refusing to stop it." >&2
        echo "PID: ${pid}" >&2
        if [[ -n "${cmd}" ]]; then
            echo "Command: ${cmd}" >&2
        fi
        return 1
    fi

    print_server_details "${pid}"
    kill -INT "${pid}"

    for _ in 1 2 3 4 5 6 7 8 9 10; do
        if ! kill -0 "${pid}" 2>/dev/null; then
            echo "Stopped Next.js hot-reload server on http://localhost:${PORT}"
            return 0
        fi
        sleep 0.2
    done

    echo "Process ${pid} did not exit after SIGINT." >&2
    return 1
}

case "${COMMAND}" in
    status)
        status
        ;;
    stop)
        stop
        ;;
    *)
        echo "Usage: $(basename "$0") <status|stop> [port]" >&2
        exit 1
        ;;
esac