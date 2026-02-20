"""Step 4: Generate image descriptions using GPT-4.1 vision on Azure Foundry."""

import base64
import logging
from pathlib import Path

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

logger = logging.getLogger(__name__)

IMAGE_PROMPT = (
    "Analyze this screenshot from a knowledge base article. Produce a structured description with:\n"
    "\n"
    "1. **Description**: A concise paragraph describing what the image shows, suitable for embedding "
    "in a search index to help users find this content via natural language queries.\n"
    "\n"
    '2. **UIElements**: List any UI elements visible (buttons, menus, tabs, form fields, navigation items). '
    'If none, say "None".\n'
    "\n"
    "3. **NavigationPath**: If the image shows a software UI, describe the navigation path to reach this "
    'screen (e.g., "Settings > Account > Security"). If not applicable, say "N/A".\n'
    "\n"
    "Respond in plain text, not JSON."
)


def describe_image(image_path: Path, endpoint: str, deployment: str) -> str:
    """Describe a single image using GPT-4.1 vision."""
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2025-03-01-preview",
    )

    image_data = image_path.read_bytes()
    encoded = base64.b64encode(image_data).decode("utf-8")

    ext = image_path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif ext == ".png":
        media_type = "image/png"
    else:
        media_type = "image/png"

    data_uri = f"data:{media_type};base64,{encoded}"

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": IMAGE_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
        max_tokens=500,
    )

    return response.choices[0].message.content


def describe_all_images(
    image_mapping: dict[str, str],
    staging_dir: Path,
    endpoint: str,
    deployment: str,
) -> dict[str, str]:
    """Describe all images referenced in the image mapping."""
    descriptions: dict[str, str] = {}

    for placeholder, source_filename in image_mapping.items():
        image_path = staging_dir / "images" / source_filename
        if not image_path.exists():
            image_path = staging_dir / source_filename
        if not image_path.exists():
            logger.warning("Image not found for placeholder %s: %s", placeholder, source_filename)
            continue

        description = describe_image(image_path, endpoint, deployment)
        descriptions[source_filename] = description
        print(f"Described: {source_filename}")

    return descriptions
