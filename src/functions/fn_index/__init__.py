"""fn-index — Stage 2: Markdown → AI Search index.

Orchestrates chunking, embedding, and indexing of a processed KB article.

Steps:
    1. Read ``article.md`` from the article directory
    2. Chunk by Markdown headers via :mod:`fn_index.chunker`
    3. Embed all chunks via :mod:`fn_index.embedder`
    4. Push to AI Search via :mod:`fn_index.indexer`
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fn_index import chunker, embedder, indexer, summarizer

logger = logging.getLogger(__name__)


def run(article_path: str) -> None:
    """Index a single processed KB article into Azure AI Search.

    Reads ``metadata.json`` from the article folder to discover index fields
    (e.g. ``department``).  The field names in ``metadata.json`` correspond
    directly to fields in the AI Search index.

    Parameters
    ----------
    article_path:
        Path to the processed article folder (contains ``article.md``,
        ``metadata.json``, and optionally ``images/``).
    """
    article_dir = Path(article_path).resolve()
    article_id = article_dir.name

    # Read metadata.json written by the convert step
    metadata_file = article_dir / "metadata.json"
    metadata: dict = {}
    if metadata_file.exists():
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

    department = metadata.get("department", "")

    logger.info("fn-index: %s (department=%s)", article_id, department)

    # 1. Read article.md
    article_md = article_dir / "article.md"
    if not article_md.exists():
        raise FileNotFoundError(f"article.md not found in {article_dir}")
    markdown = article_md.read_text(encoding="utf-8")

    # 2. Chunk
    chunks = chunker.chunk_article(markdown)
    logger.info("Chunked into %d sections", len(chunks))

    # 3. Embed
    embedded_chunks = embedder.embed_chunks(chunks)
    logger.info("Embedded %d chunks", len(embedded_chunks))

    # 4. Summarize
    summaries = summarizer.summarize_chunks(chunks)
    logger.info("Summarized %d chunks", len(summaries))

    # 5. Index
    indexed_at = datetime.now(timezone.utc).isoformat()
    indexer.ensure_index_exists()
    indexer.index_chunks(
        article_id,
        embedded_chunks,
        department=department,
        summaries=summaries,
        indexed_at=indexed_at,
    )
    logger.info("fn-index complete: %s (%d chunks indexed)", article_id, len(embedded_chunks))
