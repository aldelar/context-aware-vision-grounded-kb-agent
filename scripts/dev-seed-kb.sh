#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ENV_FILE="${ROOT_DIR}/.env.dev"
LOCAL_KB_ROOT="${ROOT_DIR}/kb/staging"
AZURITE_ACCOUNT_KEY="Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="

has_local_kb_content() {
    local entry

    for entry in "${LOCAL_KB_ROOT}"/*; do
        [[ -e "${entry}" ]] && return 0
    done

    return 1
}

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: ${ENV_FILE} not found. Create it from .env.dev.template first." >&2
    exit 1
fi

if [[ ! -d "${LOCAL_KB_ROOT}" ]] || ! has_local_kb_content; then
    echo "ERROR: ${LOCAL_KB_ROOT} is empty. Add sample article folders before running the local pipeline." >&2
    exit 1
fi

set -a
source "${ENV_FILE}"
set +a

STAGING_BLOB_ENDPOINT=${STAGING_BLOB_ENDPOINT//azurite/localhost}
AZURITE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=${AZURITE_ACCOUNT_KEY};BlobEndpoint=${STAGING_BLOB_ENDPOINT};QueueEndpoint=http://localhost:10001/devstoreaccount1;TableEndpoint=http://localhost:10002/devstoreaccount1;"

export LOCAL_KB_ROOT AZURITE_CONNECTION_STRING
export STAGING_CONTAINER_NAME=${STAGING_CONTAINER_NAME:-staging}

echo "Syncing ${LOCAL_KB_ROOT} to Azurite container ${STAGING_CONTAINER_NAME}..."
cd "${ROOT_DIR}/src/functions"
env -u VIRTUAL_ENV uv run python - <<'PY'
import os
from pathlib import Path

from azure.storage.blob import BlobServiceClient, ContentSettings

root = Path(os.environ["LOCAL_KB_ROOT"])
container_name = os.environ["STAGING_CONTAINER_NAME"]
connection_string = os.environ["AZURITE_CONNECTION_STRING"]

client = BlobServiceClient.from_connection_string(connection_string)
container = client.get_container_client(container_name)

uploaded = 0
for path in sorted(root.rglob("*")):
    if not path.is_file():
        continue

    blob_name = path.relative_to(root).as_posix()
    content_type = None
    if path.suffix == ".html":
        content_type = "text/html"
    elif path.suffix == ".json":
        content_type = "application/json"

    kwargs = {"overwrite": True}
    if content_type:
        kwargs["content_settings"] = ContentSettings(content_type=content_type)

    with path.open("rb") as handle:
        container.upload_blob(blob_name, handle, **kwargs)
    uploaded += 1

print(f"Uploaded {uploaded} files to {container_name}")
PY
