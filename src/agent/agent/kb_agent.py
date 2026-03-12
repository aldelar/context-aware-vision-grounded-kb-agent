"""KB Search Agent — conversational agent using Microsoft Agent Framework.

Uses gpt-4.1 via ``AzureOpenAIChatClient`` and ``Agent`` with a single
``search_knowledge_base`` function tool to answer knowledge-base questions
grounded in Azure AI Search results.

Exports a ``create_agent()`` factory used by the hosting adapter (``main.py``).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Annotated

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from agent_framework import Agent
from agent_framework._sessions import InMemoryHistoryProvider
from agent_framework.azure import AzureOpenAIChatClient

from agent.search_tool import SearchResult, search_kb
from agent.image_service import get_image_url
from agent.vision_middleware import VisionImageMiddleware
from agent.config import config

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a helpful knowledge-base assistant. You answer questions about Azure \
services, features, and how-to guides using the search_knowledge_base tool.

Rules:
1. ALWAYS use the search_knowledge_base tool to find relevant information \
   before answering.
2. Ground your answers in the search results — do not make up information.
3. You have vision capabilities. The actual images from search results are \
   attached to the conversation so you can see them. When an image would \
   genuinely help illustrate or clarify your answer, embed it inline using \
   standard Markdown: ![brief description](url). You MUST copy the URL \
   exactly from the "url" field in each search result's "images" array — \
   it will always start with "/api/images/". \
   CORRECT example: ![Architecture diagram](/api/images/my-article/images/arch.png) \
   WRONG — do NOT use any of these formats: \
     • https://learn.microsoft.com/... (external URLs) \
     • attachment:filename.png (attachment scheme) \
     • api/images/... (missing leading slash) \
   Only include images that add value — do not embed every available image. \
   Refer to visual details you can see in the images when they are relevant.
4. Use inline reference markers to attribute information to its source. Each \
   search result has a ref_number — insert [Ref #N] immediately after the \
   sentence or paragraph that uses that result. For example: \
   "Azure AI Search supports IP firewall rules [Ref #1]."
5. Do NOT include a Sources section at the end — the UI handles that.
6. If the search results don't contain enough information to answer the \
   question, say so honestly.
7. Use clear Markdown formatting: headings, bullet points, bold for emphasis.
8. Be concise but thorough.
"""


# ---------------------------------------------------------------------------
# Dataclasses for structured output
# ---------------------------------------------------------------------------

@dataclass
class Citation:
    """A source citation from a search result."""

    article_id: str
    title: str
    section_header: str
    chunk_index: int
    content: str = ""
    image_urls: list[str] = field(default_factory=list)


@dataclass
class AgentResponse:
    """The agent's response to a user question."""

    text: str
    citations: list[Citation] = field(default_factory=list)
    images: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tool function — exposed to the agent as a callable function tool.
#
# The agent framework discovers the function signature and docstring
# automatically; no manual JSON schema definition is needed.
# ---------------------------------------------------------------------------


def search_knowledge_base(
    query: Annotated[str, "The search query — use natural language describing what information is needed"],
) -> str:
    """Search the knowledge base for articles about Azure services, features, and how-to guides.

    Returns relevant text chunks with optional images.
    """
    logger.info("search_knowledge_base(query='%s')", query[:80])

    try:
        results: list[SearchResult] = search_kb(query)
    except Exception:
        logger.error("search_kb execution failed", exc_info=True)
        return json.dumps({"error": "Search failed. Please try again."})

    result_dicts: list[dict] = []
    for idx, r in enumerate(results, start=1):
        result_dicts.append({
            "ref_number": idx,
            "content": r.content,
            "title": r.title,
            "section_header": r.section_header,
            "article_id": r.article_id,
            "chunk_index": r.chunk_index,
            "image_urls": list(r.image_urls),  # raw paths like 'images/foo.png'
            "images": [
                {"name": url.split("/")[-1], "url": get_image_url(r.article_id, url)}
                for url in r.image_urls
            ] if r.image_urls else [],
        })

    return json.dumps(result_dicts, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Agent factory — used by the hosting adapter
# ---------------------------------------------------------------------------

def create_agent() -> Agent:
    """Create and return a configured Agent instance.

    This factory is the entry point for the hosting adapter (``main.py``).
    It creates the ``AzureOpenAIChatClient`` with ``DefaultAzureCredential``
    (which includes WorkloadIdentityCredential for Foundry hosted agents,
    ManagedIdentityCredential, AzureCliCredential for local dev, etc.)
    and returns an ``Agent`` configured with the search tool and
    vision middleware.
    """
    # Use API key if provided (local dev), otherwise credential chain
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")

    if api_key:
        client = AzureOpenAIChatClient(
            api_key=api_key,
            endpoint=config.ai_services_endpoint,
            deployment_name=config.agent_model_deployment_name,
            api_version="2025-03-01-preview",
            middleware=[VisionImageMiddleware()],
        )
    else:
        # Use ad_token_provider pattern (not credential=) to avoid eager token
        # acquisition and support automatic token refresh for long-running servers.
        # Reference: foundry-samples/agent-with-foundry-tools/main.py
        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        client = AzureOpenAIChatClient(
            credential=token_provider,
            endpoint=config.ai_services_endpoint,
            deployment_name=config.agent_model_deployment_name,
            api_version="2025-03-01-preview",
            middleware=[VisionImageMiddleware()],
        )

    agent = Agent(
        client=client,
        id=os.environ.get("OTEL_SERVICE_NAME", "kb-agent"),
        name="KBSearchAgent",
        instructions=_SYSTEM_PROMPT,
        tools=[search_knowledge_base],
        context_providers=[InMemoryHistoryProvider()],
    )
    logger.info(
        "Created KBSearchAgent (model=%s, endpoint=%s)",
        config.agent_model_deployment_name,
        config.ai_services_endpoint,
    )
    return agent
