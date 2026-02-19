#!/bin/bash
# ---------------------------------------------------------------------------
# setup-entra-auth.sh — Create or reuse an Entra App Registration for Easy Auth
# Called by AZD preprovision hook to set ENTRA_CLIENT_ID and ENTRA_CLIENT_SECRET.
# ---------------------------------------------------------------------------
set -euo pipefail

ENV_NAME="${AZURE_ENV_NAME:-}"
if [ -z "$ENV_NAME" ]; then
  # Fallback: read from AZD environment values (works when run via AZD hooks)
  ENV_NAME=$(azd env get-value AZURE_ENV_NAME 2>/dev/null || echo "")
fi
if [ -z "$ENV_NAME" ]; then
  echo "ERROR: AZURE_ENV_NAME is not set and could not be determined from AZD."
  exit 1
fi

APP_NAME="webapp-kbidx-${ENV_NAME}"
echo "Setting up Entra App Registration: $APP_NAME"

# Check if we already have a client ID stored
EXISTING_CLIENT_ID=$(azd env get-value ENTRA_CLIENT_ID 2>/dev/null || echo "")
if [ -n "$EXISTING_CLIENT_ID" ]; then
  # Verify the app still exists
  APP_EXISTS=$(az ad app show --id "$EXISTING_CLIENT_ID" --query appId -o tsv 2>/dev/null || echo "")
  if [ -n "$APP_EXISTS" ]; then
    echo "Entra App Registration already exists: $EXISTING_CLIENT_ID"
    # Ensure client secret is set
    EXISTING_SECRET=$(azd env get-value ENTRA_CLIENT_SECRET 2>/dev/null || echo "")
    if [ -n "$EXISTING_SECRET" ]; then
      echo "Client secret already configured. Skipping."
      exit 0
    fi
    echo "Client secret missing. Generating a new one..."
    SECRET_JSON=$(az ad app credential reset --id "$EXISTING_CLIENT_ID" --display-name "easy-auth" --years 2 --query password -o tsv)
    azd env set ENTRA_CLIENT_SECRET "$SECRET_JSON"
    echo "Client secret stored."
    exit 0
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

echo "Entra App Registration configured:"
echo "  Client ID: $APP_ID"
echo "  Client Secret: (stored in AZD env)"
