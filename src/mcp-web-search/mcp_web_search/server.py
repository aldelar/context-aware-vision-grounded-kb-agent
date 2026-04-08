"""MCP web search server — exposes web_search via stateless Streamable HTTP.

Uses the Microsoft Learn search API to search whitelisted documentation sites.
"""

from __future__ import annotations

import json
import logging
import os

from mcp.server import Server
from mcp.types import TextContent, Tool

from mcp_web_search.whitelist import load_whitelist

logger = logging.getLogger(__name__)

server = Server("mcp-web-search")
_whitelist: list[str] = []


def _get_environment() -> str:
    environment = os.environ.get("ENVIRONMENT", "").strip().lower()
    if environment not in {"dev", "prod"}:
        raise RuntimeError("ENVIRONMENT must be set to 'dev' or 'prod' for mcp-web-search")
    return environment


def _validate_runtime_configuration() -> str:
    environment = _get_environment()
    if environment == "prod":
        from mcp_web_search.search_prod import validate_prod_search_configuration

        validate_prod_search_configuration()
    return environment


async def _run_web_search(query: str) -> str:
    environment = _get_environment()
    if environment == "dev":
        from mcp_web_search.search_dev import dev_web_search

        return await dev_web_search(query, _whitelist)

    from mcp_web_search.search_prod import prod_web_search

    return await prod_web_search(query, _whitelist)


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

    logger.info("web_search(query='%s')", query[:80])

    result = await _run_web_search(query)

    return [TextContent(type="text", text=result)]


def main() -> None:
    """Run the MCP server with stateless JSON streamable HTTP transport."""
    global _whitelist
    _whitelist = load_whitelist()
    environment = _validate_runtime_configuration()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )

    port = int(os.environ.get("MCP_PORT", "8089"))
    logger.info("Starting MCP web search server (env=%s, port=%d)", environment, port)

    from contextlib import asynccontextmanager
    from collections.abc import AsyncIterator
    from starlette.applications import Starlette
    from starlette.requests import Request as StarletteRequest
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route
    import uvicorn

    session_manager = create_session_manager()

    async def health(request: StarletteRequest) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    app = Starlette(
        routes=[
            Route("/health", health),
            Mount("/mcp", app=session_manager.handle_request),
        ],
        lifespan=lifespan,
    )

    uvicorn.run(app, host="0.0.0.0", port=port)


def create_session_manager():
    """Create the MCP session manager using the production-safe transport mode."""
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    return StreamableHTTPSessionManager(
        server,
        json_response=True,
        stateless=True,
    )


if __name__ == "__main__":
    main()
