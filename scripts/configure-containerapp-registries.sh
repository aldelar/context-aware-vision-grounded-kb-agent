#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# configure-containerapp-registries.sh — Attach ACR to provisioned Container Apps
# ---------------------------------------------------------------------------
# Idempotent — safe to re-run before prod service deploys.
# Configures each provisioned Container App to use the ACR from the active AZD
# environment with its system-assigned managed identity.
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/azd.sh"

readonly RESOURCE_GROUP="$(azd env get-value RESOURCE_GROUP 2>/dev/null || azd env get-value AZURE_RESOURCE_GROUP 2>/dev/null || echo "")"
readonly REGISTRY_SERVER="$(azd env get-value CONTAINER_REGISTRY_LOGIN_SERVER 2>/dev/null || azd env get-value AZURE_CONTAINER_REGISTRY_ENDPOINT 2>/dev/null || echo "")"

configure_registry() {
    local env_key="$1"
    local app_name

    app_name="$(azd env get-value "$env_key" 2>/dev/null || echo "")"
    if [[ -z "$app_name" ]]; then
        echo "  skip        $env_key is not set in the active AZD environment"
        return 0
    fi

    if ! az containerapp show --resource-group "$RESOURCE_GROUP" --name "$app_name" --query name -o tsv >/dev/null 2>&1; then
        echo "  skip        container app $app_name not found in $RESOURCE_GROUP"
        return 0
    fi

    az containerapp registry set \
        --resource-group "$RESOURCE_GROUP" \
        --name "$app_name" \
        --server "$REGISTRY_SERVER" \
        --identity system \
        -o none

    echo "  registry    attached $REGISTRY_SERVER to $app_name"
}

main() {
    echo "=== Configure Container App Registries ==="

    if [[ -z "$RESOURCE_GROUP" || -z "$REGISTRY_SERVER" ]]; then
        echo "  skip        active AZD environment is missing RESOURCE_GROUP or registry settings"
        exit 0
    fi

    echo "  Resource Group: $RESOURCE_GROUP"
    echo "  Registry:       $REGISTRY_SERVER"

    configure_registry WEBAPP_NAME
    configure_registry AGENT_APP_NAME
    configure_registry FUNC_CONVERT_CU_NAME
    configure_registry FUNC_CONVERT_MARKITDOWN_NAME
    configure_registry FUNC_CONVERT_MISTRAL_NAME
    configure_registry FUNC_INDEX_NAME

    echo "=== Done ==="
}

main "$@"