"""Embedding — call Microsoft Foundry text-embedding-3-small.

Embeds chunk text via the ``azure-ai-inference`` SDK using the
``text-embedding-3-small`` model (1536 dimensions).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from azure.ai.inference import EmbeddingsClient
from azure.identity import DefaultAzureCredential

from shared.config import config

if TYPE_CHECKING:
    from fn_index.chunker import Chunk

logger = logging.getLogger(__name__)

_client: EmbeddingsClient | None = None


def _get_client() -> EmbeddingsClient:
    """Lazy singleton for the embeddings client."""
    global _client
    if _client is None:
        # Azure AI Services endpoint → must include /openai/deployments/{model}
        endpoint = config.ai_services_endpoint.rstrip("/")
        model_endpoint = f"{endpoint}/openai/deployments/{config.embedding_deployment_name}"
        _client = EmbeddingsClient(
            endpoint=model_endpoint,
            credential=DefaultAzureCredential(),
            credential_scopes=["https://cognitiveservices.azure.com/.default"],
        )
    return _client


def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns a 1536-dimension vector."""
    client = _get_client()
    response = client.embed(
        input=[text],
    )
    vector = response.data[0].embedding
    logger.debug("Embedded %d chars → %d-dim vector", len(text), len(vector))
    return vector


def embed_chunks(chunks: list[Chunk]) -> list[dict]:
    """Embed all chunks and return dicts with ``content_vector`` populated.

    Parameters
    ----------
    chunks:
        List of :class:`Chunk` objects from the chunker.

    Returns
    -------
    list[dict]
        Each dict contains all chunk fields plus ``content_vector``.
    """
    texts = [c.content for c in chunks]
    client = _get_client()

    # Batch embedding — send all texts at once
    response = client.embed(
        input=texts,
    )

    results: list[dict] = []
    for chunk, embedding_item in zip(chunks, response.data):
        results.append(
            {
                "content": chunk.content,
                "title": chunk.title,
                "section_header": chunk.section_header,
                "image_refs": chunk.image_refs,
                "content_vector": embedding_item.embedding,
            }
        )

    logger.info("Embedded %d chunks (model=%s)", len(results), config.embedding_deployment_name)
    return results
