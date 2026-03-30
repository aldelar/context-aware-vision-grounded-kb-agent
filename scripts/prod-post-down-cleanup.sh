#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME=""
ENVIRONMENT_NAME=""
LOCATION=""
RESOURCE_GROUP=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project-name)
            PROJECT_NAME="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT_NAME="$2"
            shift 2
            ;;
        --location)
            LOCATION="$2"
            shift 2
            ;;
        --resource-group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

if [[ -z "${PROJECT_NAME}" || -z "${ENVIRONMENT_NAME}" ]]; then
    echo "prod-post-down-cleanup.sh requires --project-name and --environment." >&2
    exit 2
fi

if [[ -z "${LOCATION}" ]]; then
    echo "prod-post-down-cleanup.sh requires --location so purge commands target the correct region." >&2
    exit 2
fi

if [[ -z "${RESOURCE_GROUP}" ]]; then
    RESOURCE_GROUP="rg-${PROJECT_NAME}-${ENVIRONMENT_NAME}"
fi

BASE_NAME="${PROJECT_NAME}-${ENVIRONMENT_NAME}"
AI_SERVICES_NAME="ai-${BASE_NAME}"
APIM_NAME="apim-${BASE_NAME}"
APP_INSIGHTS_NAME="appi-${BASE_NAME}"
WORKSPACE_NAME="log-${BASE_NAME}"

resource_group_exists() {
    az group exists --name "${RESOURCE_GROUP}" -o tsv 2>/dev/null | tr '[:upper:]' '[:lower:]'
}

delete_live_app_insights_component() {
    if [[ "$(resource_group_exists)" != "true" ]]; then
        return 0
    fi

    if az monitor app-insights component show \
        --app "${APP_INSIGHTS_NAME}" \
        --resource-group "${RESOURCE_GROUP}" \
        --only-show-errors >/dev/null 2>&1; then
        echo "Deleting Application Insights component ${APP_INSIGHTS_NAME}..."
        az monitor app-insights component delete \
            --app "${APP_INSIGHTS_NAME}" \
            --resource-group "${RESOURCE_GROUP}" \
            --only-show-errors >/dev/null || true
    fi
}

delete_live_log_analytics_workspace() {
    if [[ "$(resource_group_exists)" != "true" ]]; then
        return 0
    fi

    if az monitor log-analytics workspace show \
        --workspace-name "${WORKSPACE_NAME}" \
        --resource-group "${RESOURCE_GROUP}" \
        --only-show-errors >/dev/null 2>&1; then
        echo "Force-deleting Log Analytics workspace ${WORKSPACE_NAME} to release the name..."
        az monitor log-analytics workspace delete \
            --workspace-name "${WORKSPACE_NAME}" \
            --resource-group "${RESOURCE_GROUP}" \
            --force \
            --yes \
            --only-show-errors >/dev/null || true
    fi
}

wait_for_resource_group_removal() {
    local attempt
    for attempt in $(seq 1 30); do
        if [[ "$(resource_group_exists)" == "false" ]]; then
            return 0
        fi
        echo "  Waiting for resource group ${RESOURCE_GROUP} to be deleted... (${attempt}/30)"
        sleep 10
    done

    echo "ERROR: Resource group ${RESOURCE_GROUP} still exists after azd down." >&2
    return 1
}

purge_deleted_cognitive_account() {
    if az cognitiveservices account show-deleted \
        --name "${AI_SERVICES_NAME}" \
        --resource-group "${RESOURCE_GROUP}" \
        --location "${LOCATION}" \
        --only-show-errors >/dev/null 2>&1; then
        echo "Purging soft-deleted Cognitive Services account ${AI_SERVICES_NAME}..."
        az cognitiveservices account purge \
            --name "${AI_SERVICES_NAME}" \
            --resource-group "${RESOURCE_GROUP}" \
            --location "${LOCATION}" \
            --only-show-errors >/dev/null
    fi
}

purge_deleted_apim_service() {
    if az apim deletedservice show \
        --service-name "${APIM_NAME}" \
        --location "${LOCATION}" \
        --only-show-errors >/dev/null 2>&1; then
        echo "Purging soft-deleted APIM service ${APIM_NAME}..."
        az apim deletedservice purge \
            --service-name "${APIM_NAME}" \
            --location "${LOCATION}" \
            --only-show-errors >/dev/null
    fi
}

warn_if_deleted_workspace_remains() {
    local count
    count=$(az monitor log-analytics workspace list-deleted-workspaces \
        --query "[?name=='${WORKSPACE_NAME}'] | length(@)" \
        -o tsv)
    if [[ "${count:-0}" != "0" ]]; then
        echo "WARNING: Deleted Log Analytics workspace ${WORKSPACE_NAME} is still listed after teardown." >&2
        echo "WARNING: azd down --purge should normally clear this. If the next provision fails on the workspace name, inspect it with:" >&2
        echo "WARNING:   az monitor log-analytics workspace list-deleted-workspaces --query \"[?name=='${WORKSPACE_NAME}']\"" >&2
    fi
}

warn_if_app_insights_requires_manual_follow_up() {
    echo "NOTE: Application Insights deleted-resource purge is not exposed as a standard CLI name-release flow in this repo." >&2
    echo "NOTE: prod-down now deletes the live component before the RG disappears, but lingering App Insights conflicting-state issues may still require manual Azure follow-up." >&2
}

delete_live_app_insights_component
delete_live_log_analytics_workspace
wait_for_resource_group_removal
purge_deleted_cognitive_account
purge_deleted_apim_service
warn_if_deleted_workspace_remains
warn_if_app_insights_requires_manual_follow_up