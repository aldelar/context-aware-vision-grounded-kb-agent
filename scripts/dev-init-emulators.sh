#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ENV_FILE="${ROOT_DIR}/.env.dev"
COMPOSE_FILE="${ROOT_DIR}/infra/docker/docker-compose.dev-infra.yml"
COMPOSE_PROJECT_NAME=${DEV_INFRA_PROJECT:-kb-agent-infra}
PYTHON_RUNTIME_DIR="${ROOT_DIR}/src/agent"
AZURITE_ACCOUNT_KEY="Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: ${ENV_FILE} not found. Create it from .env.dev.template first." >&2
    exit 1
fi

set -a
source "${ENV_FILE}"
set +a

# The env template uses Compose service hostnames for app containers.
# This script runs on the host, so rewrite emulator endpoints to localhost.
COSMOS_ENDPOINT=${COSMOS_ENDPOINT//cosmos-emulator/localhost}
STAGING_BLOB_ENDPOINT=${STAGING_BLOB_ENDPOINT//azurite/localhost}
SERVING_BLOB_ENDPOINT=${SERVING_BLOB_ENDPOINT//azurite/localhost}
SEARCH_ENDPOINT=${SEARCH_ENDPOINT//search-simulator/localhost}
OLLAMA_ENDPOINT=${OLLAMA_ENDPOINT//ollama/localhost}
OLLAMA_ENDPOINT=${OLLAMA_ENDPOINT//host.docker.internal/localhost}

# Rebuild the connection string explicitly for host-side tooling. Sourcing the
# .env file in bash cannot safely preserve the semicolon-delimited value.
AZURITE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=${AZURITE_ACCOUNT_KEY};BlobEndpoint=${STAGING_BLOB_ENDPOINT};QueueEndpoint=http://localhost:10001/devstoreaccount1;TableEndpoint=http://localhost:10002/devstoreaccount1;"

export COSMOS_ENDPOINT STAGING_BLOB_ENDPOINT SERVING_BLOB_ENDPOINT
export AZURITE_CONNECTION_STRING SEARCH_ENDPOINT OLLAMA_ENDPOINT
OLLAMA_API_ROOT="${OLLAMA_ENDPOINT%/v1}"
OLLAMA_API_ROOT="${OLLAMA_API_ROOT%/}"

normalize_ollama_model_ref() {
    local model=$1
    if [[ "${model}" == *:* ]]; then
        printf '%s\n' "${model}"
        return 0
    fi

    printf '%s:latest\n' "${model}"
}

ollama_model_present() {
    local normalized_model=$1

    python3 - "${OLLAMA_API_ROOT}" "${normalized_model}" <<'PY'
import json
import sys
import urllib.request

root, expected = sys.argv[1:]
with urllib.request.urlopen(f"{root}/api/tags", timeout=10) as response:
    payload = json.load(response)

available = set()
for model in payload.get("models", []):
    for key in ("name", "model"):
        value = model.get(key)
        if value:
            available.add(value)

sys.exit(0 if expected in available else 1)
PY
}

ollama_pull_model() {
    local model=$1

    python3 - "${OLLAMA_API_ROOT}" "${model}" <<'PY'
import json
import sys
import urllib.request

root, model = sys.argv[1:]
body = json.dumps({"name": model, "stream": False}).encode("utf-8")
request = urllib.request.Request(
    f"{root}/api/pull",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=1800) as response:
    payload = json.load(response)

if payload.get("error"):
    print(payload["error"], file=sys.stderr)
    sys.exit(1)
PY
}

wait_for_port() {
    local name=$1
    local host=$2
    local port=$3
    local attempts=${4:-60}

    for ((i=1; i<=attempts; i++)); do
        if python3 - <<PY
import socket
socket.create_connection(("${host}", ${port}), 2).close()
PY
        then
            echo "${name} is ready (${host}:${port})"
            return 0
        fi
        sleep 2
    done

    echo "ERROR: Timed out waiting for ${name} on ${host}:${port}" >&2
    exit 1
}

wait_for_cosmos_api() {
    local attempts=${1:-60}

    for ((i=1; i<=attempts; i++)); do
        if (cd "${PYTHON_RUNTIME_DIR}" && env -u VIRTUAL_ENV uv run python - <<'PY')
import os, sys, urllib3
urllib3.disable_warnings()

from azure.cosmos import CosmosClient

try:
    client = CosmosClient(
        url=os.environ["COSMOS_ENDPOINT"],
        credential=os.environ["COSMOS_KEY"],
        connection_verify=False,
    )
    client.list_databases()
except Exception:
    sys.exit(1)
print("Cosmos SDK connectivity ready")
PY
        then
            return 0
        fi
        sleep 3
    done

    echo "ERROR: Timed out waiting for Cosmos DB emulator API readiness" >&2
    exit 1
}

echo "Waiting for emulator ports..."
wait_for_port "Cosmos DB emulator" "localhost" 8081
wait_for_port "Azurite blob endpoint" "localhost" 10000
wait_for_port "AI Search Simulator" "localhost" 7250
wait_for_port "Ollama" "localhost" 11434
wait_for_cosmos_api

echo "Initializing Cosmos DB databases and containers..."
cd "${PYTHON_RUNTIME_DIR}"
env -u VIRTUAL_ENV uv run python - <<'PY'
import os, urllib3
urllib3.disable_warnings()

from azure.cosmos import CosmosClient, PartitionKey

client = CosmosClient(
    url=os.environ["COSMOS_ENDPOINT"],
    credential=os.environ["COSMOS_KEY"],
    connection_verify=False,
)

container_sets = {
    os.environ.get("COSMOS_DATABASE_NAME", "kb-agent"): {
        os.environ.get("COSMOS_SESSIONS_CONTAINER", "agent-sessions"): "/id",
        os.environ.get("COSMOS_CONVERSATIONS_CONTAINER", "conversations"): "/userId",
    },
    os.environ.get("COSMOS_TEST_DATABASE_NAME", "kb-agent-test"): {
        os.environ.get("COSMOS_SESSIONS_TEST_CONTAINER", "agent-sessions-test"): "/id",
        os.environ.get("COSMOS_CONVERSATIONS_TEST_CONTAINER", "conversations-test"): "/userId",
    },
}

for database_name, containers in container_sets.items():
    database = client.create_database_if_not_exists(id=database_name)
    for container_name, partition_key in containers.items():
        try:
            database.create_container_if_not_exists(
                id=container_name,
                partition_key=PartitionKey(path=partition_key),
            )
        except Exception as exc:
            if "Conflict" not in str(exc):
                raise
        print(f"Ready: {database_name}/{container_name} ({partition_key})")
PY

echo "Initializing Azurite blob containers..."
env -u VIRTUAL_ENV uv run python - <<'PY'
import os

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient

client = BlobServiceClient.from_connection_string(os.environ["AZURITE_CONNECTION_STRING"])
for container_name in (
    os.environ.get("STAGING_CONTAINER_NAME", "staging"),
    os.environ.get("SERVING_CONTAINER_NAME", "serving"),
    os.environ.get("STAGING_TEST_CONTAINER_NAME", "staging-test"),
    os.environ.get("SERVING_TEST_CONTAINER_NAME", "serving-test"),
):
    try:
        client.create_container(container_name)
    except ResourceExistsError:
        pass
    print(f"Ready: blob container {container_name}")
PY

echo "Ensuring Ollama models are available..."
for model in "${AGENT_MODEL_DEPLOYMENT_NAME:-phi4-mini}" "${EMBEDDING_DEPLOYMENT_NAME:-mxbai-embed-large}" "${VISION_DEPLOYMENT_NAME:-moondream}"; do
    normalized_model=$(normalize_ollama_model_ref "${model}")
    if ollama_model_present "${normalized_model}"; then
        echo "Ollama model already present: ${model}"
        continue
    fi
    echo "Pulling Ollama model: ${model}"
    ollama_pull_model "${model}"
done

echo "Emulator initialization complete."