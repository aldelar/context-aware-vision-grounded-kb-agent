"""KB Agent — entry point for both local development and Foundry deployment.

Uses the ``from_agent_framework`` adapter from the Azure AI Agent Server SDK
to run the Agent as an HTTP server on port 8088.  The adapter handles:

- The Responses protocol (``/responses`` endpoint)
- SSE streaming (``agent.run_stream`` → Server-Sent Events)
- Health / readiness probes (``/liveness``, ``/readiness``)

Run locally::

    cd src/agent && uv run python main.py

The same ``main.py`` is used in the Dockerfile for Foundry hosted deployment.
"""

from __future__ import annotations

import logging
import os

from azure.ai.agentserver.agentframework import from_agent_framework

# Setup observability — two paths:
#   1. APPLICATIONINSIGHTS_CONNECTION_STRING set → use Azure Monitor (traces + logs + metrics)
#   2. OTEL_EXPORTER_OTLP_ENDPOINT set → use generic OTLP exporter (e.g., Aspire Dashboard)
#   3. Neither → instrumentation enabled but no export (local dev fallback)
#
# configure_azure_monitor() sets up the OTel providers (TracerProvider, LoggerProvider,
# MeterProvider) with Azure Monitor exporters.  enable_instrumentation() then tells the
# agent framework to emit spans for tool calls, model invocations, etc.
_appinsights_conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
if _appinsights_conn:
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(
        connection_string=_appinsights_conn,
        logger_name="agent",        # only export our loggers (agent.*), not agent_framework's
        logging_level=logging.INFO,  # export INFO+ to App Insights (default is WARNING)
    )
else:
    # Fall back to the standard configure_otel_providers which reads OTEL_EXPORTER_OTLP_ENDPOINT
    from agent_framework.observability import configure_otel_providers

    configure_otel_providers()

# Setup logging — force=True ensures a StreamHandler is added even when
# configure_azure_monitor() already attached an OTel handler to the root logger.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    force=True,
)
for _name in ("azure.core", "azure.identity", "httpx"):
    logging.getLogger(_name).setLevel(logging.WARNING)
# agent_framework INFO logs dump full tool call/response payloads (60KB+) which
# exceed App Insights' 64KB telemetry item limit and block the OTel exporter.
logging.getLogger("agent_framework").setLevel(logging.WARNING)
# Suppress noisy OpenTelemetry context-detach errors caused by async context
# propagation across task boundaries during SSE streaming.  These are harmless
# (open-telemetry/opentelemetry-python#4253).
logging.getLogger("opentelemetry.context").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


def _patch_agentserver_streaming_converter() -> None:
    """Work around null text deltas emitted by some local streaming responses."""
    from azure.ai.agentserver.agentframework.models.agent_framework_output_streaming_converter import (
        AgentFrameworkOutputStreamingConverter,
        ItemContentOutputText,
        ResponsesAssistantMessageItemResource,
        ResponseContentPartAddedEvent,
        ResponseContentPartDoneEvent,
        ResponseOutputItemAddedEvent,
        ResponseOutputItemDoneEvent,
        ResponseTextDeltaEvent,
        ResponseTextDoneEvent,
        _TextContentStreamingState,
    )

    if getattr(AgentFrameworkOutputStreamingConverter, "_kb_agent_null_text_patch", False):
        return

    async def _read_updates_without_null_text(self, updates):
        async for update in updates:
            if not update.contents:
                continue

            author_name = getattr(update, "author_name", "") or ""
            accepted_types = {"text", "function_call", "user_input_request", "function_result", "error"}
            for content in update.contents:
                if content.type not in accepted_types:
                    continue
                if content.type == "text" and getattr(content, "text", None) is None:
                    logger.debug("Skipping null text delta from agent stream")
                    continue
                yield (content, author_name)

    AgentFrameworkOutputStreamingConverter._read_updates = _read_updates_without_null_text

    async def _convert_contents_without_null_text(self, contents, author_name):
        item_id = self._parent.context.id_generator.generate_message_id()
        output_index = self._parent.next_output_index()

        yield ResponseOutputItemAddedEvent(
            sequence_number=self._parent.next_sequence(),
            output_index=output_index,
            item=ResponsesAssistantMessageItemResource(
                id=item_id,
                status="in_progress",
                content=[],
                created_by=self._parent._build_created_by(author_name),
            ),
        )

        yield ResponseContentPartAddedEvent(
            sequence_number=self._parent.next_sequence(),
            item_id=item_id,
            output_index=output_index,
            content_index=0,
            part=ItemContentOutputText(text="", annotations=[], logprobs=[]),
        )

        text = ""
        async for content in contents:
            delta = getattr(content, "text", None)
            if delta is None:
                logger.debug("Skipping null text delta inside converter state")
                continue
            text += delta

            yield ResponseTextDeltaEvent(
                sequence_number=self._parent.next_sequence(),
                item_id=item_id,
                output_index=output_index,
                content_index=0,
                delta=delta,
            )

        yield ResponseTextDoneEvent(
            sequence_number=self._parent.next_sequence(),
            item_id=item_id,
            output_index=output_index,
            content_index=0,
            text=text,
        )

        content_part = ItemContentOutputText(text=text, annotations=[], logprobs=[])
        yield ResponseContentPartDoneEvent(
            sequence_number=self._parent.next_sequence(),
            item_id=item_id,
            output_index=output_index,
            content_index=0,
            part=content_part,
        )

        item = ResponsesAssistantMessageItemResource(
            id=item_id,
            status="completed",
            content=[content_part],
            created_by=self._parent._build_created_by(author_name),
        )
        yield ResponseOutputItemDoneEvent(
            sequence_number=self._parent.next_sequence(),
            output_index=output_index,
            item=item,
        )

        self._parent.add_completed_output_item(item)

    _TextContentStreamingState.convert_contents = _convert_contents_without_null_text
    AgentFrameworkOutputStreamingConverter._kb_agent_null_text_patch = True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


from agent_framework.ag_ui import AgentFrameworkAgent, add_agent_framework_fastapi_endpoint
from fastapi import Depends, FastAPI

from middleware.jwt_auth import JWTAuthMiddleware, require_jwt_auth


def _create_ag_ui_app(agent) -> FastAPI:
    """Build the AG-UI FastAPI app mounted onto the Starlette agent server."""
    ag_ui_app = FastAPI(
        title="KB Agent AG-UI",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )
    ag_ui_agent = AgentFrameworkAgent(agent=agent, use_service_session=True)
    add_agent_framework_fastapi_endpoint(
        ag_ui_app,
        ag_ui_agent,
        "/",
        dependencies=[Depends(require_jwt_auth)],
    )
    return ag_ui_app


def main() -> None:
    """Run the KB Agent as an HTTP server on port 8088."""
    logger.info("[KB-AGENT] Starting agent server (port 8088)…")
    _patch_agentserver_streaming_converter()

    from agent.config import config
    from agent.kb_agent import create_agent
    from agent.session_repository import CosmosAgentSessionRepository

    agent = create_agent()
    logger.info("[KB-AGENT] Agent created, starting server…")

    session_repo = None
    if config.cosmos_endpoint:
        session_repo = CosmosAgentSessionRepository(
            endpoint=config.cosmos_endpoint,
            database_name=config.cosmos_database_name,
            container_name=config.cosmos_sessions_container,
        )
        logger.info("[KB-AGENT] Session persistence enabled (Cosmos DB)")
    else:
        logger.info("[KB-AGENT] Session persistence disabled (no COSMOS_ENDPOINT)")

    server = from_agent_framework(agent, session_repository=session_repo)
    server.app.add_middleware(JWTAuthMiddleware)
    server.app.mount("/ag-ui", _create_ag_ui_app(agent))
    server.run()


if __name__ == "__main__":
    main()
