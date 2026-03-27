#!/usr/bin/env bash
set -euo pipefail
# scripts/dev-clean-data.sh — Clear knowledge-base data from local emulators.
# Usage: bash scripts/dev-clean-data.sh <storage|cosmos|index>

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ENV_FILE="${ROOT_DIR}/.env.dev"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: ${ENV_FILE} not found." >&2
    exit 1
fi

set -a
source "${ENV_FILE}"
set +a

# Rewrite Compose service hostnames to localhost for host-side access.
COSMOS_ENDPOINT=${COSMOS_ENDPOINT//cosmos-emulator/localhost}
STAGING_BLOB_ENDPOINT=${STAGING_BLOB_ENDPOINT//azurite/localhost}
SERVING_BLOB_ENDPOINT=${SERVING_BLOB_ENDPOINT//azurite/localhost}
SEARCH_ENDPOINT=${SEARCH_ENDPOINT//search-simulator/localhost}

AZURITE_ACCOUNT_KEY="Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
AZURITE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=${AZURITE_ACCOUNT_KEY};BlobEndpoint=${STAGING_BLOB_ENDPOINT};QueueEndpoint=http://localhost:10001/devstoreaccount1;TableEndpoint=http://localhost:10002/devstoreaccount1;"

export COSMOS_ENDPOINT STAGING_BLOB_ENDPOINT SERVING_BLOB_ENDPOINT
export AZURITE_CONNECTION_STRING SEARCH_ENDPOINT

ACTION="${1:?Usage: dev-clean-data.sh <storage|cosmos|index>}"

case "${ACTION}" in
storage)
    echo "Clearing staging + serving blob containers..."
    cd "${ROOT_DIR}/src/web-app"
    uv run python - <<'PY'
import os
from azure.storage.blob import BlobServiceClient

client = BlobServiceClient.from_connection_string(os.environ["AZURITE_CONNECTION_STRING"])
for name in (
    os.environ.get("STAGING_CONTAINER_NAME", "staging"),
    os.environ.get("SERVING_CONTAINER_NAME", "serving"),
):
    container = client.get_container_client(name)
    blobs = list(container.list_blobs())
    for blob in blobs:
        container.delete_blob(blob.name)
    print(f"  Cleared {len(blobs)} blob(s) from {name}")
PY
    echo "Done."
    ;;

cosmos)
    echo "Clearing Cosmos DB containers..."
    cd "${ROOT_DIR}/src/web-app"
    uv run python - <<'PY'
import os
from azure.cosmos import CosmosClient

client = CosmosClient(
    url=os.environ["COSMOS_ENDPOINT"],
    credential=os.environ["COSMOS_KEY"],
    connection_verify=False,
)

db_name = os.environ.get("COSMOS_DATABASE_NAME", "kb-agent")
database = client.get_database_client(db_name)

containers = {
    os.environ.get("COSMOS_SESSIONS_CONTAINER", "agent-sessions"): "/id",
    os.environ.get("COSMOS_CONVERSATIONS_CONTAINER", "conversations"): "/userId",
    os.environ.get("COSMOS_MESSAGES_CONTAINER", "messages"): "/conversationId",
    os.environ.get("COSMOS_REFERENCES_CONTAINER", "references"): "/conversationId",
}

for container_name, pk_path in containers.items():
    container = database.get_container_client(container_name)
    pk_field = pk_path.lstrip("/")
    items = list(container.read_all_items())
    for item in items:
        container.delete_item(item["id"], partition_key=item[pk_field])
    print(f"  Cleared {len(items)} item(s) from {db_name}/{container_name}")
PY
    echo "Done."
    ;;

index)
    echo "Clearing AI Search index documents..."
    cd "${ROOT_DIR}/src/web-app"
    uv run python - <<'PY'
import os, urllib3
urllib3.disable_warnings()

from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

index_name = os.environ.get("SEARCH_INDEX_NAME", "kb-articles")
endpoint = os.environ["SEARCH_ENDPOINT"]
api_key = os.environ.get("SEARCH_API_KEY", "dev-admin-key")
verify = os.environ.get("SEARCH_VERIFY_CERT", "true").lower() == "true"

client = SearchClient(
    endpoint=endpoint,
    index_name=index_name,
    credential=AzureKeyCredential(api_key),
    connection_verify=verify,
)
try:
    docs = list(client.search("*", select=["id"]))
    if docs:
        client.delete_documents(documents=[{"id": d["id"]} for d in docs])
    print(f"  Cleared {len(docs)} document(s) from '{index_name}'.")
except Exception as exc:
    if "404" in str(exc) or "not found" in str(exc).lower():
        print(f"  Index '{index_name}' does not exist — nothing to clear.")
    else:
        raise
PY
    echo "Done."
    ;;

*)
    echo "Usage: dev-clean-data.sh <storage|cosmos|index>" >&2
    exit 1
    ;;
esac
