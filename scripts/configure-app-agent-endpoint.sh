#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# configure-app-agent-endpoint.sh — Set web app's AGENT_ENDPOINT to the
# registered agent proxy URL (from APIM gateway registration).
# ---------------------------------------------------------------------------
# Idempotent — safe to re-run. Updates the web app Container App's
# AGENT_ENDPOINT env var to point to the registered agent URL.
#
# Prerequisites:
#   - azd env has AGENT_REGISTERED_URL (set by register-agent.sh)
#   - Web app Container App is deployed
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/azd.sh"

echo "=== Configure Web App Agent Endpoint ==="
echo ""

# Read values from AZD env
# Use the APIM gateway URL as the agent endpoint. The Foundry proxy URL
# (AGENT_REGISTERED_URL) does not support token-based CheckAccess for the
# Applications_Wildcard_Post operation, so traffic must go through our APIM
# gateway which passes requests through to the agent Container App.
APIM_GATEWAY_URL=$(azd env get-value APIM_GATEWAY_URL 2>/dev/null || echo "")
WEBAPP_NAME=$(azd env get-value WEBAPP_NAME)
RESOURCE_GROUP=$(azd env get-value RESOURCE_GROUP)

if [ -z "$APIM_GATEWAY_URL" ]; then
  echo "WARNING: APIM_GATEWAY_URL not set in AZD env."
  echo "  Run 'azd provision' first."
  echo "  Skipping web app configuration."
  exit 0
fi

echo "  Web App:            $WEBAPP_NAME"
echo "  Resource Group:     $RESOURCE_GROUP"
echo "  Agent Endpoint:     $APIM_GATEWAY_URL"
echo ""

echo "Updating web app AGENT_ENDPOINT..."
az containerapp update \
  --name "$WEBAPP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars "AGENT_ENDPOINT=$APIM_GATEWAY_URL" \
  -o none

echo "  Web app AGENT_ENDPOINT updated to: $APIM_GATEWAY_URL"
echo ""
echo "=== Done ==="
