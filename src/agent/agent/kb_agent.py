"""Internal Search Agent — conversational agent using Microsoft Agent Framework.

Uses gpt-4.1 via ``OpenAIChatCompletionClient`` and ``Agent`` with a single
``search_knowledge_base`` function tool to answer knowledge-base questions
grounded in Azure AI Search results.  Scoped to topics defined in
``config/internal-search-agent.yaml``.

Exports a ``create_agent()`` factory used by the hosting adapter (``main.py``).
"""

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from typing import Annotated

from pydantic import BeforeValidator

from agent_framework import (
    Agent,
    CompactionProvider,
    FunctionInvocationContext,
    InMemoryHistoryProvider,
    SlidingWindowStrategy,
    ToolResultCompactionStrategy,
)

from agent.client_factories import create_chat_client
from agent.image_service import get_image_url
from agent.scope_config import AgentScopeConfig, load_scope_config
from agent.search_tool import SearchResult, build_security_filter, search_kb
from agent.security_middleware import SecurityFilterMiddleware
from agent.vision_middleware import VisionImageMiddleware
from agent.config import config

logger = logging.getLogger(__name__)
_PROMPTS_DIR = Path(__file__).with_name("prompts")
_SCOPE_CONFIG = load_scope_config("internal-search-agent.yaml")


def _resolve_prompt_environment(environment: str | None = None) -> str:
    normalized = (environment or config.environment or "prod").strip().lower()
    return "dev" if normalized == "dev" else "prod"


def _get_system_prompt_path(environment: str | None = None) -> Path:
    prompt_environment = _resolve_prompt_environment(environment)
    return _PROMPTS_DIR / f"system_prompt-{prompt_environment}.md"


def _get_scoped_prompt_path() -> Path:
    """Return the path to the scoped internal-search-agent prompt template."""
    return _PROMPTS_DIR / "internal_search_agent" / "system_prompt.md"


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


def _load_scoped_prompt(scope: AgentScopeConfig) -> str:
    """Load the scoped prompt template and interpolate scope fields."""
    prompt_path = _get_scoped_prompt_path()
    try:
        template = prompt_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Unable to load scoped prompt from {prompt_path}") from exc

    if not template:
        raise RuntimeError(f"Scoped prompt file is empty: {prompt_path}")

    topics_formatted = " and ".join(scope.topics) if len(scope.topics) <= 2 else \
        ", ".join(scope.topics[:-1]) + f", and {scope.topics[-1]}"
    return template.replace("{topics_formatted}", topics_formatted).replace(
        "{description}", scope.description,
    )


_SYSTEM_PROMPT_PATH = _get_system_prompt_path()
_SYSTEM_PROMPT = _load_system_prompt()
_SCOPED_PROMPT = _load_scoped_prompt(_SCOPE_CONFIG)


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
    ctx: FunctionInvocationContext | None = None,
    **kwargs,
) -> str:
    """Search the knowledge base for articles about Azure services, features, and how-to guides.

    Returns relevant text chunks with optional images.
    """
    normalized_query = _normalize_search_query(query)
    if not normalized_query:
        return json.dumps({"error": "Search query was missing or malformed."})

    logger.info("search_knowledge_base(query='%s')", normalized_query[:80])

    # Build OData filter from departments injected by SecurityFilterMiddleware.
    # The framework injects a FunctionInvocationContext when middleware is active;
    # fall back to direct **kwargs for unit-test convenience.
    if ctx is not None:
        departments = ctx.kwargs.get("departments", [])
    else:
        departments = kwargs.get("departments", [])
    security_filter = build_security_filter(departments)
    if security_filter:
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
            "chunk_id": r.id,
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

def create_agent(*, standalone: bool = True) -> Agent:
    """Create and return a configured Agent instance.

    This factory is the entry point for the hosting adapter (``main.py``).
    It creates the ``OpenAIChatCompletionClient`` with ``DefaultAzureCredential``
    (which includes WorkloadIdentityCredential for Foundry hosted agents,
    ManagedIdentityCredential, AzureCliCredential for local dev, etc.)
    and returns an ``Agent`` configured with the search tool and
    vision middleware.

    Args:
        standalone: If True (default), includes compaction and history
            providers for standalone operation. Set to False when used
            as a specialist agent under the orchestrator — the orchestrator
            owns compaction/history to avoid double-compaction.
    """
    client = create_chat_client()
    client.function_invocation_configuration["max_iterations"] = 3

    context_providers = None
    if standalone:
        history = InMemoryHistoryProvider(skip_excluded=True)
        compaction = CompactionProvider(
            before_strategy=SlidingWindowStrategy(keep_last_groups=3),
            after_strategy=ToolResultCompactionStrategy(keep_last_tool_call_groups=1),
        )
        context_providers = [history, compaction]

    agent = Agent(
        client=client,
        id=_SCOPE_CONFIG.id,
        name=_SCOPE_CONFIG.name,
        instructions=_SCOPED_PROMPT,
        tools=[search_knowledge_base],
        middleware=[SecurityFilterMiddleware(), VisionImageMiddleware()],
        context_providers=context_providers,
    )
    logger.info(
        "Created %s (model=%s, endpoint=%s, standalone=%s)",
        _SCOPE_CONFIG.name,
        config.agent_model_deployment_name,
        config.ai_services_endpoint,
        standalone,
    )
    return agent
