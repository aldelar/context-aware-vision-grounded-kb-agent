"""Manage CU custom analyzers (deploy / delete / setup).

Usage:
    python -m manage_analyzers setup    # Set CU default model deployments (run once)
    python -m manage_analyzers deploy   # Create or update kb-image-analyzer
    python -m manage_analyzers delete   # Delete kb-image-analyzer
    python -m manage_analyzers status   # Check if kb-image-analyzer exists
"""

import json
import os
import sys
from pathlib import Path

from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

ANALYZER_ID = "kb_image_analyzer"
ANALYZER_DEF_PATH = Path(__file__).resolve().parent / "definitions" / "kb-image-analyzer.json"

# Map CU model names → deployment names in our AI Services account.
# CU completion models: gpt-4o, gpt-4o-mini, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano
# NOTE: prebuilt-documentSearch requires text-embedding-3-large AND gpt-4.1-mini —
#       silently returns 0 contents if either is not deployed and registered.
MODEL_DEPLOYMENTS = {
    "gpt-4.1": "gpt-4.1",
    "gpt-4.1-mini": "gpt-4.1-mini",
    "text-embedding-3-small": os.environ.get("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small"),
    "text-embedding-3-large": "text-embedding-3-large",
}


def _get_client() -> ContentUnderstandingClient:
    return ContentUnderstandingClient(
        endpoint=os.environ.get("AI_SERVICES_ENDPOINT", ""),
        credential=DefaultAzureCredential(),
    )


def setup() -> None:
    """Set CU default model deployments (required once per AI Services resource).

    Uses JSON Merge Patch: sets desired mappings and removes stale ones
    (null = delete in merge-patch semantics) so old deployments that no
    longer exist don't break subsequent analyzer operations.
    """
    client = _get_client()
    print("Setting CU default model deployments...")

    # Read current defaults and build a patch that removes stale entries.
    try:
        current = client.get_defaults()
        current_mappings = current.model_deployments or {}
    except HttpResponseError:
        # Defaults not yet set (fresh deployment) — nothing stale to clean up.
        current_mappings = {}
    stale_keys = set(current_mappings.keys()) - set(MODEL_DEPLOYMENTS.keys())

    patch: dict[str, str | None] = {}
    for key in stale_keys:
        patch[key] = None  # null → remove via merge-patch
        print(f"  Removing stale default: {key}")
    patch.update(MODEL_DEPLOYMENTS)

    client.update_defaults(body={"modelDeployments": patch})

    # Verify
    defaults = client.get_defaults()
    for model_name, deployment_name in defaults.model_deployments.items():
        print(f"  {model_name} → {deployment_name}")
    print("  Defaults configured.")


def deploy() -> None:
    """Create or update the kb-image-analyzer in Content Understanding."""
    # Ensure defaults are set before deploying
    setup()

    if not ANALYZER_DEF_PATH.exists():
        print(f"Error: Analyzer definition not found at {ANALYZER_DEF_PATH}", file=sys.stderr)
        sys.exit(1)

    definition = json.loads(ANALYZER_DEF_PATH.read_text())
    client = _get_client()

    print(f"Deploying analyzer '{ANALYZER_ID}'...")
    poller = client.begin_create_analyzer(
        analyzer_id=ANALYZER_ID,
        resource=definition,
        allow_replace=True,
    )
    result = poller.result()
    print(f"  Analyzer '{result.analyzer_id}' deployed successfully.")


def delete() -> None:
    """Delete the kb-image-analyzer from Content Understanding."""
    client = _get_client()

    try:
        client.delete_analyzer(ANALYZER_ID)
        print(f"Analyzer '{ANALYZER_ID}' deleted.")
    except ResourceNotFoundError:
        print(f"Analyzer '{ANALYZER_ID}' not found (already deleted).")


def status() -> bool:
    """Check if the kb-image-analyzer exists in Content Understanding."""
    client = _get_client()

    try:
        analyzer = client.get_analyzer(ANALYZER_ID)
        print(f"  ✔ Analyzer '{analyzer.analyzer_id}' exists (status: {analyzer.status})")
        if hasattr(analyzer, "field_schema") and analyzer.field_schema:
            fs = analyzer.field_schema
            fields = fs.get("fields", {}) if hasattr(fs, "get") else getattr(fs, "fields", {}) or {}
            if isinstance(fields, dict) and fields:
                print(f"    Fields: {', '.join(fields.keys())}")
        return True
    except ResourceNotFoundError:
        print(f"  ✘ Analyzer '{ANALYZER_ID}' not found")
        return False


def main() -> None:
    commands = ("setup", "deploy", "delete", "status")
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(f"Usage: python -m manage_analyzers [{' | '.join(commands)}]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    if command == "setup":
        setup()
    elif command == "deploy":
        deploy()
    elif command == "delete":
        delete()
    elif command == "status":
        status()


if __name__ == "__main__":
    main()
