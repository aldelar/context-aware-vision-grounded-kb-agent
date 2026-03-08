#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# publish-agent.sh — Publish the KB Agent to Foundry and assign RBAC
# ---------------------------------------------------------------------------
# Workflow:
#   1. Create Agent Application via ARM PUT
#   2. Create Agent Deployment via ARM PUT (required for invocation endpoint)
#   3. Wait for identity provisioning (up to 5 minutes)
#   4. Assign RBAC roles to the published agent identity:
#      - Cognitive Services OpenAI User  (AI Services — reasoning + embeddings)
#      - Search Index Data Reader        (AI Search — query index)
#      - Storage Blob Data Reader        (Serving Storage — download images)
#   5. Store the agent endpoint URL in AZD env for web app deployment
#
# Published endpoint:
#   POST https://{account}.services.ai.azure.com/api/projects/{project}/
#        applications/kb-agent/protocols/openai/responses?api-version=2025-11-15-preview
#
# Notes:
#   - Publishing requires TWO ARM operations: Application + Deployment.
#     Without a deployment, the endpoint returns "no deployments associated".
#   - The `az cognitiveservices account agent publish` CLI command does not
#     exist. We use the ARM management-plane PUT API directly.
#   - Published agent identities may take several minutes to provision.
#     The agent works with the project MI while identity provisioning
#     completes.
#
# Prerequisites:
#   - azd env is configured (run `azd provision` first)
#   - Agent is deployed in dev mode (`azd deploy --service agent`)
#   - az CLI logged in with sufficient permissions
# ---------------------------------------------------------------------------
set -euo pipefail

echo "=== Publish KB Agent to Foundry ==="
echo ""

# ---------------------------------------------------------------------------
# 1. Read environment values from AZD
# ---------------------------------------------------------------------------
AI_SERVICES_NAME=$(azd env get-value AI_SERVICES_NAME)
RESOURCE_GROUP=$(azd env get-value RESOURCE_GROUP)
FOUNDRY_PROJECT_NAME=$(azd env get-value FOUNDRY_PROJECT_NAME 2>/dev/null || azd env get-value AZURE_AI_PROJECT_NAME)
SEARCH_SERVICE_NAME=$(azd env get-value SEARCH_SERVICE_NAME)
SERVING_STORAGE_ACCOUNT=$(azd env get-value SERVING_STORAGE_ACCOUNT)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

echo "  AI Services:     $AI_SERVICES_NAME"
echo "  Project:         $FOUNDRY_PROJECT_NAME"
echo "  Resource Group:  $RESOURCE_GROUP"
echo "  Search:          $SEARCH_SERVICE_NAME"
echo "  Serving Storage: $SERVING_STORAGE_ACCOUNT"
echo "  Subscription:    $SUBSCRIPTION_ID"
echo ""

# ARM API base path
ARM_BASE="https://management.azure.com/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/$AI_SERVICES_NAME/projects/$FOUNDRY_PROJECT_NAME"
API_VERSION="2025-10-01-preview"

# ---------------------------------------------------------------------------
# 2. Create Agent Application via ARM PUT
# ---------------------------------------------------------------------------
echo "Step 1/2: Creating agent application..."
PUBLISH_OUTPUT=$(az rest --method PUT \
    --url "$ARM_BASE/applications/kb-agent?api-version=$API_VERSION" \
    --body '{"properties":{"displayName":"KB Agent","agents":[{"agentName":"kb-agent"}]}}' \
    -o json 2>&1) || {
    echo "ERROR: Failed to create agent application."
    echo "$PUBLISH_OUTPUT"
    exit 1
}

echo "  Application created/updated."

# Extract key fields
APP_BASE_URL=$(echo "$PUBLISH_OUTPUT" | python3 -c "import json,sys; print(json.load(sys.stdin)['properties']['baseUrl'])" 2>/dev/null || echo "")
BLUEPRINT_STATE=$(echo "$PUBLISH_OUTPUT" | python3 -c "import json,sys; print(json.load(sys.stdin)['properties']['agentIdentityBlueprint']['provisioningState'])" 2>/dev/null || echo "Unknown")
BLUEPRINT_PRINCIPAL=$(echo "$PUBLISH_OUTPUT" | python3 -c "import json,sys; print(json.load(sys.stdin)['properties']['agentIdentityBlueprint']['principalId'])" 2>/dev/null || echo "")

echo "  Base URL:            $APP_BASE_URL"
echo "  Blueprint state:     $BLUEPRINT_STATE"
echo "  Blueprint principal: $BLUEPRINT_PRINCIPAL"
echo ""

# ---------------------------------------------------------------------------
# 3. Create Agent Deployment via ARM PUT (with retry for transient errors)
# ---------------------------------------------------------------------------
echo "Step 2/2: Creating agent deployment..."
AGENT_VERSION=$(az rest --method GET \
    --url "$ARM_BASE/agents/kb-agent?api-version=$API_VERSION" \
    --query "properties.latestVersion" -o tsv 2>/dev/null || echo "3")

DEPLOY_BODY=$(cat <<EOF
{
  "properties": {
    "deploymentType": "Hosted",
    "minReplicas": 1,
    "maxReplicas": 1,
    "protocols": [{"protocol": "Responses", "version": "1.0"}],
    "agents": [{"agentName": "kb-agent", "agentVersion": "$AGENT_VERSION"}]
  }
}
EOF
)

# Retry up to 4 times with 30s backoff — ARM backend returns transient
# SystemError when the application identity is still provisioning.
DEPLOY_OK=false
for attempt in 1 2 3 4; do
    DEPLOY_OUTPUT=$(az rest --method PUT \
        --url "$ARM_BASE/applications/kb-agent/agentdeployments/default?api-version=$API_VERSION" \
        --body "$DEPLOY_BODY" \
        -o json 2>&1) && { DEPLOY_OK=true; break; }

    echo "  Attempt $attempt failed (transient error). Retrying in 30s..."
    sleep 30
done

if [ "$DEPLOY_OK" = false ]; then
    # Last resort: check if the deployment already exists and is usable
    DEPLOY_STATE=$(az rest --method GET \
        --url "$ARM_BASE/applications/kb-agent/agentdeployments/default?api-version=$API_VERSION" \
        --query "properties.state" -o tsv 2>/dev/null || echo "")
    if [ -n "$DEPLOY_STATE" ]; then
        echo "  Deployment already exists (state=$DEPLOY_STATE). Continuing."
    else
        echo "ERROR: Failed to create agent deployment after 4 attempts."
        echo "$DEPLOY_OUTPUT"
        exit 1
    fi
else
    DEPLOY_STATE=$(echo "$DEPLOY_OUTPUT" | python3 -c "import json,sys; print(json.load(sys.stdin)['properties']['state'])" 2>/dev/null || echo "Unknown")
    echo "  Deployment state: $DEPLOY_STATE"
fi

# Wait for deployment to reach Running state (up to 3 minutes)
if [ "$DEPLOY_STATE" != "Running" ]; then
    echo "  Waiting for deployment to reach Running state..."
    for i in $(seq 1 18); do
        sleep 10
        DEPLOY_STATE=$(az rest --method GET \
            --url "$ARM_BASE/applications/kb-agent/agentdeployments/default?api-version=$API_VERSION" \
            --query "properties.state" -o tsv 2>/dev/null || echo "Unknown")
        echo "  [$i/18] Deployment state: $DEPLOY_STATE"
        if [ "$DEPLOY_STATE" = "Running" ]; then
            break
        fi
    done
fi

if [ "$DEPLOY_STATE" = "Running" ]; then
    echo "  Deployment is running!"
else
    echo "  WARNING: Deployment not yet Running (state=$DEPLOY_STATE). May need more time."
fi
echo ""

# ---------------------------------------------------------------------------
# 4. Wait for identity provisioning (up to 5 minutes)
# ---------------------------------------------------------------------------
if [ "$BLUEPRINT_STATE" != "Succeeded" ]; then
    echo "Waiting for agent identity to provision (up to 5 minutes)..."
    for i in $(seq 1 20); do
        sleep 15
        STATE=$(az rest --method GET \
            --url "$ARM_BASE/applications/kb-agent?api-version=$API_VERSION" \
            --query "properties.agentIdentityBlueprint.provisioningState" -o tsv 2>&1)
        echo "  [$i/20] Identity state: $STATE"
        if [ "$STATE" = "Succeeded" ]; then
            BLUEPRINT_STATE="Succeeded"
            # Re-read the principal ID (may have changed)
            BLUEPRINT_PRINCIPAL=$(az rest --method GET \
                --url "$ARM_BASE/applications/kb-agent?api-version=$API_VERSION" \
                --query "properties.agentIdentityBlueprint.principalId" -o tsv 2>&1)
            echo "  Identity provisioned! Principal: $BLUEPRINT_PRINCIPAL"
            break
        fi
    done
    echo ""
fi

# ---------------------------------------------------------------------------
# 5. Assign RBAC to the published agent identity
# ---------------------------------------------------------------------------
if [ "$BLUEPRINT_STATE" = "Succeeded" ] && [ -n "$BLUEPRINT_PRINCIPAL" ]; then
    echo "Assigning RBAC roles to published agent identity ($BLUEPRINT_PRINCIPAL)..."

    # Cognitive Services OpenAI User (AI Services — reasoning + embeddings)
    echo "  → Cognitive Services OpenAI User on AI Services..."
    AI_SERVICES_ID=$(az cognitiveservices account show \
        --name "$AI_SERVICES_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query id -o tsv)
    az role assignment create \
        --assignee-object-id "$BLUEPRINT_PRINCIPAL" \
        --assignee-principal-type ServicePrincipal \
        --role "Cognitive Services OpenAI User" \
        --scope "$AI_SERVICES_ID" \
        --only-show-errors 2>/dev/null || echo "    (may already exist)"

    # Search Index Data Reader (AI Search — query index)
    echo "  → Search Index Data Reader on AI Search..."
    SEARCH_ID=$(az search service show \
        --name "$SEARCH_SERVICE_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query id -o tsv)
    az role assignment create \
        --assignee-object-id "$BLUEPRINT_PRINCIPAL" \
        --assignee-principal-type ServicePrincipal \
        --role "Search Index Data Reader" \
        --scope "$SEARCH_ID" \
        --only-show-errors 2>/dev/null || echo "    (may already exist)"

    # Storage Blob Data Reader (Serving Storage — download images for vision)
    echo "  → Storage Blob Data Reader on Serving Storage..."
    STORAGE_ID=$(az storage account show \
        --name "$SERVING_STORAGE_ACCOUNT" \
        --resource-group "$RESOURCE_GROUP" \
        --query id -o tsv)
    az role assignment create \
        --assignee-object-id "$BLUEPRINT_PRINCIPAL" \
        --assignee-principal-type ServicePrincipal \
        --role "Storage Blob Data Reader" \
        --scope "$STORAGE_ID" \
        --only-show-errors 2>/dev/null || echo "    (may already exist)"

    echo "  RBAC assignments complete."
    echo ""
else
    echo "WARNING: Agent identity provisioning did not complete."
    echo "         RBAC roles must be assigned manually once the identity is ready."
    echo "         Check status:"
    echo "           az rest --method GET --url '$ARM_BASE/applications/kb-agent?api-version=$API_VERSION'"
    echo ""
fi

# ---------------------------------------------------------------------------
# 6. Store agent endpoint in AZD env
# ---------------------------------------------------------------------------
# The published invocation URL requires the /protocols/openai suffix.
# The OpenAI SDK appends /responses to the base_url, producing:
#   {base_url}/responses?api-version=2025-11-15-preview
if [ -n "$APP_BASE_URL" ]; then
    AGENT_ENDPOINT="${APP_BASE_URL%/}/protocols/openai"
    echo "Using published endpoint: $AGENT_ENDPOINT"
else
    # Fall back to dev endpoint (metadata only — not suitable for invocation)
    AGENT_ENDPOINT=$(azd env get-value AGENT_AGENT_ENDPOINT 2>/dev/null || echo "")
    if [ -z "$AGENT_ENDPOINT" ]; then
        echo "WARNING: No endpoint found. Set AGENT_ENDPOINT manually."
    else
        echo "Published baseUrl not available — using dev endpoint as fallback."
        echo "  Dev endpoint: $AGENT_ENDPOINT"
    fi
fi

if [ -n "$AGENT_ENDPOINT" ]; then
    azd env set AGENT_ENDPOINT "$AGENT_ENDPOINT"
    echo ""
    echo "  AGENT_ENDPOINT=$AGENT_ENDPOINT"
    echo ""
    echo "To deploy the web app with this endpoint:"
    echo "  make azure-deploy-app"
fi

echo ""
echo "=== Done ==="
