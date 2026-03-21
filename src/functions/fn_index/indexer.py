"""Search indexer — push chunks to Azure AI Search.

Creates the ``kb-articles`` index (with vector search config) if it doesn't
exist, then merges-or-uploads chunk documents.
"""

from __future__ import annotations

import logging

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

from shared.config import config

logger = logging.getLogger(__name__)

VECTOR_DIMENSIONS = 1536
VECTOR_PROFILE_NAME = "default-profile"
ALGORITHM_CONFIG_NAME = "default-hnsw"


def ensure_index_exists() -> None:
    """Create the ``kb-articles`` index if it doesn't exist.

    Uses HNSW algorithm for vector search.  Idempotent — safe to call
    multiple times.
    """
    credential = DefaultAzureCredential()
    client = SearchIndexClient(
        endpoint=config.search_endpoint,
        credential=credential,
    )

    index_name = config.search_index_name

    # Check if index already exists
    try:
        client.get_index(index_name)
        logger.info("Index '%s' already exists", index_name)
        return
    except Exception:
        pass  # Index doesn't exist, create it

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(
            name="article_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="chunk_index",
            type=SearchFieldDataType.Int32,
            sortable=True,
        ),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=VECTOR_DIMENSIONS,
            vector_search_profile_name=VECTOR_PROFILE_NAME,
        ),
        SimpleField(
            name="image_urls",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=False,
        ),
        SimpleField(
            name="source_url",
            type=SearchFieldDataType.String,
            filterable=False,
        ),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SimpleField(
            name="section_header",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="key_topics",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
        ),
        SimpleField(
            name="department",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="summary",
            type=SearchFieldDataType.String,
            filterable=False,
        ),
        SimpleField(
            name="indexed_at",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name=ALGORITHM_CONFIG_NAME)],
        profiles=[
            VectorSearchProfile(
                name=VECTOR_PROFILE_NAME,
                algorithm_configuration_name=ALGORITHM_CONFIG_NAME,
            )
        ],
    )

    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search,
    )

    client.create_index(index)
    logger.info("Created index '%s' with vector search", index_name)


def index_chunks(
    article_id: str,
    chunks: list[dict],
    *,
    department: str = "",
    summaries: list[str] | None = None,
    indexed_at: str = "",
) -> None:
    """Push chunk documents to AI Search using merge-or-upload.

    Parameters
    ----------
    article_id:
        Article folder name (used for ``article_id`` field and as
        part of the document ``id``).
    chunks:
        List of dicts with ``content``, ``content_vector``, ``title``,
        ``section_header``, ``image_refs``.
    department:
        Department name (e.g. ``"engineering"``) for the filterable field.
    summaries:
        Optional per-chunk summaries (same order as chunks).
    indexed_at:
        ISO-8601 timestamp for this indexing run.
    """
    credential = DefaultAzureCredential()
    client = SearchClient(
        endpoint=config.search_endpoint,
        index_name=config.search_index_name,
        credential=credential,
    )

    documents = []
    for i, chunk in enumerate(chunks):
        doc = {
            "id": f"{article_id}_{i}",
            "article_id": article_id,
            "chunk_index": i,
            "content": chunk["content"],
            "content_vector": chunk["content_vector"],
            "image_urls": [
                f"images/{ref}" for ref in chunk.get("image_refs", [])
            ],
            "source_url": "",
            "title": chunk.get("title", ""),
            "section_header": chunk.get("section_header", ""),
            "key_topics": [],
            "department": department,
            "summary": summaries[i] if summaries and i < len(summaries) else "",
            "indexed_at": indexed_at,
        }
        documents.append(doc)

    result = client.merge_or_upload_documents(documents=documents)
    succeeded = sum(1 for r in result if r.succeeded)
    logger.info(
        "Indexed %d/%d chunks for article '%s'",
        succeeded,
        len(documents),
        article_id,
    )
