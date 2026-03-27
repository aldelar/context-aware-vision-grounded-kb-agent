#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# configure-containerapp-target-ports.sh — Set real ingress target ports
# ---------------------------------------------------------------------------
# Idempotent — safe to re-run after prod service deploys.
# Updates Container App ingress target ports from the placeholder bootstrap
# port to the actual application ports required by the deployed images.
# ---------------------------------------------------------------------------

set -euo pipefail

readonly RESOURCE_GROUP="$(azd env get-value RESOURCE_GROUP 2>/dev/null || azd env get-value AZURE_RESOURCE_GROUP 2>/dev/null || echo "")"

set_target_port() {
    local env_key="$1"
    local target_port="$2"
    local app_name
    local current_port

    app_name="$(azd env get-value "$env_key" 2>/dev/null || echo "")"
    if [[ -z "$app_name" ]]; then
        echo "  skip        $env_key is not set in the active AZD environment"
        return 0
    fi

    if ! current_port="$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$app_name" --query properties.configuration.ingress.targetPort -o tsv 2>/dev/null)"; then
        echo "  skip        container app $app_name not found in $RESOURCE_GROUP"
        return 0
    fi

    if [[ "$current_port" == "$target_port" ]]; then
        echo "  port        $app_name already targets $target_port"
        return 0
    fi

    az containerapp ingress update \
        --resource-group "$RESOURCE_GROUP" \
        --name "$app_name" \
        --target-port "$target_port" \
        -o none

    echo "  port        updated $app_name target port from $current_port to $target_port"
}

main() {
    echo "=== Configure Container App Target Ports ==="

    if [[ -z "$RESOURCE_GROUP" ]]; then
        echo "  skip        active AZD environment is missing RESOURCE_GROUP"
        exit 0
    fi

    echo "  Resource Group: $RESOURCE_GROUP"

    set_target_port WEBAPP_NAME 8080
    set_target_port AGENT_APP_NAME 8088

    echo "=== Done ==="
}

main "$@"