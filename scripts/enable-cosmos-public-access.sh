#!/usr/bin/env bash
# scripts/enable-cosmos-public-access.sh — Enable public access on Cosmos DB for local dev
# Run via: make dev-enable-cosmos
#
# Azure policy may disable public access nightly. This script re-enables it and
# adds the developer's current public IP to the Cosmos DB firewall allowlist.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/azd.sh"

ENV=$(azd env get-value AZURE_ENV_NAME 2>/dev/null || echo "dev")
PROJECT=$(azd env get-value PROJECT_NAME)
COSMOS_ACCOUNT="cosmos-${PROJECT}-${ENV}"
RG="rg-${PROJECT}-${ENV}"

echo "Resolving developer public IP..."
DEV_IP=$(curl -s https://ifconfig.me)

# On some networks (e.g. VPN / split-tunnel / Azure gateway) Cosmos DB may
# see a DIFFERENT source IP than the general internet IP.  Try to detect it
# by making a probe call and parsing the "originated from IP x.x.x.x" error.
COSMOS_IP=""
PROBE_MSG=$(az cosmosdb show \
    --name "$COSMOS_ACCOUNT" \
    --resource-group "$RG" \
    --query "documentEndpoint" -o tsv 2>/dev/null || true)
if [[ -n "$PROBE_MSG" ]]; then
    # Try a low-level Cosmos call that will fail with the IP in the error if blocked
    PROBE_ERR=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "x-ms-version: 2020-07-15" \
        "${PROBE_MSG}" 2>&1 || true)
    # If we can't detect from curl, try using Python to probe and capture the error IP
    COSMOS_IP=$(python3 -c "
import re, subprocess, sys
try:
    from azure.cosmos import CosmosClient
    from azure.identity import DefaultAzureCredential
    import logging
    logging.disable(logging.CRITICAL)
    c = CosmosClient('${PROBE_MSG}', credential=DefaultAzureCredential())
except Exception as e:
    m = re.search(r'originated from IP (\d+\.\d+\.\d+\.\d+)', str(e))
    if m:
        print(m.group(1))
" 2>/dev/null || true)
fi

echo ""
echo "  Cosmos DB Account : $COSMOS_ACCOUNT"
echo "  Resource Group    : $RG"
echo "  Developer IP      : $DEV_IP"
if [[ -n "$COSMOS_IP" && "$COSMOS_IP" != "$DEV_IP" ]]; then
    echo "  Cosmos-routed IP  : $COSMOS_IP (VPN/gateway)"
fi
echo ""

# Get any existing IP rules so we don't clobber them
EXISTING_IPS=$(az cosmosdb show \
    --name "$COSMOS_ACCOUNT" \
    --resource-group "$RG" \
    --query "ipRules[].ipAddressOrRange" \
    -o tsv 2>/dev/null || true)

# Build comma-separated list, adding dev IP if not already present
IP_LIST="$DEV_IP"
# Include the Cosmos-routed IP if it differs from general internet IP
if [[ -n "$COSMOS_IP" && "$COSMOS_IP" != "$DEV_IP" ]]; then
    IP_LIST="${IP_LIST},${COSMOS_IP}"
fi
if [[ -n "$EXISTING_IPS" ]]; then
    while IFS= read -r ip; do
        if [[ "$ip" != "$DEV_IP" && "$ip" != "$COSMOS_IP" ]]; then
            IP_LIST="${IP_LIST},${ip}"
        fi
    done <<< "$EXISTING_IPS"
fi

echo "Enabling public network access and updating firewall..."
az cosmosdb update \
    --name "$COSMOS_ACCOUNT" \
    --resource-group "$RG" \
    --public-network-access ENABLED \
    --ip-range-filter "$IP_LIST" \
    --output none

echo "  ✔ $COSMOS_ACCOUNT — public access enabled (IPs: $IP_LIST)"
echo ""
echo "Done. You can now connect to Cosmos DB from this machine."
