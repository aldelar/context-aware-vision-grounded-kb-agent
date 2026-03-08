#!/bin/bash
# ---------------------------------------------------------------------------
# setup-entra-auth.sh — Create or reuse an Entra App Registration for Easy Auth
# Called by AZD preprovision hook to set ENTRA_CLIENT_ID and ENTRA_CLIENT_SECRET.
# Easy Auth handles authentication at the Container App platform level.
# ---------------------------------------------------------------------------
set -euo pipefail

# ---------------------------------------------------------------------------
# Helper functions (defined before use)
# ---------------------------------------------------------------------------

update_redirect_uris() {
  local client_id="$1"

  # Get the web app URL from AZD env (may not exist on first provision)
  local webapp_url
  webapp_url=$(azd env get-value WEBAPP_URL 2>/dev/null || echo "")
  if [ -z "$webapp_url" ]; then
    echo "WEBAPP_URL not set yet — skipping redirect URI configuration."
    echo "Run this script again after 'azd provision' to add redirect URIs."
    return 0
  fi

  # Add Chainlit's OAuth callback redirect URI
  local callback_url="${webapp_url}/auth/oauth/azure-ad/callback"
  echo "Adding redirect URI: $callback_url"

  # Get existing redirect URIs
  local existing_uris
  existing_uris=$(az ad app show --id "$client_id" --query "web.redirectUris" -o json 2>/dev/null || echo "[]")

  # Check if already present
  if echo "$existing_uris" | grep -q "$callback_url"; then
    echo "Redirect URI already configured."
    return 0
  fi

  # Add the new URI to existing ones
  az ad app update --id "$client_id" \
    --web-redirect-uris $callback_url \
    $(echo "$existing_uris" | python3 -c "import sys,json; [print(u) for u in json.load(sys.stdin)]" 2>/dev/null || true)

  echo "Redirect URI added successfully."
}

# ---------------------------------------------------------------------------
# Main script
# ---------------------------------------------------------------------------

ENV_NAME="${AZURE_ENV_NAME:-}"
if [ -z "$ENV_NAME" ]; then
  ENV_NAME=$(azd env get-value AZURE_ENV_NAME 2>/dev/null || echo "")
fi
if [ -z "$ENV_NAME" ]; then
  echo "ERROR: AZURE_ENV_NAME is not set and could not be determined from AZD."
  exit 1
fi

PROJECT_NAME=$(azd env get-value PROJECT_NAME)
APP_NAME="webapp-${PROJECT_NAME}-${ENV_NAME}"
echo "Setting up Entra App Registration: $APP_NAME"

# ---------------------------------------------------------------------------
# Create or reuse Entra App Registration
# ---------------------------------------------------------------------------
EXISTING_CLIENT_ID=$(azd env get-value ENTRA_CLIENT_ID 2>/dev/null || echo "")
if [ -n "$EXISTING_CLIENT_ID" ]; then
  # Try to verify the app registration; Graph API may be unavailable (CAE token refresh, etc.)
  APP_CHECK_OUTPUT=$(az ad app show --id "$EXISTING_CLIENT_ID" --query appId -o tsv 2>&1) && APP_CHECK_RC=0 || APP_CHECK_RC=$?

  if [ $APP_CHECK_RC -eq 0 ] && [ -n "$APP_CHECK_OUTPUT" ]; then
    echo "Entra App Registration already exists: $EXISTING_CLIENT_ID"
    EXISTING_SECRET=$(azd env get-value ENTRA_CLIENT_SECRET 2>/dev/null || echo "")
    if [ -n "$EXISTING_SECRET" ]; then
      echo "Client secret already configured."
    else
      echo "Client secret missing. Generating a new one..."
      SECRET_JSON=$(az ad app credential reset --id "$EXISTING_CLIENT_ID" --display-name "easy-auth" --years 2 --query password -o tsv)
      azd env set ENTRA_CLIENT_SECRET "$SECRET_JSON"
      echo "Client secret stored."
    fi

    # Ensure redirect URIs and OAuth env vars are up to date
    update_redirect_uris "$EXISTING_CLIENT_ID" || true
    exit 0
  elif echo "$APP_CHECK_OUTPUT" | grep -qi "InteractionRequired\|TokenCreated\|Continuous access"; then
    # Graph API unavailable due to CAE or token issues — not proof the app is deleted.
    # If we already have both client ID and secret, proceed optimistically.
    EXISTING_SECRET=$(azd env get-value ENTRA_CLIENT_SECRET 2>/dev/null || echo "")
    if [ -n "$EXISTING_SECRET" ]; then
      echo "WARNING: Graph API unavailable (CAE challenge). Using cached Entra credentials."
      echo "  Run 'az login --scope https://graph.microsoft.com/.default' then re-run this script to verify."
      exit 0
    else
      echo "ERROR: Graph API unavailable and no cached client secret. Please run:"
      echo "  az login --scope https://graph.microsoft.com/.default"
      echo "Then re-run this script."
      exit 1
    fi
  else
    echo "Stored client ID $EXISTING_CLIENT_ID no longer exists. Recreating..."
  fi
fi

# Create the Entra App Registration (single-tenant)
echo "Creating Entra App Registration..."
APP_ID=$(az ad app create \
  --display-name "$APP_NAME" \
  --sign-in-audience "AzureADMyOrg" \
  --enable-id-token-issuance true \
  --query appId -o tsv)

echo "App Registration created: $APP_ID"

# Create a client secret
SECRET=$(az ad app credential reset --id "$APP_ID" --display-name "easy-auth" --years 2 --query password -o tsv)

# Store in AZD environment
azd env set ENTRA_CLIENT_ID "$APP_ID"
azd env set ENTRA_CLIENT_SECRET "$SECRET"

# Set redirect URIs
update_redirect_uris "$APP_ID" || true

echo "Entra App Registration configured:"
echo "  Client ID: $APP_ID"
echo "  Client Secret: (stored in AZD env)"
