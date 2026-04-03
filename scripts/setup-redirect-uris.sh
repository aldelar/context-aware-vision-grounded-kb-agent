#!/bin/bash
# ---------------------------------------------------------------------------
# setup-redirect-uris.sh — Add redirect URIs to the Entra App Registration
#
# Idempotent: safe to run multiple times.  Reads ENTRA_CLIENT_ID and
# WEBAPP_URL from AZD env.  Designed for both interactive dev and CI/CD
# (service-principal auth works fine — the CAE issue only affects interactive
# sessions with stale policies).
#
# Usage:
#   bash scripts/setup-redirect-uris.sh          # reads from AZD env
#   ENTRA_CLIENT_ID=xxx WEBAPP_URL=https://... bash scripts/setup-redirect-uris.sh
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/azd.sh"

# ---------------------------------------------------------------------------
# Resolve inputs — env vars take precedence, then AZD env
# ---------------------------------------------------------------------------
CLIENT_ID="${ENTRA_CLIENT_ID:-$(azd env get-value ENTRA_CLIENT_ID 2>/dev/null || echo "")}"
WEBAPP_URL="${WEBAPP_URL:-$(azd env get-value WEBAPP_URL 2>/dev/null || echo "")}"

if [ -z "$CLIENT_ID" ]; then
  echo "ERROR: ENTRA_CLIENT_ID is not set (env var or AZD env)." >&2
  exit 1
fi
if [ -z "$WEBAPP_URL" ]; then
  echo "ERROR: WEBAPP_URL is not set (env var or AZD env)." >&2
  exit 1
fi

# Strip trailing slash if present
WEBAPP_URL="${WEBAPP_URL%/}"

EASY_AUTH_URI="${WEBAPP_URL}/.auth/login/aad/callback"

echo "Entra App: $CLIENT_ID"
echo "Redirect URIs to ensure:"
echo "  1) $EASY_AUTH_URI"

# ---------------------------------------------------------------------------
# Read current redirect URIs
# ---------------------------------------------------------------------------
if ! CURRENT_URIS=$(az ad app show --id "$CLIENT_ID" --query "web.redirectUris" -o json 2>&1); then
  echo "ERROR: Could not read app registration. 'az ad' output:" >&2
  echo "$CURRENT_URIS" >&2
  echo "" >&2
  echo "If this is a CAE error, try:  az logout && az login --scope https://graph.microsoft.com/.default" >&2
  exit 1
fi

echo "Current redirect URIs: $CURRENT_URIS"

# ---------------------------------------------------------------------------
# Build the desired URI list (existing + any missing)
# ---------------------------------------------------------------------------
DESIRED_URIS=$(python3 -c "
import json, sys
current = json.loads('''$CURRENT_URIS''')
needed = ['$EASY_AUTH_URI']
merged = list(dict.fromkeys(current + needed))  # deduplicate, preserve order
for u in merged:
    print(u)
")

# Check if update is needed
NEED_UPDATE=false
for URI in "$EASY_AUTH_URI"; do
  if ! echo "$CURRENT_URIS" | grep -q "$URI"; then
    NEED_UPDATE=true
    break
  fi
done

if [ "$NEED_UPDATE" = "false" ]; then
  echo "All redirect URIs already present. Nothing to do."
  exit 0
fi

# ---------------------------------------------------------------------------
# Update the app registration
# ---------------------------------------------------------------------------
echo "Updating redirect URIs..."
# shellcheck disable=SC2086
az ad app update --id "$CLIENT_ID" --web-redirect-uris $DESIRED_URIS

echo "Redirect URIs updated successfully."

# Verify
UPDATED_URIS=$(az ad app show --id "$CLIENT_ID" --query "web.redirectUris" -o json)
echo "Verified: $UPDATED_URIS"
