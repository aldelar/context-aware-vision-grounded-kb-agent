"""MCP web search server — exposes web_search tool via SSE transport.

Environment-driven implementation:
  - ``ENVIRONMENT=dev`` → fetch/scrape (no Azure costs)
  - ``ENVIRONMENT=prod`` → Bing Grounding API
"""

from __future__ import annotations

import json
import logging
import os

from mcp.server import Server
from mcp.types import TextContent, Tool

from mcp_web_search.whitelist import load_whitelist

logger = logging.getLogger(__name__)

_ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev").strip().lower()

server = Server("mcp-web-search")
_whitelist: list[str] = []


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="web_search",
            description="Search whitelisted web sites for information. Returns structured results with source URLs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query — use natural language describing what information is needed",
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "web_search":
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    query = arguments.get("query", "").strip()
    if not query:
        return [TextContent(type="text", text=json.dumps({"error": "Query is required"}))]

    logger.info("web_search(query='%s', env=%s)", query[:80], _ENVIRONMENT)

    if _ENVIRONMENT == "prod":
        from mcp_web_search.search_prod import prod_web_search
        result = await prod_web_search(query, _whitelist)
    else:
        from mcp_web_search.search_dev import dev_web_search
        result = await dev_web_search(query, _whitelist)

    return [TextContent(type="text", text=result)]


def main() -> None:
    """Run the MCP server with SSE transport."""
    global _whitelist
    _whitelist = load_whitelist()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )

    port = int(os.environ.get("MCP_PORT", "8089"))
    logger.info("Starting MCP web search server (env=%s, port=%d)", _ENVIRONMENT, port)

    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from contextlib import asynccontextmanager
    from collections.abc import AsyncIterator
    from starlette.applications import Starlette
    from starlette.routing import Mount
    import uvicorn

    session_manager = StreamableHTTPSessionManager(server)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    app = Starlette(
        routes=[
            Mount("/mcp", app=session_manager.handle_request),
        ],
        lifespan=lifespan,
    )

    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
