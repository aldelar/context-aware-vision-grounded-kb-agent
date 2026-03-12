"""Send a PDF to Mistral Document AI OCR on Azure Foundry and return the raw response.

Uses the ``/providers/mistral/azure/ocr`` endpoint on the Azure AI Services
(Foundry) host.  Authenticates via ``DefaultAzureCredential`` (managed
identity in Azure, ``az login`` locally).
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


def _derive_foundry_endpoint(endpoint: str) -> str:
    """Derive the Foundry Services endpoint from a Cognitive Services endpoint.

    Microsoft Foundry models (Mistral, Cohere, etc.) use the
    ``https://<name>.services.ai.azure.com`` domain, while the classic
    Cognitive Services / OpenAI endpoint uses
    ``https://<name>.cognitiveservices.azure.com``.

    If the endpoint already uses ``services.ai.azure.com``, it is returned
    as-is.
    """
    endpoint = endpoint.rstrip("/")
    if ".services.ai.azure.com" in endpoint:
        return endpoint
    # Extract resource name from https://<name>.cognitiveservices.azure.com
    # or https://<name>.openai.azure.com
    try:
        host = endpoint.split("//")[1].split(".")[0]
    except (IndexError, AttributeError):
        raise ValueError(
            f"Cannot derive Foundry endpoint from: {endpoint!r}. "
            "Set AI_SERVICES_ENDPOINT to a valid Azure AI Services URL."
        )
    return f"https://{host}.services.ai.azure.com"


def ocr_pdf(pdf_path: Path, endpoint: str, deployment: str) -> dict:
    """Send a PDF to Mistral OCR via Azure Foundry and return the parsed JSON response.

    The endpoint can be either a Cognitive Services endpoint
    (``https://<name>.cognitiveservices.azure.com``) or a Foundry Services
    endpoint (``https://<name>.services.ai.azure.com``).  The function
    derives the correct Foundry URL automatically.

    Args:
        pdf_path: Path to the PDF file to process.
        endpoint: Azure AI Services or Foundry endpoint base URL.
        deployment: Model deployment name (e.g., ``mistral-document-ai-2512``).

    Returns:
        The raw JSON response from the OCR API.

    Raises:
        httpx.HTTPStatusError: If the OCR call fails.
    """
    pdf_bytes = pdf_path.read_bytes()
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    credential = DefaultAzureCredential()
    token = credential.get_token("https://cognitiveservices.azure.com/.default").token

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    body = {
        "model": deployment,
        "document": {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{pdf_b64}",
        },
        "include_image_base64": True,
    }

    foundry_url = _derive_foundry_endpoint(endpoint)
    ocr_url = f"{foundry_url}/providers/mistral/azure/ocr"

    logger.info("Calling Mistral OCR: %s  (model=%s)", ocr_url, deployment)
    logger.info("PDF size: %d bytes", len(pdf_bytes))

    resp = httpx.post(ocr_url, json=body, headers=headers, timeout=180)
    logger.info("Response status: %s", resp.status_code)

    if not resp.is_success:
        logger.error("OCR error body: %s", resp.text[:500])
        resp.raise_for_status()

    return resp.json()
