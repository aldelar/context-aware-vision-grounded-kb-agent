"""Orchestrator — multi-agent handoff orchestration using HandoffBuilder.

Wires a triage orchestrator that routes questions to specialist agents:
  - InternalSearchAgent — for Azure AI Search + Content Understanding
  - WebSearchAgent — for other Azure topics via web search

Exports ``create_orchestrator()`` which returns a ``Workflow``, and
``create_orchestrator_agent()`` which returns a ``WorkflowAgent`` suitable
for both ``from_agent_framework()`` and ``AgentFrameworkAgent``.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from agent_framework import (
    Agent,
    CompactionProvider,
    InMemoryHistoryProvider,
    SlidingWindowStrategy,
    ToolResultCompactionStrategy,
    Workflow,
)
from agent_framework.orchestrations import HandoffBuilder

from agent.client_factories import create_chat_client
from agent.kb_agent import create_agent as create_internal_search_agent
from agent.web_search_agent import create_web_search_agent

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).with_name("prompts")


@lru_cache(maxsize=1)
def _load_orchestrator_prompt() -> str:
    """Load the orchestrator system prompt."""
    prompt_path = _PROMPTS_DIR / "orchestrator" / "system_prompt.md"
    try:
        prompt = prompt_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Unable to load orchestrator prompt from {prompt_path}") from exc
    if not prompt:
        raise RuntimeError(f"Orchestrator prompt is empty: {prompt_path}")
    return prompt


def create_orchestrator_builder() -> HandoffBuilder:
    """Create the multi-agent orchestrator HandoffBuilder.

    Returns a ``HandoffBuilder`` that can be passed directly to
    ``from_agent_framework()`` — it will call ``.build()`` per request,
    creating a fresh ``Workflow`` each time.  This avoids the
    ``Workflow is already running`` error that occurs when a singleton
    ``WorkflowAgent`` is reused across sequential AG-UI requests.

    The orchestrator holds the compaction and history providers.
    Specialist agents are stateless per invocation.
    """
    # Create specialist agents without compaction — orchestrator owns that
    internal_agent = create_internal_search_agent(standalone=False)
    web_agent = create_web_search_agent()

    # Create the orchestrator agent (triage)
    client = create_chat_client()
    prompt = _load_orchestrator_prompt()

    history = InMemoryHistoryProvider(skip_excluded=True)
    compaction = CompactionProvider(
        before_strategy=SlidingWindowStrategy(keep_last_groups=3),
        after_strategy=ToolResultCompactionStrategy(keep_last_tool_call_groups=1),
    )

    orchestrator_agent = Agent(
        client=client,
        id="orchestrator",
        name="Orchestrator",
        instructions=prompt,
        tools=[],  # HandoffBuilder adds handoff tools automatically
        context_providers=[history, compaction],
    )

    # Build the handoff builder (NOT .build() — let from_agent_framework handle that)
    # IMPORTANT: separate add_handoff calls per target so each handoff tool gets
    # a distinct description. The LLM routes based on tool descriptions.
    builder = (
        HandoffBuilder(name="kb-agent-orchestrator")
        .participants([orchestrator_agent, internal_agent, web_agent])
        .with_start_agent(orchestrator_agent)
        .add_handoff(
            source=orchestrator_agent,
            targets=[internal_agent],
            description="Hand off to the internal knowledge base search agent. Use ONLY for questions about Azure AI Search or Azure Content Understanding.",
        )
        .add_handoff(
            source=orchestrator_agent,
            targets=[web_agent],
            description="Hand off to the web search agent. Use for ALL other Azure topics including Cosmos DB, App Service, Functions, Container Apps, Kubernetes, Storage, networking, pricing, and any Azure service that is NOT Azure AI Search or Azure Content Understanding.",
        )
        .add_handoff(
            source=internal_agent,
            targets=[orchestrator_agent],
            description="Return to the orchestrator when done or if the question is outside scope.",
        )
        .add_handoff(
            source=web_agent,
            targets=[orchestrator_agent],
            description="Return to the orchestrator when done.",
        )
    )

    logger.info(
        "Created orchestrator HandoffBuilder with agents: %s, %s",
        internal_agent.name,
        web_agent.name,
    )
    return builder


def create_orchestrator() -> Workflow:
    """Create a built Workflow for testing purposes."""
    return create_orchestrator_builder().build()
