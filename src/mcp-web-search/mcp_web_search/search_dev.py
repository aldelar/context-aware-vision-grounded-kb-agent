"""Dev-mode web search implementation using HTTP fetch + HTML scraping.

Searches whitelisted sites by fetching pages and extracting content.
Used in local development to avoid Azure Bing API costs.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_SEARCH_TIMEOUT = 15.0
_MAX_RESULTS = 5
_MAX_SNIPPET_LEN = 500


async def dev_web_search(query: str, whitelist: list[str]) -> str:
    """Search whitelisted sites via Google site-scoped search and scrape results.

    Returns JSON matching the MCP tool contract.
    """
    if not whitelist:
        return json.dumps({"results": [], "summary": "No whitelisted sites configured"})

    site_filter = " OR ".join(f"site:{site}" for site in whitelist)
    search_url = f"https://www.google.com/search?q={quote_plus(query + ' ' + site_filter)}&num={_MAX_RESULTS}"

    results: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(
            timeout=_SEARCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MCPWebSearch/1.0)"},
        ) as client:
            resp = await client.get(search_url)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            links = _extract_search_links(soup, whitelist)

            for idx, link_info in enumerate(links[:_MAX_RESULTS], start=1):
                snippet = await _fetch_page_snippet(client, link_info["url"])
                results.append({
                    "ref_number": idx,
                    "title": link_info["title"],
                    "snippet": snippet,
                    "source_url": link_info["url"],
                    "anchor": link_info.get("anchor", ""),
                })
    except Exception:
        logger.error("Dev web search failed", exc_info=True)
        return json.dumps({"results": [], "summary": "Search failed"})

    summary = f"{len(results)} results from {', '.join(whitelist)}"
    return json.dumps({"results": results, "summary": summary}, ensure_ascii=False)


def _extract_search_links(soup: BeautifulSoup, whitelist: list[str]) -> list[dict[str, str]]:
    """Extract links from Google search results that match whitelisted domains."""
    links: list[dict[str, str]] = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if not href.startswith("http"):
            continue
        try:
            parsed = urlparse(href)
            hostname = (parsed.hostname or "").lower()
        except Exception:
            continue

        if not any(hostname == s or hostname.endswith(f".{s}") for s in whitelist):
            continue

        title = a_tag.get_text(strip=True) or parsed.path.split("/")[-1]
        if not title or len(title) < 3:
            continue

        anchor = parsed.fragment or ""
        links.append({"url": href, "title": title[:200], "anchor": anchor})

    return links


async def _fetch_page_snippet(client: httpx.AsyncClient, url: str) -> str:
    """Fetch a page and extract the first meaningful text paragraph."""
    try:
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
    except Exception:
        logger.debug("Failed to fetch page: %s", url)
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove nav, header, footer, script, style
    for tag in soup.find_all(["nav", "header", "footer", "script", "style", "aside"]):
        tag.decompose()

    # Try to find main content
    main = soup.find("main") or soup.find("article") or soup.find("div", role="main") or soup.body
    if not main:
        return ""

    paragraphs = main.find_all("p")
    text_parts: list[str] = []
    total_len = 0
    for p in paragraphs:
        text = p.get_text(strip=True)
        if len(text) < 20:
            continue
        text_parts.append(text)
        total_len += len(text)
        if total_len >= _MAX_SNIPPET_LEN:
            break

    return " ".join(text_parts)[:_MAX_SNIPPET_LEN]
