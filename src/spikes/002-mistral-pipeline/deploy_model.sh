#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Deploy the mistral-document-ai-2512 model to an existing Azure AI Foundry
# (Cognitive Services) resource using a local Bicep template.
#
# Uses the same pattern as the core project (infra/modules/ai-services.bicep)
# but with 'Mistral AI' format instead of 'OpenAI'.
# Ref: https://github.com/Azure-Samples/azureai-model-inference-bicep
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Load environment variables from src/functions/.env
ENV_FILE="$PROJECT_ROOT/src/functions/.env"
if [[ -f "$ENV_FILE" ]]; then
    echo "Loading environment from $ENV_FILE"
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
else
    echo "Warning: $ENV_FILE not found – relying on existing environment / azd."
fi

# Resolve required variables, falling back to azd env get-value
RESOURCE_GROUP="${RESOURCE_GROUP:-${AZURE_RESOURCE_GROUP:-$(azd env get-value AZURE_RESOURCE_GROUP)}}"
AI_SERVICES_ACCOUNT="${AI_SERVICES_ACCOUNT:-${AI_SERVICES_NAME:-$(azd env get-value AI_SERVICES_NAME)}}"
DEPLOYMENT_NAME="mistral-document-ai-2512"

echo ""
echo "Resource Group       : $RESOURCE_GROUP"
echo "AI Services Account  : $AI_SERVICES_ACCOUNT"
echo "Deployment           : $DEPLOYMENT_NAME"
echo "Bicep template       : $SCRIPT_DIR/deploy-model.bicep"
echo ""

# ---- Deploy via Bicep ------------------------------------------------------
echo "Deploying model via Bicep ..."
az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$SCRIPT_DIR/deploy-model.bicep" \
    --parameters accountName="$AI_SERVICES_ACCOUNT" \
    --name "spike-002-mistral-$(date +%s)" \
    -o table

echo ""

# ---- Confirm the deployment ------------------------------------------------
echo "Confirming deployment ..."
az cognitiveservices account deployment show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$AI_SERVICES_ACCOUNT" \
    --deployment-name "$DEPLOYMENT_NAME" \
    -o table

echo ""
echo "Done. The '$DEPLOYMENT_NAME' deployment is ready."
