#!/usr/bin/env bash
# =============================================================================
# validate-infra.sh — Verify Azure infrastructure is ready for local dev
# =============================================================================
# Checks:
#   1. Required env vars are set (from src/functions/.env)
#   2. Azure AI Search service is reachable
#   3. Content Understanding resource is reachable
#   4. Embedding deployment exists
#   5. Local kb/staging/ and kb/serving/ folders exist
#   6. Developer RBAC roles are assigned
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/src/functions/.env"

passed=0
failed=0
warnings=0

pass()  { echo "  ✔ $1"; passed=$((passed + 1)); }
fail()  { echo "  ✘ $1"; failed=$((failed + 1)); }
warn()  { echo "  ⚠ $1"; warnings=$((warnings + 1)); }

# ---------------------------------------------------------------------------
# 1. Load environment
# ---------------------------------------------------------------------------
echo ""
echo "─── Environment ───"

if [[ ! -f "$ENV_FILE" ]]; then
    fail ".env file not found at $ENV_FILE"
    echo ""
    echo "  Run: azd -C infra/azure env get-values > src/functions/.env"
    echo ""
    exit 1
fi

# Source .env (handles KEY="value" and KEY=value formats)
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

required_vars=(
    AI_SERVICES_ENDPOINT
    AI_SERVICES_NAME
    SEARCH_ENDPOINT
    SEARCH_SERVICE_NAME
    EMBEDDING_DEPLOYMENT_NAME
    RESOURCE_GROUP
    AZURE_SUBSCRIPTION_ID
)

all_vars_set=true
for var in "${required_vars[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        fail "Missing env var: $var"
        all_vars_set=false
    fi
done

if $all_vars_set; then
    pass "All required env vars are set"
else
    echo ""
    echo "  Fix: azd -C infra/azure env get-values > src/functions/.env"
    echo ""
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. Azure AI Search — reachable
# ---------------------------------------------------------------------------
echo ""
echo "─── Azure AI Search ───"

search_url="${SEARCH_ENDPOINT}/servicestats?api-version=2024-07-01"
http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $(az account get-access-token --resource https://search.azure.com --query accessToken -o tsv 2>/dev/null)" \
    "$search_url" 2>/dev/null || echo "000")

if [[ "$http_code" =~ ^2 ]]; then
    pass "AI Search reachable at $SEARCH_ENDPOINT (HTTP $http_code)"
elif [[ "$http_code" == "403" ]]; then
    warn "AI Search reachable but access denied (HTTP 403) — check RBAC roles"
elif [[ "$http_code" == "000" ]]; then
    fail "AI Search not reachable at $SEARCH_ENDPOINT (connection failed)"
else
    warn "AI Search returned HTTP $http_code at $SEARCH_ENDPOINT"
fi

# ---------------------------------------------------------------------------
# 3. Content Understanding — reachable
# ---------------------------------------------------------------------------
echo ""
echo "─── Content Understanding ───"

cu_url="${AI_SERVICES_ENDPOINT}contentunderstanding/analyzers?api-version=2025-05-01-preview"
http_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv 2>/dev/null)" \
    "$cu_url" 2>/dev/null || echo "000")

if [[ "$http_code" =~ ^(2|4) ]]; then
    pass "Content Understanding reachable at $AI_SERVICES_ENDPOINT (HTTP $http_code)"
elif [[ "$http_code" == "000" ]]; then
    fail "Content Understanding not reachable at $AI_SERVICES_ENDPOINT (connection failed)"
else
    warn "Content Understanding returned HTTP $http_code at $AI_SERVICES_ENDPOINT"
fi

# ---------------------------------------------------------------------------
# 4. Embedding deployment — exists
# ---------------------------------------------------------------------------
echo ""
echo "─── Embedding Deployment ───"

deploy_output=$(az cognitiveservices account deployment show \
    --name "$AI_SERVICES_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --deployment-name "$EMBEDDING_DEPLOYMENT_NAME" \
    --query "{name:name, model:properties.model.name, status:properties.provisioningState}" \
    -o tsv 2>&1) && deploy_rc=0 || deploy_rc=$?

if [[ $deploy_rc -eq 0 ]]; then
    pass "Embedding deployment '$EMBEDDING_DEPLOYMENT_NAME' exists"
else
    fail "Embedding deployment '$EMBEDDING_DEPLOYMENT_NAME' not found"
    echo "       $deploy_output"
fi

# ---------------------------------------------------------------------------
# 5. Local folders
# ---------------------------------------------------------------------------
echo ""
echo "─── Local Folders ───"

if [[ -d "$PROJECT_ROOT/kb/staging" ]]; then
    article_count=$(find "$PROJECT_ROOT/kb/staging" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
    if [[ "$article_count" -gt 0 ]]; then
        pass "kb/staging/ exists with $article_count article folder(s)"
    else
        warn "kb/staging/ exists but has no article subfolders"
    fi
else
    fail "kb/staging/ folder not found"
    echo "       Create it: mkdir -p kb/staging"
fi

if [[ -d "$PROJECT_ROOT/kb/serving" ]]; then
    pass "kb/serving/ exists"
else
    warn "kb/serving/ folder not found (will be created by fn-convert)"
    mkdir -p "$PROJECT_ROOT/kb/serving"
    pass "kb/serving/ created"
fi

# ---------------------------------------------------------------------------
# 6. Developer RBAC roles
# ---------------------------------------------------------------------------
echo ""
echo "─── Developer RBAC Roles ───"

# Get the current user's object ID
user_oid=$(az ad signed-in-user show --query id -o tsv 2>/dev/null) || true

if [[ -z "$user_oid" ]]; then
    warn "Could not determine signed-in user — skipping RBAC check (run 'az login' first)"
else
    # Roles to check: resource scope → role name
    declare -A role_checks=(
        ["Cognitive Services OpenAI User"]="/subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/$AI_SERVICES_NAME"
        ["Cognitive Services User"]="/subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/$AI_SERVICES_NAME"
        ["Search Index Data Contributor"]="/subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Search/searchServices/$SEARCH_SERVICE_NAME"
        ["Search Service Contributor"]="/subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Search/searchServices/$SEARCH_SERVICE_NAME"
    )

    for role_name in "${!role_checks[@]}"; do
        scope="${role_checks[$role_name]}"
        assignment=$(az role assignment list \
            --assignee "$user_oid" \
            --role "$role_name" \
            --scope "$scope" \
            --query "[0].id" -o tsv 2>/dev/null) || true

        if [[ -n "$assignment" ]]; then
            pass "$role_name"
        else
            fail "$role_name — not assigned"
            echo "       Fix: make grant-dev-roles"
        fi
    done
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "─── Summary ───"
echo "  Passed:   $passed"
echo "  Failed:   $failed"
echo "  Warnings: $warnings"
echo ""

if [[ $failed -gt 0 ]]; then
    echo "❌ Validation FAILED — fix the issues above before proceeding."
    exit 1
elif [[ $warnings -gt 0 ]]; then
    echo "⚠️  Validation passed with warnings."
    exit 0
else
    echo "✅ All checks passed — infrastructure is ready."
    exit 0
fi
