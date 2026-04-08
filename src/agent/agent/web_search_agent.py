"""Web Search Agent — searches Microsoft Learn via MCP web search tool.

Connects to an MCP web search server (SSE transport) to find information
from Microsoft Learn documentation. Used by the orchestrator
for Azure topics outside the internal knowledge base scope.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from agent_framework import Agent, MCPStreamableHTTPTool

from agent.client_factories import create_chat_client
from agent.vision_middleware import VisionImageMiddleware

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).with_name("prompts")


@lru_cache(maxsize=1)
def _load_web_search_prompt() -> str:
    """Load the web search agent system prompt."""
    prompt_path = _PROMPTS_DIR / "web_search_agent" / "system_prompt.md"
    try:
        prompt = prompt_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Unable to load web search agent prompt from {prompt_path}") from exc
    if not prompt:
        raise RuntimeError(f"Web search agent prompt is empty: {prompt_path}")
    return prompt


def create_web_search_agent() -> Agent:
    """Create the web search agent with MCP tool connection.

    The agent connects to an MCP web search server via SSE transport.
    The server endpoint is configured via ``WEB_SEARCH_MCP_ENDPOINT``.

    Returns:
        A configured ``Agent`` instance with the MCP web search tool.
    """
    client = create_chat_client()

    mcp_endpoint = os.environ.get("WEB_SEARCH_MCP_ENDPOINT", "http://localhost:8089/mcp/")

    prompt = _load_web_search_prompt()

    mcp_tool = MCPStreamableHTTPTool(
        name="mcp-web-search",
        url=mcp_endpoint,
        allowed_tools=["web_search"],
        load_prompts=False,
    )

    agent = Agent(
        client=client,
        id="web-search-agent",
        name="WebSearchAgent",
        instructions=prompt,
        tools=[mcp_tool],
        middleware=[VisionImageMiddleware()],
        # No SecurityFilterMiddleware (web search results are public docs)
        # No GroundingMiddleware (grounding is specific to internal search result format)
        # No compaction providers (orchestrator handles this)
    )

    logger.info("Created WebSearchAgent (mcp_endpoint=%s)", mcp_endpoint)
    return agent
