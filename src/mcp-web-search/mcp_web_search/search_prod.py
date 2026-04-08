"""Prod-mode web search using Azure Bing Web Search API.

Filters results to whitelisted domains using the ``site:`` operator.
Requires ``BING_SEARCH_API_KEY`` environment variable.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BING_ENDPOINT = os.environ.get(
    "BING_SEARCH_ENDPOINT",
    "https://api.bing.microsoft.com/v7.0/search",
)
_MAX_RESULTS = 5


def validate_prod_search_configuration() -> str:
    """Validate required prod-mode configuration and return the API key."""
    api_key = os.environ.get("BING_SEARCH_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("BING_SEARCH_API_KEY is required for prod web search")
    return api_key


async def prod_web_search(query: str, whitelist: list[str]) -> str:
    """Search using Bing Web Search API, filtering to whitelisted sites.

    Returns JSON matching the MCP tool contract.
    """
    if not whitelist:
        raise RuntimeError("No whitelisted sites configured for prod web search")

    # Build site-scoped query
    site_filter = " OR ".join(f"site:{site}" for site in whitelist)
    scoped_query = f"{query} ({site_filter})"

    api_key = validate_prod_search_configuration()

    headers = {"Ocp-Apim-Subscription-Key": api_key}

    results: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _BING_ENDPOINT,
                params={"q": scoped_query, "count": str(_MAX_RESULTS), "mkt": "en-US"},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            web_pages = data.get("webPages", {}).get("value", [])
            for idx, page in enumerate(web_pages[:_MAX_RESULTS], start=1):
                results.append({
                    "ref_number": idx,
                    "title": page.get("name", ""),
                    "snippet": page.get("snippet", ""),
                    "source_url": page.get("url", ""),
                    "anchor": "",
                })
    except Exception as exc:
        logger.error("Bing web search failed", exc_info=True)
        raise RuntimeError("Bing search failed") from exc

    summary = f"{len(results)} results from {', '.join(whitelist)}"
    return json.dumps({"results": results, "summary": summary}, ensure_ascii=False)
