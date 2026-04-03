"""Cosmos DB-backed agent session repository.

Persists AgentSession state to the 'agent-sessions' container in Cosmos DB.
Used by the from_agent_framework() adapter to auto-load sessions before
each request and auto-save after.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.ai.agentserver.agentframework.persistence import (
    SerializedAgentSessionRepository,
)

from agent.client_factories import create_async_cosmos_client
from agent.search_result_store import compact_serialized_session_for_storage

logger = logging.getLogger(__name__)


class CosmosAgentSessionRepository(SerializedAgentSessionRepository):
    """Persists serialized AgentSession dicts to Cosmos DB.

    The 'agent-sessions' container uses partition key '/id'.
    Each document has:
      - id: conversation_id (partition key)
      - session: serialized session dict from AgentSession.to_dict()
    """

    def __init__(
        self,
        endpoint: str,
        database_name: str,
        container_name: str = "agent-sessions",
    ) -> None:
        self._endpoint = endpoint
        self._database_name = database_name
        self._container_name = container_name
        self._client: CosmosClient | None = None

    async def _get_container(self):
        """Lazy-init the Cosmos container client."""
        if self._client is None:
            self._client = create_async_cosmos_client(self._endpoint)
        db = self._client.get_database_client(self._database_name)
        return db.get_container_client(self._container_name)

    async def read_from_storage(
        self, conversation_id: Optional[str]
    ) -> Optional[Any]:
        """Read a serialized session from Cosmos DB.

        Returns None if the document doesn't exist.
        """
        if not conversation_id or not conversation_id.strip():
            return None
        container = await self._get_container()
        try:
            doc = await container.read_item(
                item=conversation_id,
                partition_key=conversation_id,
            )
            logger.info("Loaded session for conversation_id=%s", conversation_id)
            return doc.get("session")
        except CosmosResourceNotFoundError:
            logger.info(
                "No session found for conversation_id=%s (new conversation)",
                conversation_id,
            )
            return None

    async def write_to_storage(
        self, conversation_id: Optional[str], serialized_session: Any
    ) -> None:
        """Write (upsert) a serialized session to Cosmos DB.

        The agent is the sole owner of this container — direct upsert,
        no read-modify-write needed.
        """
        if not conversation_id or not conversation_id.strip():
            return
        container = await self._get_container()
        compacted_session = compact_serialized_session_for_storage(serialized_session)
        doc = {"id": conversation_id, "session": compacted_session}
        await container.upsert_item(doc)
        logger.info("Saved session for conversation_id=%s", conversation_id)
