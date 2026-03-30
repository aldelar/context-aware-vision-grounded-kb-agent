#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# register-agent.sh — Register KB Agent in Foundry (Operate → Assets)
# ---------------------------------------------------------------------------
# Registers the agent in the Foundry portal via the AI Gateway (APIM).
# The agent runs as a Container App; this script creates/updates the
# agent entry so it appears under Operate → Assets with traces, and
# captures the Foundry-generated proxy URL for downstream use.
#
# Idempotent — re-running updates the existing registration.
#
# Prerequisites:
#   - azd env is configured (run `azd provision` first)
#   - Agent Container App is deployed (`azd deploy --service agent`)
#   - APIM connection exists on the Foundry project
#   - az CLI logged in
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/azd.sh"

echo "=== Register KB Agent in Foundry ==="
echo ""

# ---------------------------------------------------------------------------
# 1. Read environment values from AZD
# ---------------------------------------------------------------------------
AI_SERVICES_NAME=$(azd env get-value AI_SERVICES_NAME)
RESOURCE_GROUP=$(azd env get-value RESOURCE_GROUP)
FOUNDRY_PROJECT_NAME=$(azd env get-value FOUNDRY_PROJECT_NAME 2>/dev/null || azd env get-value AZURE_AI_PROJECT_NAME)
APIM_GATEWAY_URL=$(azd env get-value APIM_GATEWAY_URL)
AGENT_EXTERNAL_URL=$(azd env get-value AGENT_EXTERNAL_URL)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

echo "  AI Services:    $AI_SERVICES_NAME"
echo "  Project:        $FOUNDRY_PROJECT_NAME"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Subscription:   $SUBSCRIPTION_ID"
echo "  APIM Gateway:   $APIM_GATEWAY_URL"
echo "  Agent URL:      $AGENT_EXTERNAL_URL"
echo ""

# ARM API base path
ARM_BASE="https://management.azure.com/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/$AI_SERVICES_NAME/projects/$FOUNDRY_PROJECT_NAME"
API_VERSION="2025-10-01-preview"

# ---------------------------------------------------------------------------
# 2. Verify APIM connection exists on Foundry project
# ---------------------------------------------------------------------------
echo "Checking APIM connection on Foundry project..."
if ! az rest --method GET \
    --url "$ARM_BASE/connections/apim-connection?api-version=$API_VERSION" \
    -o json 2>/dev/null >/dev/null; then
    echo "ERROR: APIM connection not found on Foundry project. Run 'azd provision' first."
    exit 1
fi
echo "  APIM connection verified."
echo ""

# ---------------------------------------------------------------------------
# 3. Register agent application via AI Gateway
# ---------------------------------------------------------------------------
echo "Registering agent application..."
REGISTER_OUTPUT=$(az rest --method PUT \
    --url "$ARM_BASE/applications/kb-agent?api-version=$API_VERSION" \
    --body "{\"properties\":{\"displayName\":\"KB Agent\",\"agents\":[{\"agentName\":\"kb-agent\"}],\"definition\":{\"endpoint\":{\"uri\":\"$AGENT_EXTERNAL_URL\",\"authentication\":{\"type\":\"None\"}}}}}" \
    -o json 2>&1) || {
    echo "ERROR: Failed to register agent."
    echo "$REGISTER_OUTPUT"
    exit 1
}

echo "  Agent registered as 'kb-agent' in Foundry."
echo ""

# Extract display info
APP_STATE=$(echo "$REGISTER_OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('properties',{}).get('provisioningState','Unknown'))" 2>/dev/null || echo "Unknown")
echo "  Provisioning state: $APP_STATE"
echo ""

# ---------------------------------------------------------------------------
# 4. Capture Foundry-generated proxy URL
# ---------------------------------------------------------------------------
PROXY_URL=$(echo "$REGISTER_OUTPUT" | python3 -c "
import json, sys
d = json.load(sys.stdin)
# The proxy URL may be in properties.endpoint.uri or properties.gatewayUrl
props = d.get('properties', {})
url = props.get('gatewayUrl', '') or props.get('endpoint', {}).get('proxyUri', '')
print(url)
" 2>/dev/null || echo "")

if [ -n "$PROXY_URL" ]; then
    azd env set AGENT_REGISTERED_URL "$PROXY_URL"
    echo "  Proxy URL captured: $PROXY_URL"
    echo "  Stored as AGENT_REGISTERED_URL in AZD env."
else
    echo "  NOTE: No proxy URL returned. The agent endpoint can still be accessed directly."
    echo "  Setting AGENT_REGISTERED_URL to agent external URL as fallback."
    azd env set AGENT_REGISTERED_URL "$AGENT_EXTERNAL_URL"
fi
echo ""

echo "View in Foundry portal: https://ai.azure.com"
echo "  → Project: $FOUNDRY_PROJECT_NAME → Operate → Assets"
echo ""
echo "=== Done ==="
