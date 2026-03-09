"""Generate image descriptions using GPT-4.1 vision on Azure Foundry.

Uses the same prompt schema as the CU ``kb-image-analyzer`` custom analyzer
and ``fn_convert_mistral`` to produce comparable image descriptions.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

logger = logging.getLogger(__name__)

IMAGE_PROMPT = (
    "Analyze this image from a knowledge base article. The image may be an architecture diagram, "
    "flowchart, network topology, conceptual illustration, chart, photograph, or a software UI "
    "screenshot. Do NOT assume it is a screenshot unless it clearly shows a software user interface.\n"
    "\n"
    "Produce a structured description with:\n"
    "\n"
    "1. **Description**: A concise paragraph describing what the image shows, suitable for embedding "
    "in a search index to help users find this content via natural language queries. Focus on the key "
    "concepts, components, relationships, and data flows depicted.\n"
    "\n"
    "2. **UIElements**: ONLY if the image is a software UI screenshot, list the UI elements visible "
    "(buttons, menus, tabs, form fields, navigation items). If the image is not a UI screenshot "
    '(e.g., it is a diagram, chart, or illustration), say "None".\n'
    "\n"
    "3. **NavigationPath**: ONLY if the image is a software UI screenshot, describe the navigation "
    'path to reach this screen (e.g., "Settings > Account > Security"). If the image is not a UI '
    'screenshot, say "N/A".\n'
    "\n"
    "Respond in plain text, not JSON."
)


def describe_image(image_path: Path, endpoint: str, deployment: str) -> str:
    """Describe a single image using GPT-4.1 vision.

    Args:
        image_path: Path to the image file.
        endpoint: Azure AI Services endpoint.
        deployment: GPT model deployment name (e.g., ``gpt-4.1``).

    Returns:
        The model's text description of the image.
    """
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
    image_stems: list[str],
    staging_dir: Path,
    endpoint: str,
    deployment: str,
) -> dict[str, str]:
    """Describe all images by their filename stems.

    Searches for image files in both ``staging_dir/images/`` and
    ``staging_dir/`` directly, supporting multiple extensions.

    Args:
        image_stems: List of unique image filename stems to describe.
        staging_dir: Directory containing the original staged images.
        endpoint: Azure AI Services endpoint.
        deployment: GPT model deployment name.

    Returns:
        Dict mapping image stem → description text.
    """
    descriptions: dict[str, str] = {}

    for stem in image_stems:
        image_path = _find_image_file(staging_dir, stem)
        if not image_path:
            logger.warning("Image not found for stem: %s", stem)
            continue

        logger.info("Describing image: %s", stem)
        description = describe_image(image_path, endpoint, deployment)
        descriptions[stem] = description

    return descriptions


def _find_image_file(staging_dir: Path, stem: str) -> Path | None:
    """Find an image file by stem in the staging directory.

    Searches ``images/`` subfolder first, then the root directory.
    Supports ``.png``, ``.jpg``, ``.jpeg``, ``.gif``, ``.image`` extensions.
    """
    extensions = [".png", ".jpg", ".jpeg", ".gif", ".image"]
    for search_dir in [staging_dir / "images", staging_dir]:
        for ext in extensions:
            candidate = search_dir / f"{stem}{ext}"
            if candidate.exists():
                return candidate
    return None
