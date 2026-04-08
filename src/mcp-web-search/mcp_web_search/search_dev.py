"""Dev-mode web search using Microsoft Learn search API.

Searches whitelisted sites via the free learn.microsoft.com search API.
Used in local development to avoid Azure Bing API costs.
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

# Microsoft Learn free search API
_LEARN_SEARCH_URL = "https://learn.microsoft.com/api/search"


async def dev_web_search(query: str, whitelist: list[str]) -> str:
    """Search whitelisted sites via Microsoft Learn search API.

    Returns JSON matching the MCP tool contract.
    """
    if not whitelist:
        raise RuntimeError("No whitelisted sites configured for dev web search")

    results: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT) as client:
            resp = await client.get(
                _LEARN_SEARCH_URL,
                params={
                    "search": query,
                    "locale": "en-us",
                    "topResults": str(_MAX_RESULTS * 2),  # fetch extra, filter by whitelist
                },
            )
            resp.raise_for_status()
            data = resp.json()

            search_results = data.get("results", [])
            idx = 0
            for item in search_results:
                url = item.get("url", "")
                if not _is_whitelisted(url, whitelist):
                    continue

                idx += 1
                description = item.get("description", "")
                results.append({
                    "ref_number": idx,
                    "title": item.get("title", ""),
                    "snippet": description[:_MAX_SNIPPET_LEN] if description else "",
                    "source_url": url,
                    "anchor": "",
                })
                if idx >= _MAX_RESULTS:
                    break
    except Exception as exc:
        logger.error("Dev web search failed", exc_info=True)
        raise RuntimeError("Search failed") from exc

    summary = f"{len(results)} results from {', '.join(whitelist)}"
    return json.dumps({"results": results, "summary": summary}, ensure_ascii=False)


def _is_whitelisted(url: str, whitelist: list[str]) -> bool:
    """Check if a URL belongs to a whitelisted domain."""
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return False
    return any(hostname == site or hostname.endswith(f".{site}") for site in whitelist)
