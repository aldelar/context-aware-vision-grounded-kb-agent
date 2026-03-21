"""AI Search hybrid query tool — vector + keyword search against kb-articles index.

Embeds the user query with ``text-embedding-3-small`` and performs a hybrid search
(vector similarity on ``content_vector`` + keyword search on ``content``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from opentelemetry import trace

from azure.ai.inference import EmbeddingsClient
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from agent.config import config

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

VECTOR_DIMENSIONS = 1536


@dataclass
class SearchResult:
    """A single search result from the kb-articles index."""

    id: str
    article_id: str
    chunk_index: int
    content: str
    title: str
    section_header: str
    department: str = ""
    summary: str = ""
    indexed_at: str = ""
    image_urls: list[str] = field(default_factory=list)
    score: float = 0.0


# ---------------------------------------------------------------------------
# Module-level clients (config is available at import time)
# ---------------------------------------------------------------------------

_credential = DefaultAzureCredential()

_embedding_endpoint = (
    f"{config.ai_services_endpoint.rstrip('/')}/openai/deployments/{config.embedding_deployment_name}"
)
_embeddings_client = EmbeddingsClient(
    endpoint=_embedding_endpoint,
    credential=_credential,
    credential_scopes=["https://cognitiveservices.azure.com/.default"],
)

_search_client = SearchClient(
    endpoint=config.search_endpoint,
    index_name=config.search_index_name,
    credential=_credential,
)


def _embed_query(query: str) -> list[float]:
    """Embed a query string. Returns a 1536-dimension vector."""
    response = _embeddings_client.embed(input=[query])
    vector = response.data[0].embedding
    logger.debug("Embedded query (%d chars) → %d-dim vector", len(query), len(vector))
    return vector


def search_kb(query: str, top: int = 5, *, security_filter: str | None = None) -> list[SearchResult]:
    """Perform hybrid search (vector + keyword) against the kb-articles index.

    Parameters
    ----------
    query:
        Natural language search query.
    top:
        Maximum number of results to return.
    security_filter:
        Optional OData filter expression for department-scoped results.

    Returns
    -------
    list[SearchResult]
        Ordered by relevance score (descending).
    """
    if not query.strip():
        return []

    # Embed the query for vector search
    query_vector = _embed_query(query)

    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=top,
        fields="content_vector",
    )

    with tracer.start_as_current_span("search_kb") as span:
        span.set_attribute("search.query", query[:200])
        span.set_attribute("search.top", top)
        if security_filter:
            span.set_attribute("search.filter", security_filter)

        results = _search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            select=["id", "article_id", "chunk_index", "content", "title", "section_header", "image_urls", "department", "summary", "indexed_at"],
            top=top,
            filter=security_filter,
        )

        search_results: list[SearchResult] = []
        for result in results:
            search_results.append(
                SearchResult(
                    id=result["id"],
                    article_id=result["article_id"],
                    chunk_index=result.get("chunk_index", 0),
                    content=result["content"],
                    title=result.get("title", ""),
                    section_header=result.get("section_header", ""),
                    department=result.get("department", ""),
                    summary=result.get("summary", ""),
                    indexed_at=result.get("indexed_at", ""),
                    image_urls=result.get("image_urls") or [],
                    score=result.get("@search.score", 0.0),
                )
            )

        span.set_attribute("search.result_count", len(search_results))

    logger.info(
        "Hybrid search for '%s' → %d results (top=%d)",
        query[:80],
        len(search_results),
        top,
    )
    return search_results
