#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
# shellcheck disable=SC1091
source "${ROOT_DIR}/scripts/lib/azd.sh"

ensure_feature_registered() {
    local namespace="$1"
    local feature_name="$2"
    local state
    local attempt

    state=$(az feature show --namespace "${namespace}" --name "${feature_name}" --query properties.state -o tsv 2>/dev/null || true)
    if [[ "${state}" == "Registered" ]]; then
        return 0
    fi

    echo "Registering Azure feature ${namespace}/${feature_name}..."
    az feature register --namespace "${namespace}" --name "${feature_name}" --only-show-errors >/dev/null

    for attempt in $(seq 1 30); do
        state=$(az feature show --namespace "${namespace}" --name "${feature_name}" --query properties.state -o tsv 2>/dev/null || true)
        if [[ "${state}" == "Registered" ]]; then
            echo "Azure feature ${namespace}/${feature_name} is registered."
            az provider register --namespace "${namespace}" --only-show-errors >/dev/null 2>&1 || true
            return 0
        fi

        echo "  Waiting for ${namespace}/${feature_name} registration... (${attempt}/30)"
        sleep 10
    done

    echo "ERROR: Azure feature ${namespace}/${feature_name} is still not registered." >&2
    echo "Check with: az feature show --namespace ${namespace} --name ${feature_name}" >&2
    exit 1
}

if ! azd env get-value PROJECT_NAME >/dev/null 2>&1; then
    echo "ERROR: PROJECT_NAME is not set. Run: make set-project name=<your-name>"
    exit 1
fi

ensure_feature_registered "Microsoft.Insights" "AIWorkspacePreview"

if ! azd env get-value AZURE_PRINCIPAL_ID >/dev/null 2>&1; then
    PRINCIPAL_ID=$(az ad signed-in-user show --query id -o tsv 2>/dev/null || true)
    if [[ -n "${PRINCIPAL_ID}" ]]; then
        azd env set AZURE_PRINCIPAL_ID "${PRINCIPAL_ID}"
        echo "Set AZURE_PRINCIPAL_ID=${PRINCIPAL_ID}"
    else
        echo "WARNING: Could not determine signed-in user principal ID. Deployer RBAC roles will be skipped."
    fi
fi

AZURE_ENV_NAME=$(azd env get-value AZURE_ENV_NAME 2>/dev/null || true)
export AZURE_ENV_NAME

RG_NAME=$(azd env get-value AZURE_RESOURCE_GROUP 2>/dev/null || true)
LOCATION=$(azd env get-value AZURE_LOCATION 2>/dev/null || echo "eastus2")
if [[ -n "${RG_NAME}" ]]; then
    az group create --name "${RG_NAME}" --location "${LOCATION}" --output none 2>/dev/null && \
        echo "Resource group '${RG_NAME}' ready in ${LOCATION}" || \
        echo "WARNING: Could not create resource group '${RG_NAME}'. It may already exist."
fi

bash "${ROOT_DIR}/scripts/setup-entra-auth.sh"