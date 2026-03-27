"""AI Search hybrid query tool — vector + keyword search against kb-articles index.

Embeds the user query with ``text-embedding-3-small`` and performs a hybrid search
(vector similarity on ``content_vector`` + keyword search on ``content``).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from opentelemetry import trace

from azure.search.documents.models import VectorizedQuery

from agent.client_factories import (
    EmbeddingBackend,
    create_query_embedding_backend,
    create_search_client,
)
from agent.config import config

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

VECTOR_DIMENSIONS = config.embedding_vector_dimensions


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


_embedding_backend: EmbeddingBackend | None = None
_search_client = None


def _get_embedding_backend() -> EmbeddingBackend:
    global _embedding_backend
    if _embedding_backend is None:
        _embedding_backend = create_query_embedding_backend()
    return _embedding_backend


def _get_search_client():
    global _search_client
    if _search_client is None:
        _search_client = create_search_client()
    return _search_client


def _embed_query(query: str) -> list[float]:
    """Embed a query string. Returns an environment-specific vector."""
    vector = _get_embedding_backend().embed([query])[0]
    logger.debug("Embedded query (%d chars) → %d-dim vector", len(query), len(vector))
    return vector


def _normalize_security_filter_for_local_search(security_filter: str | None) -> str | None:
    """Rewrite `search.in(...)` filters to simple OData OR clauses for local emulators.

    The Azure AI Search simulator used for local dev does not reliably honor
    `search.in(...)` in the same way the managed service does. For dev-mode
    integration tests, convert department filters to an equivalent `eq`/`or`
    expression while leaving production behavior unchanged.
    """
    if not security_filter or not config.is_dev:
        return security_filter

    match = re.fullmatch(r"search\.in\(department, '([^']*)', ','\)", security_filter)
    if not match:
        return security_filter

    departments = [part.strip() for part in match.group(1).split(",") if part.strip()]
    if not departments:
        return None
    if len(departments) == 1:
        return f"department eq '{departments[0]}'"

    joined = " or ".join(f"department eq '{department}'" for department in departments)
    return f"({joined})"


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

    security_filter = _normalize_security_filter_for_local_search(security_filter)

    # Embed the query for vector search
    query_vector = _embed_query(query)

    vector_query = VectorizedQuery(
        vector=query_vector,
        k=top,
        fields="content_vector",
    )

    with tracer.start_as_current_span("search_kb") as span:
        span.set_attribute("search.query", query[:200])
        span.set_attribute("search.top", top)
        if security_filter:
            span.set_attribute("search.filter", security_filter)

        results = _get_search_client().search(
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
