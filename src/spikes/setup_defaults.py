"""One-time setup: configure default model deployments for Content Understanding.

Run this once per Microsoft Foundry resource to map your deployed models
to those required by prebuilt analyzers.

Usage:
    uv run python setup_defaults.py
"""

from azure.ai.contentunderstanding import ContentUnderstandingClient
from config import load_config, get_credential


def setup_defaults() -> None:
    config = load_config()
    credential = get_credential(config)

    # Setup defaults on the Content Understanding resource
    client = ContentUnderstandingClient(
        endpoint=config["CONTENTUNDERSTANDING_ENDPOINT"],
        credential=credential,
    )

    # Map model names to your deployment names
    model_deployments = {
        "gpt-4.1": config["GPT_4_1_DEPLOYMENT"],
        "gpt-4.1-mini": config["GPT_4_1_MINI_DEPLOYMENT"],
        "text-embedding-3-small": config["TEXT_EMBEDDING_3_SMALL_DEPLOYMENT"],
    }

    print("Updating default model deployments...")
    client.update_defaults(model_deployments=model_deployments)

    # Verify
    defaults = client.get_defaults()
    print("Current model deployment defaults:")
    for model_name, deployment_name in defaults.model_deployments.items():
        print(f"  {model_name} -> {deployment_name}")

    print("\nSetup complete. You can now use prebuilt analyzers.")


if __name__ == "__main__":
    setup_defaults()
