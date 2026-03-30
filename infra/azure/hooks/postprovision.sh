#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)

bash "${ROOT_DIR}/scripts/setup-redirect-uris.sh" || \
    echo "WARNING: Could not update redirect URIs. Run 'make azure-setup-auth' after fixing Graph API auth."

echo ""
echo "=============================================="
echo "  AI Gateway Manual Configuration Required"
echo "=============================================="
echo ""
echo "The APIM instance '${APIM_NAME}' is deployed."
echo "Link it to Foundry as AI Gateway via the portal:"
echo ""
echo "  1. Go to https://ai.azure.com"
echo "  2. Enable 'New Foundry' toggle"
echo "  3. Operate > Admin console > AI Gateway tab"
echo "  4. Click 'Add AI Gateway'"
echo "  5. Select Foundry resource: ${AI_SERVICES_NAME}"
echo "  6. Choose 'Use existing' > select: ${APIM_NAME}"
echo "  7. Name the gateway and click 'Add'"
echo "  8. After status shows 'Enabled', click the gateway name"
echo "  9. Add project '${FOUNDRY_PROJECT_NAME}' to the gateway"
echo ""
echo "=============================================="