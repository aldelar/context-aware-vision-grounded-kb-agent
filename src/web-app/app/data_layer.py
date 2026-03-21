"""Cosmos DB-backed data layer for Chainlit conversation persistence.

Uses a 4-container model with clean ownership boundaries:

- ``conversations``  (PK ``/userId``)         — sidebar metadata
- ``messages``       (PK ``/conversationId``)  — one doc per message
- ``references``     (PK ``/conversationId``)  — one doc per citation
- ``agent-sessions`` (PK ``/id``)              — agent-only (read for fallback)

The web app exclusively owns ``conversations``, ``messages``, and
``references``.  The agent exclusively owns ``agent-sessions``.
No shared documents — eliminates read-modify-write races.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity import DefaultAzureCredential
from chainlit.data import BaseDataLayer
from chainlit.types import (
    Feedback,
    PageInfo,
    Pagination,
    PaginatedResponse,
    ThreadFilter,
)

from app.config import config

if TYPE_CHECKING:
    from chainlit.element import ElementDict
    from chainlit.step import StepDict
    from chainlit.types import ThreadDict
    from chainlit.user import PersistedUser, User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cosmos client singleton
# ---------------------------------------------------------------------------

_cosmos_client: CosmosClient | None = None
_cosmos_client_failed: bool = False


def _get_cosmos_client() -> CosmosClient | None:
    """Return a module-level Cosmos client (created on first call).

    Returns ``None`` if the connection cannot be established (e.g. firewall
    or RBAC misconfiguration).  The caller must handle the ``None`` case
    gracefully so the app can still run without persistence.
    """
    global _cosmos_client, _cosmos_client_failed
    if _cosmos_client is not None:
        return _cosmos_client
    if _cosmos_client_failed:
        return None
    try:
        _cosmos_client = CosmosClient(
            url=config.cosmos_endpoint,
            credential=DefaultAzureCredential(),
        )
        return _cosmos_client
    except Exception:
        _cosmos_client_failed = True
        logger.warning(
            "Could not connect to Cosmos DB at %s — running WITHOUT "
            "conversation persistence.  Fix the firewall / RBAC and restart.",
            config.cosmos_endpoint,
            exc_info=True,
        )
        return None


# ---------------------------------------------------------------------------
# Data layer implementation
# ---------------------------------------------------------------------------


class CosmosDataLayer(BaseDataLayer):
    """Chainlit ``BaseDataLayer`` backed by Azure Cosmos DB (NoSQL / serverless).

    Uses four containers: ``conversations`` (sidebar metadata),
    ``messages`` (one doc per message), ``references`` (one doc per
    citation), and ``agent-sessions`` (read-only fallback).
    """

    def __init__(self) -> None:
        client = _get_cosmos_client()
        if client is not None:
            db = client.get_database_client(config.cosmos_database_name)
            self._conversations_container = db.get_container_client(
                config.cosmos_conversations_container
            )
            self._messages_container = db.get_container_client(
                config.cosmos_messages_container
            )
            self._references_container = db.get_container_client(
                config.cosmos_references_container
            )
            logger.info(
                "CosmosDataLayer initialised (database=%s, containers=%s)",
                config.cosmos_database_name,
                [config.cosmos_conversations_container,
                 config.cosmos_messages_container,
                 config.cosmos_references_container],
            )
        else:
            self._conversations_container = None  # type: ignore[assignment]
            self._messages_container = None  # type: ignore[assignment]
            self._references_container = None  # type: ignore[assignment]
            logger.warning("CosmosDataLayer running in degraded mode (no persistence)")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _user_identifier(doc: dict) -> str:
        """Derive the clean user identifier from a conversation document.

        Chainlit passes ``user.id`` (e.g. ``"user:local-user"``) as the
        ``user_id`` argument to ``update_thread``, but the auth check on
        resume compares ``thread["userIdentifier"]`` against
        ``user.identifier`` (e.g. ``"local-user"``).  This helper strips
        the ``user:`` prefix so the values match.
        """
        uid = doc.get("userIdentifier") or doc.get("userId", "")
        if uid.startswith("user:"):
            return uid[len("user:"):]
        return uid

    @staticmethod
    def _normalize_user_id(user_id: str | None) -> str:
        """Strip the ``user:`` prefix that Chainlit adds to persisted user IDs."""
        if not user_id:
            return "local-user"
        return user_id[len("user:"):] if user_id.startswith("user:") else user_id

    def _find_conversation(self, thread_id: str) -> dict | None:
        """Find a conversation doc by ID (cross-partition query).

        The ``conversations`` container is partitioned by ``/userId``, so
        looking up by ``id`` alone requires a cross-partition query.  This
        is acceptable because it only happens on resume and delete — not
        on every message.
        """
        if not self._conversations_container:
            return None
        try:
            results = list(
                self._conversations_container.query_items(
                    query="SELECT * FROM c WHERE c.id = @id",
                    parameters=[{"name": "@id", "value": thread_id}],
                    enable_cross_partition_query=True,
                    max_item_count=1,
                )
            )
            return results[0] if results else None
        except Exception:
            return None

    @staticmethod
    def _element_to_dict(element) -> dict:
        """Convert a Chainlit Element object or ElementDict to a plain dict."""
        if isinstance(element, dict):
            return element
        d: dict = {}
        for key in (
            "id", "threadId", "type", "url", "name", "display",
            "language", "size", "page", "forId", "mime",
        ):
            attr = "thread_id" if key == "threadId" else "for_id" if key == "forId" else key
            val = getattr(element, attr, None)
            if val is not None:
                d[key] = val
        content = getattr(element, "content", None) or getattr(element, "output", None)
        if content is not None:
            d["content"] = content
        return d

    @staticmethod
    def _step_type_to_role(step_type: str) -> str | None:
        """Map Chainlit step type to message role. Returns None for non-message types."""
        if step_type == "user_message":
            return "user"
        if step_type == "assistant_message":
            return "assistant"
        return None

    # ------------------------------------------------------------------
    # User management (no Cosmos IO)
    # ------------------------------------------------------------------

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        from chainlit.user import PersistedUser

        return PersistedUser(
            id=f"user:{identifier}",
            identifier=identifier,
            display_name=None,
            metadata={},
            createdAt=datetime.now(timezone.utc).isoformat(),
        )

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        from chainlit.user import PersistedUser

        now = datetime.now(timezone.utc).isoformat()
        return PersistedUser(
            id=f"user:{user.identifier}",
            identifier=user.identifier,
            display_name=user.display_name,
            metadata=user.metadata,
            createdAt=now,
        )

    # ------------------------------------------------------------------
    # Feedback (no-op)
    # ------------------------------------------------------------------

    async def upsert_feedback(self, feedback: Feedback) -> str:
        feedback_id = feedback.id or str(uuid.uuid4())
        logger.debug("Feedback upserted: %s (no-op storage)", feedback_id)
        return feedback_id

    async def delete_feedback(self, feedback_id: str) -> bool:
        logger.debug("Feedback deleted: %s (no-op)", feedback_id)
        return True

    # ------------------------------------------------------------------
    # References (formerly "elements")
    # ------------------------------------------------------------------

    async def create_element(self, element: "ElementDict") -> None:
        """Write a reference document to the ``references`` container."""
        if not self._references_container:
            return
        el_dict = self._element_to_dict(element)
        thread_id = el_dict.get("threadId")
        if not thread_id:
            return
        doc = {
            "id": el_dict.get("id", str(uuid.uuid4())),
            "conversationId": thread_id,
            "messageId": el_dict.get("forId", ""),
            "type": el_dict.get("type", "text"),
            "name": el_dict.get("name", ""),
            "content": el_dict.get("content", ""),
            "display": el_dict.get("display", "side"),
            "mime": el_dict.get("mime"),
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        self._references_container.upsert_item(doc)

    async def get_element(
        self, thread_id: str, element_id: str
    ) -> Optional[ElementDict]:
        """Point-read a reference from the ``references`` container."""
        if not self._references_container:
            return None
        try:
            doc = self._references_container.read_item(
                item=element_id, partition_key=thread_id
            )
            return {
                "id": doc["id"],
                "threadId": thread_id,
                "type": doc.get("type", "text"),
                "name": doc.get("name", ""),
                "content": doc.get("content", ""),
                "display": doc.get("display", "side"),
                "forId": doc.get("messageId"),
            }  # type: ignore[return-value]
        except CosmosResourceNotFoundError:
            return None

    async def delete_element(
        self, element_id: str, thread_id: Optional[str] = None
    ) -> None:
        if not self._references_container or not thread_id:
            return
        try:
            self._references_container.delete_item(
                item=element_id, partition_key=thread_id
            )
        except CosmosResourceNotFoundError:
            pass

    # ------------------------------------------------------------------
    # Messages (formerly "steps")
    # ------------------------------------------------------------------

    _LIFECYCLE_RUN_NAMES = frozenset({"on_chat_start", "on_message", "on_chat_resume"})

    def _is_lifecycle_run(self, step_dict: "StepDict") -> bool:
        return (
            step_dict.get("type") == "run"
            and step_dict.get("name") in self._LIFECYCLE_RUN_NAMES
        )

    def _auto_title_conversation(self, thread_id: str, output: str) -> None:
        """Set conversation name from first user message if unnamed."""
        if not self._conversations_container or not output:
            return
        conv = self._find_conversation(thread_id)
        if conv and not conv.get("name"):
            conv["name"] = output[:80]
            conv["updatedAt"] = datetime.now(timezone.utc).isoformat()
            self._conversations_container.upsert_item(conv)

    async def create_step(self, step_dict: "StepDict") -> None:
        """Insert a message document into the ``messages`` container."""
        if not self._messages_container:
            return
        if self._is_lifecycle_run(step_dict):
            return
        thread_id = step_dict.get("threadId")
        if not thread_id:
            return
        role = self._step_type_to_role(step_dict.get("type", ""))
        if not role:
            return  # skip tool, run, and other non-message types
        doc = {
            "id": step_dict.get("id") or str(uuid.uuid4()),
            "conversationId": thread_id,
            "role": role,
            "content": step_dict.get("output", ""),
            "createdAt": step_dict.get("createdAt") or datetime.now(timezone.utc).isoformat(),
        }
        self._messages_container.upsert_item(doc)

        # Auto-title: name the conversation from first user message
        if role == "user":
            self._auto_title_conversation(thread_id, step_dict.get("output", ""))

    async def update_step(self, step_dict: "StepDict") -> None:
        """Upsert a message document in the ``messages`` container."""
        if not self._messages_container:
            return
        if self._is_lifecycle_run(step_dict):
            return
        thread_id = step_dict.get("threadId")
        if not thread_id:
            return
        role = self._step_type_to_role(step_dict.get("type", ""))
        if not role:
            return
        doc = {
            "id": step_dict.get("id") or str(uuid.uuid4()),
            "conversationId": thread_id,
            "role": role,
            "content": step_dict.get("output", ""),
            "createdAt": step_dict.get("createdAt") or datetime.now(timezone.utc).isoformat(),
        }
        self._messages_container.upsert_item(doc)

    async def delete_step(self, step_id: str) -> None:
        logger.debug("delete_step %s (no-op without thread context)", step_id)

    # ------------------------------------------------------------------
    # Threads (conversations)
    # ------------------------------------------------------------------

    async def get_thread_author(self, thread_id: str) -> str:
        conv = self._find_conversation(thread_id)
        if not conv:
            return ""
        return self._user_identifier(conv)

    async def delete_thread(self, thread_id: str) -> None:
        """Delete conversation metadata, messages, and references."""
        # 1. Delete conversation doc (need userId for partition key)
        conv = self._find_conversation(thread_id)
        if conv and self._conversations_container:
            try:
                self._conversations_container.delete_item(
                    item=thread_id, partition_key=conv["userId"]
                )
            except CosmosResourceNotFoundError:
                pass

        # 2. Delete all messages (partition key = conversationId)
        if self._messages_container:
            msgs = list(
                self._messages_container.query_items(
                    query="SELECT c.id FROM c WHERE c.conversationId = @convId",
                    parameters=[{"name": "@convId", "value": thread_id}],
                    partition_key=thread_id,
                )
            )
            for msg in msgs:
                try:
                    self._messages_container.delete_item(
                        item=msg["id"], partition_key=thread_id
                    )
                except CosmosResourceNotFoundError:
                    pass

        # 3. Delete all references (partition key = conversationId)
        if self._references_container:
            refs = list(
                self._references_container.query_items(
                    query="SELECT c.id FROM c WHERE c.conversationId = @convId",
                    parameters=[{"name": "@convId", "value": thread_id}],
                    partition_key=thread_id,
                )
            )
            for ref in refs:
                try:
                    self._references_container.delete_item(
                        item=ref["id"], partition_key=thread_id
                    )
                except CosmosResourceNotFoundError:
                    pass

        logger.info("Thread deleted: %s", thread_id)

    async def list_threads(
        self,
        pagination: Pagination,
        filters: ThreadFilter,
    ) -> PaginatedResponse[ThreadDict]:
        """List conversations for the current user — single-partition query."""
        if not self._conversations_container:
            return PaginatedResponse(
                pageInfo=PageInfo(hasNextPage=False, startCursor=None, endCursor=None),
                data=[],
            )
        user_id = filters.userId or "local-user"
        clean_id = self._normalize_user_id(user_id)
        page_size = pagination.first or 20

        query = (
            "SELECT * FROM c WHERE c.userId = @userId "
            "ORDER BY c.updatedAt DESC"
        )
        params: list[dict] = [{"name": "@userId", "value": clean_id}]

        items = list(
            self._conversations_container.query_items(
                query=query,
                parameters=params,
                partition_key=clean_id,
                max_item_count=page_size + 1,
            )
        )

        has_next = len(items) > page_size
        items = items[:page_size]

        threads: list[ThreadDict] = []
        for item in items:
            threads.append(
                {
                    "id": item["id"],
                    "createdAt": item.get("createdAt", ""),
                    "name": item.get("name"),
                    "userId": item.get("userId"),
                    "userIdentifier": self._user_identifier(item),
                    "tags": item.get("tags"),
                    "metadata": item.get("metadata"),
                    "steps": [],
                    "elements": [],
                }
            )

        return PaginatedResponse(
            pageInfo=PageInfo(
                hasNextPage=has_next,
                startCursor=threads[0]["id"] if threads else None,
                endCursor=threads[-1]["id"] if threads else None,
            ),
            data=threads,
        )

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        """Load conversation metadata, messages, and references."""
        conv = self._find_conversation(thread_id)
        if not conv:
            return None

        # Load messages — single-partition query
        messages = list(
            self._messages_container.query_items(
                query=(
                    "SELECT * FROM c WHERE c.conversationId = @convId "
                    "ORDER BY c.createdAt ASC"
                ),
                parameters=[{"name": "@convId", "value": thread_id}],
                partition_key=thread_id,
            )
        ) if self._messages_container else []

        # Convert messages → StepDict format
        steps: list[dict] = []
        for msg in messages:
            step_type = "user_message" if msg.get("role") == "user" else "assistant_message"
            steps.append({
                "id": msg["id"],
                "type": step_type,
                "output": msg.get("content", ""),
                "createdAt": msg.get("createdAt", ""),
                "threadId": thread_id,
            })

        # Load references — single-partition query
        refs = list(
            self._references_container.query_items(
                query="SELECT * FROM c WHERE c.conversationId = @convId",
                parameters=[{"name": "@convId", "value": thread_id}],
                partition_key=thread_id,
            )
        ) if self._references_container else []

        # Convert references → ElementDict format
        elements: list[dict] = []
        for ref in refs:
            elements.append({
                "id": ref["id"],
                "threadId": thread_id,
                "type": ref.get("type", "text"),
                "name": ref.get("name", ""),
                "content": ref.get("content", ""),
                "display": ref.get("display", "side"),
                "forId": ref.get("messageId"),
                "mime": ref.get("mime"),
            })

        return {
            "id": thread_id,
            "createdAt": conv.get("createdAt", ""),
            "name": conv.get("name"),
            "userId": conv.get("userId"),
            "userIdentifier": self._user_identifier(conv),
            "tags": conv.get("tags"),
            "metadata": conv.get("metadata"),
            "steps": steps,
            "elements": elements,
        }

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Create or update a conversation document in ``conversations``."""
        if not self._conversations_container:
            return
        now = datetime.now(timezone.utc).isoformat()
        clean_user_id = self._normalize_user_id(user_id)

        # Try to read existing conversation
        doc = self._find_conversation(thread_id)

        if not doc:
            doc = {
                "id": thread_id,
                "userId": clean_user_id,
                "createdAt": now,
            }

        if name is not None:
            doc["name"] = name
        if user_id is not None:
            doc["userId"] = clean_user_id
        if metadata is not None:
            doc["metadata"] = metadata
        if tags is not None:
            doc["tags"] = tags
        doc["updatedAt"] = now

        self._conversations_container.upsert_item(doc)

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    async def build_debug_url(self) -> str:
        return ""

    async def close(self) -> None:
        logger.info("CosmosDataLayer closed")

    async def get_favorite_steps(self, user_id: str) -> List[StepDict]:
        return []
