"""Web search using the Microsoft Learn search API.

The MCP server uses the same Microsoft Learn-backed implementation in both
dev and prod. Results are constrained to Microsoft Learn documentation pages.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_SEARCH_TIMEOUT = 15.0
_MAX_RESULTS = 5
_MAX_SNIPPET_LEN = 500
_MICROSOFT_LEARN_HOST = "learn.microsoft.com"

# Microsoft Learn free search API
_LEARN_SEARCH_URL = "https://learn.microsoft.com/api/search"


async def web_search(query: str) -> str:
    """Search Microsoft Learn documentation.

    Returns JSON matching the MCP tool contract.
    """
    results: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT) as client:
            resp = await client.get(
                _LEARN_SEARCH_URL,
                params={
                    "search": query,
                    "locale": "en-us",
                    "topResults": str(_MAX_RESULTS * 2),
                },
            )
            resp.raise_for_status()
            data = resp.json()

            search_results = data.get("results", [])
            index = 0
            for item in search_results:
                url = item.get("url", "")
                if not _is_microsoft_learn_url(url):
                    continue

                index += 1
                description = item.get("description", "")
                results.append({
                    "ref_number": index,
                    "title": item.get("title", ""),
                    "snippet": description[:_MAX_SNIPPET_LEN] if description else "",
                    "source_url": url,
                    "anchor": "",
                })
                if index >= _MAX_RESULTS:
                    break
    except Exception as exc:
        logger.error("Web search failed", exc_info=True)
        raise RuntimeError("Search failed") from exc

    summary = f"{len(results)} results from {_MICROSOFT_LEARN_HOST}"
    return json.dumps({"results": results, "summary": summary}, ensure_ascii=False)


def _is_microsoft_learn_url(url: str) -> bool:
    """Return whether a URL points to Microsoft Learn."""
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return False
    return hostname == _MICROSOFT_LEARN_HOST or hostname.endswith(f".{_MICROSOFT_LEARN_HOST}")