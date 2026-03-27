"""KB Search Agent — conversational agent using Microsoft Agent Framework.

Uses gpt-4.1 via ``AzureOpenAIChatClient`` and ``Agent`` with a single
``search_knowledge_base`` function tool to answer knowledge-base questions
grounded in Azure AI Search results.

Exports a ``create_agent()`` factory used by the hosting adapter (``main.py``).
"""

import json
import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from typing import Annotated

from pydantic import BeforeValidator

from agent_framework import Agent
from agent_framework._compaction import (
    CompactionProvider,
    SlidingWindowStrategy,
    ToolResultCompactionStrategy,
)
from agent_framework._sessions import InMemoryHistoryProvider

from agent.client_factories import create_chat_client
from agent.search_tool import SearchResult, search_kb
from agent.image_service import get_image_url
from agent.vision_middleware import VisionImageMiddleware
from agent.security_middleware import SecurityFilterMiddleware
from agent.config import config

logger = logging.getLogger(__name__)
_PROMPTS_DIR = Path(__file__).with_name("prompts")


def _resolve_prompt_environment(environment: str | None = None) -> str:
    normalized = (environment or config.environment or "prod").strip().lower()
    return "dev" if normalized == "dev" else "prod"


def _get_system_prompt_path(environment: str | None = None) -> Path:
    prompt_environment = _resolve_prompt_environment(environment)
    return _PROMPTS_DIR / f"system_prompt-{prompt_environment}.md"


def _coerce_search_query(value: Any) -> str:
    normalized = _normalize_search_query(value)
    if not normalized:
        raise ValueError("Search query was missing or malformed.")
    return normalized


@lru_cache(maxsize=2)
def _load_system_prompt(environment: str | None = None) -> str:
    """Load the agent system prompt from the external prompt file."""
    system_prompt_path = _get_system_prompt_path(environment)
    try:
        prompt = system_prompt_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Unable to load system prompt from {system_prompt_path}") from exc

    if not prompt:
        raise RuntimeError(f"System prompt file is empty: {system_prompt_path}")

    return prompt


_SYSTEM_PROMPT_PATH = _get_system_prompt_path()
_SYSTEM_PROMPT = _load_system_prompt()


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
    query: Annotated[
        str,
        BeforeValidator(_coerce_search_query),
        "The search query — use natural language describing what information is needed",
    ],
    **kwargs,
) -> str:
    """Search the knowledge base for articles about Azure services, features, and how-to guides.

    Returns relevant text chunks with optional images.
    """
    normalized_query = _normalize_search_query(query)
    if not normalized_query:
        return json.dumps({"error": "Search query was missing or malformed."})

    logger.info("search_knowledge_base(query='%s')", normalized_query[:80])

    # Build OData filter from departments injected by SecurityFilterMiddleware
    departments = kwargs.get("departments", [])
    security_filter = None
    if departments:
        dept_list = ",".join(departments)
        security_filter = f"search.in(department, '{dept_list}', ',')"
        logger.info("Applying security filter: %s", security_filter)

    try:
        results: list[SearchResult] = search_kb(normalized_query, security_filter=security_filter)
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
            "summary": r.summary,
            "indexed_at": r.indexed_at,
            "image_urls": list(r.image_urls),  # raw paths like 'images/foo.png'
            "images": [
                {"name": url.split("/")[-1], "url": get_image_url(r.article_id, url)}
                for url in r.image_urls
            ] if r.image_urls else [],
        })

    # Build a top-level summary for compaction metadata
    topics = list(dict.fromkeys(r.title for r in results if r.title))
    top_summary = f"{len(results)} results covering: {', '.join(topics[:5])}"

    return json.dumps(
        {"results": result_dicts, "summary": top_summary},
        ensure_ascii=False,
    )


def _normalize_search_query(query: str | dict[str, Any]) -> str | None:
    """Accept plain-string tool args and typed wrappers emitted by local models."""
    if isinstance(query, str):
        normalized = query.strip()
        return normalized or None

    if not isinstance(query, dict):
        return None

    value = query.get("value")
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None

    nested_query = query.get("query")
    if isinstance(nested_query, str):
        normalized = nested_query.strip()
        return normalized or None

    if isinstance(nested_query, dict):
        nested_value = nested_query.get("value")
        if isinstance(nested_value, str):
            normalized = nested_value.strip()
            return normalized or None

    return None


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
    client = create_chat_client()
    client.middleware = [VisionImageMiddleware()]

    history = InMemoryHistoryProvider(skip_excluded=True)
    compaction = CompactionProvider(
        before_strategy=SlidingWindowStrategy(keep_last_groups=3),
        after_strategy=ToolResultCompactionStrategy(keep_last_tool_call_groups=1),
    )

    agent = Agent(
        client=client,
        id=os.environ.get("OTEL_SERVICE_NAME", "kb-agent"),
        name="KBSearchAgent",
        instructions=_SYSTEM_PROMPT,
        tools=[search_knowledge_base],
        middleware=[SecurityFilterMiddleware()],
        context_providers=[history, compaction],
    )
    logger.info(
        "Created KBSearchAgent (model=%s, endpoint=%s)",
        config.agent_model_deployment_name,
        config.ai_services_endpoint,
    )
    return agent
