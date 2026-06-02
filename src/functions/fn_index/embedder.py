"""Embedding — call Microsoft Foundry text-embedding-3-small.

Embeds chunk text via the ``azure-ai-inference`` SDK using the
``text-embedding-3-small`` model (1536 dimensions).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from shared.client_factories import EmbeddingBackend, create_embedding_backend

from shared.config import config

if TYPE_CHECKING:
    from fn_index.chunker import Chunk

logger = logging.getLogger(__name__)

_client: EmbeddingBackend | None = None


def _get_client() -> EmbeddingBackend:
    """Lazy singleton for the embedding backend."""
    global _client
    if _client is None:
        _client = create_embedding_backend()
    return _client


def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns an environment-specific vector."""
    client = _get_client()
    vector = client.embed([text])[0]
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

    if config.is_dev:
        embeddings = [client.embed([text])[0] for text in texts]
    else:
        embeddings = client.embed(texts)

    results: list[dict] = []
    for chunk, embedding in zip(chunks, embeddings):
        results.append(
            {
                "content": chunk.content,
                "title": chunk.title,
                "section_header": chunk.section_header,
                "image_refs": chunk.image_refs,
                "content_vector": embedding,
            }
        )

    logger.info("Embedded %d chunks (model=%s)", len(results), config.embedding_deployment_name)
    return results
