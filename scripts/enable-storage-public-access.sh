#!/usr/bin/env bash
# scripts/enable-storage-public-access.sh — Re-enable public network access on storage accounts
# Run via: make dev-enable-storage
#
# Azure policy disables public access nightly. This script re-enables it so you
# can upload staging files and test the app locally.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/azd.sh"

echo "Resolving storage account names from AZD environment..."

RG=$(azd env get-value RESOURCE_GROUP)
STAGING=$(azd env get-value STAGING_STORAGE_ACCOUNT)
SERVING=$(azd env get-value SERVING_STORAGE_ACCOUNT)
FUNCTIONS=$(azd env get-value FUNCTIONS_STORAGE_ACCOUNT 2>/dev/null || true)

echo ""
echo "  Resource Group : $RG"
echo "  Staging        : $STAGING"
echo "  Serving        : $SERVING"
echo "  Functions      : ${FUNCTIONS:-<not set — run make azure-provision to populate>}"
echo ""

ACCOUNTS=("$STAGING" "$SERVING")
if [[ -n "$FUNCTIONS" ]]; then
    ACCOUNTS+=("$FUNCTIONS")
fi

for ACCOUNT in "${ACCOUNTS[@]}"; do
    echo "Enabling public network access on $ACCOUNT..."
    az storage account update \
        --name "$ACCOUNT" \
        --resource-group "$RG" \
        --public-network-access Enabled \
        --output none
    echo "  ✔ $ACCOUNT — public access enabled"
done

echo ""
echo "Done. You can now upload staging files and test locally."
