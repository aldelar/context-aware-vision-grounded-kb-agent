"""Chunk summarizer — generate 1–2 sentence summaries via gpt-4.1-mini.

Used at index time to create compact per-chunk summaries stored in AI Search.
These summaries serve as compacted representations when the agent's
ToolResultCompactionStrategy replaces older tool output.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from azure.ai.inference import ChatCompletionsClient
from azure.identity import DefaultAzureCredential

import os

from shared.config import config

if TYPE_CHECKING:
    from fn_index.chunker import Chunk

logger = logging.getLogger(__name__)

_SUMMARY_DEPLOYMENT = os.environ.get("SUMMARY_DEPLOYMENT_NAME", "gpt-4.1-mini")

_client: ChatCompletionsClient | None = None


def _get_client() -> ChatCompletionsClient:
    """Lazy singleton for the chat completions client."""
    global _client
    if _client is None:
        endpoint = config.ai_services_endpoint.rstrip("/")
        model_endpoint = f"{endpoint}/openai/deployments/{_SUMMARY_DEPLOYMENT}"
        _client = ChatCompletionsClient(
            endpoint=model_endpoint,
            credential=DefaultAzureCredential(),
            credential_scopes=["https://cognitiveservices.azure.com/.default"],
        )
    return _client


def summarize_chunk(chunk_content: str, title: str, section_header: str) -> str:
    """Generate a 1–2 sentence summary for a chunk.

    Parameters
    ----------
    chunk_content:
        The full text content of the chunk.
    title:
        Article title for context.
    section_header:
        Section header for context.

    Returns
    -------
    str
        A concise 1–2 sentence summary.
    """
    prompt = (
        f"Summarize the following knowledge base content in 1-2 sentences. "
        f"Be concise and capture the key information.\n\n"
        f"Article: {title}\n"
        f"Section: {section_header}\n\n"
        f"Content:\n{chunk_content[:2000]}"
    )
    try:
        client = _get_client()
        response = client.complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.0,
        )
        summary = response.choices[0].message.content.strip()
        logger.debug("Summarized chunk (%s > %s): %s", title, section_header, summary[:80])
        return summary
    except Exception:
        logger.warning("Failed to summarize chunk (%s > %s)", title, section_header, exc_info=True)
        return ""


def summarize_chunks(chunks: list[Chunk]) -> list[str]:
    """Generate summaries for all chunks.

    Parameters
    ----------
    chunks:
        List of Chunk objects from the chunker.

    Returns
    -------
    list[str]
        Summaries in the same order as the input chunks.
    """
    summaries = []
    for chunk in chunks:
        summary = summarize_chunk(chunk.content, chunk.title, chunk.section_header)
        summaries.append(summary)
    logger.info("Generated %d chunk summaries", len(summaries))
    return summaries
