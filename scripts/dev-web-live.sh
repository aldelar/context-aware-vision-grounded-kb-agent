#!/usr/bin/env bash

set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ENV_FILE="${ROOT_DIR}/.env.dev"
readonly AZURITE_ACCOUNT_KEY="Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="

# shellcheck source=lib/system.sh
source "${ROOT_DIR}/scripts/lib/system.sh"

port="${1:-3001}"
log_file="${2:-${ROOT_DIR}/.tmp/logs/dev-ui-live.log}"

describe_pid() {
    local pid="$1"

    ps -wwp "${pid}" -o cmd= 2>/dev/null || true
}

describe_tty() {
    local pid="$1"

    ps -wwp "${pid}" -o tty= 2>/dev/null | awk '{$1=$1; print}'
}

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: ${ENV_FILE} not found. Run make dev-setup first." >&2
    exit 1
fi

existing_pid="$(system_port_owner_pid "${port}")"
if [[ -n "${existing_pid}" ]]; then
    existing_cmd="$(describe_pid "${existing_pid}")"
    if [[ "${existing_cmd}" == *"next-server"* || "${existing_cmd}" == *"next dev"* ]]; then
        existing_tty="$(describe_tty "${existing_pid}")"
        echo "Next.js hot-reload server already running on http://localhost:${port}" >&2
        echo "PID: ${existing_pid}" >&2
        if [[ -n "${existing_tty}" && "${existing_tty}" != "?" ]]; then
            echo "Terminal: ${existing_tty}" >&2
        fi
        echo "Use make dev-ui-live-stop to stop it, or make dev-ui-live-logs to tail the saved log file." >&2
        exit 0
    fi

    echo "Port ${port} required for host web-app dev server is already in use." >&2
    if [[ -n "${existing_cmd}" ]]; then
        echo "Conflicting process: PID ${existing_pid} — ${existing_cmd}" >&2
    else
        echo "Conflicting process: PID ${existing_pid}" >&2
    fi
    echo "Stop the conflicting process or free the port, then rerun the target." >&2
    exit 1
fi

set -a
source "${ENV_FILE}"
set +a

mkdir -p "$(dirname "${log_file}")"
: > "${log_file}"
exec > >(tee -a "${log_file}") 2>&1

export ENVIRONMENT=dev
export AGENT_ENDPOINT="http://localhost:8088"
export OLLAMA_ENDPOINT="http://localhost:11434/v1"
export SEARCH_ENDPOINT="https://localhost:7250"
export STAGING_BLOB_ENDPOINT="http://localhost:10000/devstoreaccount1"
export SERVING_BLOB_ENDPOINT="http://localhost:10000/devstoreaccount1"
export AZURITE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=${AZURITE_ACCOUNT_KEY};BlobEndpoint=http://localhost:10000/devstoreaccount1;QueueEndpoint=http://localhost:10001/devstoreaccount1;TableEndpoint=http://localhost:10002/devstoreaccount1;"
export COSMOS_ENDPOINT="https://localhost:8081/"
export COSMOS_VERIFY_CERT=false
export OTEL_EXPORTER_OTLP_ENDPOINT=

echo "Starting Next.js hot-reload server on http://localhost:${port}"
echo "Using local backends at localhost:8088 (agent), 7250 (search), 8081 (Cosmos), and 10000 (Azurite)."
echo "Logging to ${log_file}"

cd "${ROOT_DIR}/src/web-app"
exec npx next dev --hostname 0.0.0.0 --port "${port}"