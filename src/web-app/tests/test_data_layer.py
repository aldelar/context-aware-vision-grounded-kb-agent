"""Tests for the Cosmos DB data layer (4-container model)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from azure.cosmos.exceptions import CosmosResourceNotFoundError
from chainlit.types import Feedback, PageInfo, Pagination, ThreadFilter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_containers():
    """Create mock Cosmos containers for the 4-container model."""
    return {
        "conversations": MagicMock(),
        "messages": MagicMock(),
        "references": MagicMock(),
    }


@pytest.fixture
def data_layer(mock_containers):
    """Create a CosmosDataLayer with mocked containers."""
    with patch("app.data_layer._get_cosmos_client") as mock_client:
        mock_db = MagicMock()

        def _get_container(name):
            return {
                "conversations": mock_containers["conversations"],
                "messages": mock_containers["messages"],
                "references": mock_containers["references"],
            }[name]

        mock_db.get_container_client.side_effect = _get_container
        mock_client.return_value.get_database_client.return_value = mock_db

        from app.data_layer import CosmosDataLayer
        layer = CosmosDataLayer()
        return layer


@pytest.fixture
def degraded_layer():
    """Create a CosmosDataLayer in degraded mode (no Cosmos connection)."""
    with patch("app.data_layer._get_cosmos_client") as mock_client:
        mock_client.return_value = None

        from app.data_layer import CosmosDataLayer
        layer = CosmosDataLayer()
        return layer


# ---------------------------------------------------------------------------
# User tests
# ---------------------------------------------------------------------------

class TestGetUser:
    @pytest.mark.asyncio
    async def test_returns_user(self, data_layer):
        user = await data_layer.get_user("alice")
        assert user is not None
        assert user.identifier == "alice"

    @pytest.mark.asyncio
    async def test_returns_user_even_without_cosmos(self, degraded_layer):
        user = await degraded_layer.get_user("alice")
        assert user is not None
        assert user.identifier == "alice"


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_creates_and_returns_user(self, data_layer):
        from chainlit.user import User
        user = User(identifier="bob", display_name="Bob")
        result = await data_layer.create_user(user)
        assert result is not None
        assert result.identifier == "bob"


# ---------------------------------------------------------------------------
# Thread (conversation) tests
# ---------------------------------------------------------------------------

class TestUpdateThread:
    @pytest.mark.asyncio
    async def test_creates_new_conversation(self, data_layer, mock_containers):
        conv = mock_containers["conversations"]
        conv.query_items.return_value = iter([])  # _find_conversation → not found

        await data_layer.update_thread(
            thread_id="t1",
            name="Test Thread",
            user_id="alice",
        )
        conv.upsert_item.assert_called_once()
        doc = conv.upsert_item.call_args[0][0]
        assert doc["id"] == "t1"
        assert doc["name"] == "Test Thread"
        assert doc["userId"] == "alice"
        assert "createdAt" in doc
        assert "updatedAt" in doc

    @pytest.mark.asyncio
    async def test_updates_existing_conversation(self, data_layer, mock_containers):
        conv = mock_containers["conversations"]
        conv.query_items.return_value = iter([
            {"id": "t1", "userId": "alice", "name": "Old", "createdAt": "2025-01-01"}
        ])

        await data_layer.update_thread(thread_id="t1", name="New Name")
        doc = conv.upsert_item.call_args[0][0]
        assert doc["name"] == "New Name"
        assert doc["userId"] == "alice"  # preserved from existing

    @pytest.mark.asyncio
    async def test_strips_user_prefix(self, data_layer, mock_containers):
        conv = mock_containers["conversations"]
        conv.query_items.return_value = iter([])

        await data_layer.update_thread(
            thread_id="t1", name="New", user_id="user:alice",
        )
        doc = conv.upsert_item.call_args[0][0]
        assert doc["userId"] == "alice"


class TestGetThread:
    @pytest.mark.asyncio
    async def test_returns_thread_with_messages_and_refs(self, data_layer, mock_containers):
        conv = mock_containers["conversations"]
        msgs = mock_containers["messages"]
        refs = mock_containers["references"]

        conv.query_items.return_value = iter([
            {"id": "t1", "userId": "alice", "createdAt": "2025-01-01", "name": "Test"}
        ])
        msgs.query_items.return_value = iter([
            {"id": "m1", "conversationId": "t1", "role": "user",
             "content": "Hello", "createdAt": "2025-01-01T00:00:01"},
            {"id": "m2", "conversationId": "t1", "role": "assistant",
             "content": "Hi there!", "createdAt": "2025-01-01T00:00:02"},
        ])
        refs.query_items.return_value = iter([
            {"id": "r1", "conversationId": "t1", "messageId": "m2",
             "type": "text", "name": "Ref #1", "content": "chunk", "display": "side"},
        ])

        thread = await data_layer.get_thread("t1")
        assert thread is not None
        assert thread["id"] == "t1"
        assert thread["name"] == "Test"
        assert len(thread["steps"]) == 2
        assert thread["steps"][0]["type"] == "user_message"
        assert thread["steps"][0]["output"] == "Hello"
        assert thread["steps"][1]["type"] == "assistant_message"
        assert len(thread["elements"]) == 1
        assert thread["elements"][0]["name"] == "Ref #1"

    @pytest.mark.asyncio
    async def test_returns_none_when_conversation_not_found(self, data_layer, mock_containers):
        mock_containers["conversations"].query_items.return_value = iter([])
        thread = await data_layer.get_thread("missing")
        assert thread is None

    @pytest.mark.asyncio
    async def test_empty_messages_returns_empty_steps(self, data_layer, mock_containers):
        conv = mock_containers["conversations"]
        conv.query_items.return_value = iter([
            {"id": "t1", "userId": "alice", "createdAt": "2025-01-01", "name": "Test"}
        ])
        mock_containers["messages"].query_items.return_value = iter([])
        mock_containers["references"].query_items.return_value = iter([])

        thread = await data_layer.get_thread("t1")
        assert thread is not None
        assert thread["steps"] == []
        assert thread["elements"] == []


class TestListThreads:
    @pytest.mark.asyncio
    async def test_lists_user_conversations(self, data_layer, mock_containers):
        conv = mock_containers["conversations"]
        conv.query_items.return_value = iter([
            {"id": "t1", "createdAt": "2025-01-02", "name": "Thread 1", "userId": "alice"},
            {"id": "t2", "createdAt": "2025-01-01", "name": "Thread 2", "userId": "alice"},
        ])

        result = await data_layer.list_threads(
            pagination=Pagination(first=20),
            filters=ThreadFilter(userId="alice"),
        )
        assert len(result.data) == 2
        assert result.pageInfo.hasNextPage is False

    @pytest.mark.asyncio
    async def test_single_partition_query(self, data_layer, mock_containers):
        """list_threads uses single-partition query (partition_key, no cross-partition)."""
        conv = mock_containers["conversations"]
        conv.query_items.return_value = iter([])

        await data_layer.list_threads(
            pagination=Pagination(first=20),
            filters=ThreadFilter(userId="alice"),
        )

        call_kwargs = conv.query_items.call_args[1]
        assert call_kwargs.get("partition_key") == "alice"
        assert "enable_cross_partition_query" not in call_kwargs

    @pytest.mark.asyncio
    async def test_paginates(self, data_layer, mock_containers):
        items = [
            {"id": f"t{i}", "createdAt": "2025-01-01", "name": f"T{i}", "userId": "u"}
            for i in range(3)
        ]
        mock_containers["conversations"].query_items.return_value = iter(items)

        result = await data_layer.list_threads(
            pagination=Pagination(first=2),
            filters=ThreadFilter(userId="u"),
        )
        assert len(result.data) == 2
        assert result.pageInfo.hasNextPage is True

    @pytest.mark.asyncio
    async def test_normalizes_prefixed_user(self, data_layer, mock_containers):
        mock_containers["conversations"].query_items.return_value = iter([])

        await data_layer.list_threads(
            pagination=Pagination(first=20),
            filters=ThreadFilter(userId="user:alice"),
        )

        call_kwargs = mock_containers["conversations"].query_items.call_args[1]
        assert call_kwargs["partition_key"] == "alice"
        params = {p["name"]: p["value"] for p in call_kwargs["parameters"]}
        assert params["@userId"] == "alice"


class TestDeleteThread:
    @pytest.mark.asyncio
    async def test_deletes_from_all_containers(self, data_layer, mock_containers):
        conv = mock_containers["conversations"]
        msgs = mock_containers["messages"]
        refs = mock_containers["references"]

        # Conversation found
        conv.query_items.return_value = iter([
            {"id": "t1", "userId": "alice"}
        ])
        # Messages to delete
        msgs.query_items.return_value = iter([
            {"id": "m1"}, {"id": "m2"},
        ])
        # References to delete
        refs.query_items.return_value = iter([
            {"id": "r1"},
        ])

        await data_layer.delete_thread("t1")

        conv.delete_item.assert_called_once_with(item="t1", partition_key="alice")
        assert msgs.delete_item.call_count == 2
        refs.delete_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_error_when_conversation_not_found(self, data_layer, mock_containers):
        conv = mock_containers["conversations"]
        msgs = mock_containers["messages"]
        refs = mock_containers["references"]

        conv.query_items.return_value = iter([])
        msgs.query_items.return_value = iter([])
        refs.query_items.return_value = iter([])

        await data_layer.delete_thread("missing")
        conv.delete_item.assert_not_called()


class TestGetThreadAuthor:
    @pytest.mark.asyncio
    async def test_returns_user_from_conversation(self, data_layer, mock_containers):
        mock_containers["conversations"].query_items.return_value = iter([
            {"id": "t1", "userId": "alice"}
        ])
        author = await data_layer.get_thread_author("t1")
        assert author == "alice"

    @pytest.mark.asyncio
    async def test_strips_user_prefix(self, data_layer, mock_containers):
        mock_containers["conversations"].query_items.return_value = iter([
            {"id": "t1", "userId": "user:alice"}
        ])
        author = await data_layer.get_thread_author("t1")
        assert author == "alice"

    @pytest.mark.asyncio
    async def test_returns_empty_when_not_found(self, data_layer, mock_containers):
        mock_containers["conversations"].query_items.return_value = iter([])
        author = await data_layer.get_thread_author("missing")
        assert author == ""


# ---------------------------------------------------------------------------
# Message (step) tests
# ---------------------------------------------------------------------------

class TestCreateStep:
    @pytest.mark.asyncio
    async def test_inserts_user_message(self, data_layer, mock_containers):
        msgs = mock_containers["messages"]
        # For auto-title: conversation exists but has no name
        mock_containers["conversations"].query_items.return_value = iter([
            {"id": "t1", "userId": "alice", "createdAt": "2025-01-01"}
        ])

        await data_layer.create_step({
            "threadId": "t1",
            "type": "user_message",
            "output": "Hello!",
            "id": "s1",
        })
        msgs.upsert_item.assert_called_once()
        doc = msgs.upsert_item.call_args[0][0]
        assert doc["id"] == "s1"
        assert doc["conversationId"] == "t1"
        assert doc["role"] == "user"
        assert doc["content"] == "Hello!"

    @pytest.mark.asyncio
    async def test_inserts_assistant_message(self, data_layer, mock_containers):
        msgs = mock_containers["messages"]

        await data_layer.create_step({
            "threadId": "t1",
            "type": "assistant_message",
            "output": "Hi there!",
            "id": "s2",
        })
        msgs.upsert_item.assert_called_once()
        doc = msgs.upsert_item.call_args[0][0]
        assert doc["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_skips_lifecycle_runs(self, data_layer, mock_containers):
        await data_layer.create_step({
            "threadId": "t1", "type": "run", "name": "on_message",
        })
        mock_containers["messages"].upsert_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_tool_steps(self, data_layer, mock_containers):
        await data_layer.create_step({
            "threadId": "t1", "type": "tool", "id": "s1",
        })
        mock_containers["messages"].upsert_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_without_thread_id(self, data_layer, mock_containers):
        await data_layer.create_step({"type": "user_message", "id": "s1"})
        mock_containers["messages"].upsert_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_titles_conversation(self, data_layer, mock_containers):
        conv = mock_containers["conversations"]
        # Conversation exists but has no name
        conv.query_items.return_value = iter([
            {"id": "t1", "userId": "alice", "createdAt": "2025-01-01"}
        ])

        await data_layer.create_step({
            "threadId": "t1",
            "type": "user_message",
            "output": "What is Azure AI Search?",
            "id": "s1",
        })

        # Verify auto-title updated the conversation
        conv.upsert_item.assert_called_once()
        titled_doc = conv.upsert_item.call_args[0][0]
        assert titled_doc["name"] == "What is Azure AI Search?"

    @pytest.mark.asyncio
    async def test_auto_title_truncates_to_80_chars(self, data_layer, mock_containers):
        conv = mock_containers["conversations"]
        conv.query_items.return_value = iter([
            {"id": "t1", "userId": "a", "createdAt": "2025-01-01"}
        ])

        long_msg = "x" * 120
        await data_layer.create_step({
            "threadId": "t1",
            "type": "user_message",
            "output": long_msg,
            "id": "s1",
        })

        titled_doc = conv.upsert_item.call_args[0][0]
        assert len(titled_doc["name"]) == 80

    @pytest.mark.asyncio
    async def test_auto_title_skips_when_name_exists(self, data_layer, mock_containers):
        conv = mock_containers["conversations"]
        conv.query_items.return_value = iter([
            {"id": "t1", "userId": "a", "name": "Existing", "createdAt": "2025-01-01"}
        ])

        await data_layer.create_step({
            "threadId": "t1",
            "type": "user_message",
            "output": "New message",
            "id": "s1",
        })

        # Conversation should NOT be updated (name already exists)
        conv.upsert_item.assert_not_called()


class TestUpdateStep:
    @pytest.mark.asyncio
    async def test_upserts_message(self, data_layer, mock_containers):
        msgs = mock_containers["messages"]

        await data_layer.update_step({
            "threadId": "t1",
            "id": "s1",
            "type": "assistant_message",
            "output": "Updated response",
        })
        msgs.upsert_item.assert_called_once()
        doc = msgs.upsert_item.call_args[0][0]
        assert doc["content"] == "Updated response"

    @pytest.mark.asyncio
    async def test_skips_lifecycle_runs(self, data_layer, mock_containers):
        await data_layer.update_step({
            "threadId": "t1", "type": "run", "name": "on_chat_start",
        })
        mock_containers["messages"].upsert_item.assert_not_called()


# ---------------------------------------------------------------------------
# Reference (element) tests
# ---------------------------------------------------------------------------

class TestCreateElement:
    @pytest.mark.asyncio
    async def test_inserts_reference(self, data_layer, mock_containers):
        refs = mock_containers["references"]

        await data_layer.create_element({
            "id": "e1", "threadId": "t1", "type": "text",
            "name": "Ref #1", "content": "chunk content", "display": "side",
            "forId": "m2",
        })
        refs.upsert_item.assert_called_once()
        doc = refs.upsert_item.call_args[0][0]
        assert doc["id"] == "e1"
        assert doc["conversationId"] == "t1"
        assert doc["messageId"] == "m2"
        assert doc["content"] == "chunk content"

    @pytest.mark.asyncio
    async def test_skips_when_no_thread_id(self, data_layer, mock_containers):
        await data_layer.create_element({"id": "e1", "type": "text"})
        mock_containers["references"].upsert_item.assert_not_called()


class TestGetElement:
    @pytest.mark.asyncio
    async def test_point_reads_reference(self, data_layer, mock_containers):
        refs = mock_containers["references"]
        refs.read_item.return_value = {
            "id": "e1", "conversationId": "t1", "messageId": "m2",
            "type": "text", "name": "Ref #1", "content": "found", "display": "side",
        }

        el = await data_layer.get_element("t1", "e1")
        assert el is not None
        assert el["content"] == "found"
        refs.read_item.assert_called_once_with(item="e1", partition_key="t1")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, data_layer, mock_containers):
        mock_containers["references"].read_item.side_effect = CosmosResourceNotFoundError()
        assert await data_layer.get_element("t1", "missing") is None


class TestDeleteElement:
    @pytest.mark.asyncio
    async def test_deletes_reference(self, data_layer, mock_containers):
        refs = mock_containers["references"]
        await data_layer.delete_element("e1", thread_id="t1")
        refs.delete_item.assert_called_once_with(item="e1", partition_key="t1")

    @pytest.mark.asyncio
    async def test_skips_when_no_thread_id(self, data_layer, mock_containers):
        await data_layer.delete_element("e1")
        mock_containers["references"].delete_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_error_when_not_found(self, data_layer, mock_containers):
        mock_containers["references"].delete_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.delete_element("e1", thread_id="t1")


# ---------------------------------------------------------------------------
# Feedback (no-op)
# ---------------------------------------------------------------------------

class TestFeedback:
    @pytest.mark.asyncio
    async def test_upsert_returns_id(self, data_layer):
        fb = Feedback(value=1, id="fb1", forId="step1")
        result = await data_layer.upsert_feedback(fb)
        assert result == "fb1"

    @pytest.mark.asyncio
    async def test_delete_returns_true(self, data_layer):
        assert await data_layer.delete_feedback("fb1") is True


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------

class TestNormalizeUserId:
    def test_strips_user_prefix(self, data_layer):
        assert data_layer._normalize_user_id("user:alice") == "alice"

    def test_leaves_clean_id(self, data_layer):
        assert data_layer._normalize_user_id("alice") == "alice"

    def test_none_returns_default(self, data_layer):
        assert data_layer._normalize_user_id(None) == "local-user"

    def test_empty_returns_default(self, data_layer):
        assert data_layer._normalize_user_id("") == "local-user"


class TestStepTypeToRole:
    def test_user_message(self, data_layer):
        assert data_layer._step_type_to_role("user_message") == "user"

    def test_assistant_message(self, data_layer):
        assert data_layer._step_type_to_role("assistant_message") == "assistant"

    def test_tool_returns_none(self, data_layer):
        assert data_layer._step_type_to_role("tool") is None

    def test_run_returns_none(self, data_layer):
        assert data_layer._step_type_to_role("run") is None


class TestFindConversation:
    def test_returns_doc_when_found(self, data_layer, mock_containers):
        conv = mock_containers["conversations"]
        conv.query_items.return_value = iter([
            {"id": "t1", "userId": "alice"}
        ])
        result = data_layer._find_conversation("t1")
        assert result is not None
        assert result["id"] == "t1"

    def test_returns_none_when_not_found(self, data_layer, mock_containers):
        mock_containers["conversations"].query_items.return_value = iter([])
        assert data_layer._find_conversation("missing") is None

    def test_returns_none_on_exception(self, data_layer, mock_containers):
        mock_containers["conversations"].query_items.side_effect = Exception("boom")
        assert data_layer._find_conversation("t1") is None

    def test_returns_none_in_degraded_mode(self, degraded_layer):
        assert degraded_layer._find_conversation("t1") is None


class TestUserMethodsNoCosmosIO:
    @pytest.mark.asyncio
    async def test_get_user_returns_persisted_user(self, data_layer, mock_containers):
        from chainlit.user import PersistedUser
        user = await data_layer.get_user("test-user")
        assert isinstance(user, PersistedUser)
        assert user.id == "user:test-user"
        assert user.identifier == "test-user"

    @pytest.mark.asyncio
    async def test_create_user_preserves_metadata(self, data_layer):
        from chainlit.user import User
        user = User(identifier="bob", display_name="Bob", metadata={"role": "admin"})
        result = await data_layer.create_user(user)
        assert result is not None
        assert result.id == "user:bob"
        assert result.metadata == {"role": "admin"}


# ---------------------------------------------------------------------------
# Degraded mode (no Cosmos connection)
# ---------------------------------------------------------------------------

class TestDegradedMode:
    @pytest.mark.asyncio
    async def test_get_user_returns_user(self, degraded_layer):
        user = await degraded_layer.get_user("alice")
        assert user is not None
        assert user.identifier == "alice"

    @pytest.mark.asyncio
    async def test_create_user_returns_ephemeral(self, degraded_layer):
        from chainlit.user import User
        user = User(identifier="bob")
        result = await degraded_layer.create_user(user)
        assert result is not None
        assert result.identifier == "bob"

    @pytest.mark.asyncio
    async def test_update_thread_is_noop(self, degraded_layer):
        await degraded_layer.update_thread(thread_id="t1", name="Test")

    @pytest.mark.asyncio
    async def test_get_thread_returns_none(self, degraded_layer):
        assert await degraded_layer.get_thread("t1") is None

    @pytest.mark.asyncio
    async def test_list_threads_returns_empty(self, degraded_layer):
        result = await degraded_layer.list_threads(
            pagination=Pagination(first=20),
            filters=ThreadFilter(userId="alice"),
        )
        assert result.data == []
        assert result.pageInfo.hasNextPage is False

    @pytest.mark.asyncio
    async def test_create_step_is_noop(self, degraded_layer):
        await degraded_layer.create_step({"threadId": "t1", "type": "user_message"})

    @pytest.mark.asyncio
    async def test_delete_thread_is_noop(self, degraded_layer):
        await degraded_layer.delete_thread("t1")

    @pytest.mark.asyncio
    async def test_create_element_is_noop(self, degraded_layer):
        await degraded_layer.create_element({"id": "e1", "threadId": "t1"})

    @pytest.mark.asyncio
    async def test_delete_element_is_noop(self, degraded_layer):
        await degraded_layer.delete_element("e1", thread_id="t1")

    @pytest.mark.asyncio
    async def test_get_element_returns_none(self, degraded_layer):
        assert await degraded_layer.get_element("t1", "e1") is None

    @pytest.mark.asyncio
    async def test_get_thread_author_returns_empty(self, degraded_layer):
        assert await degraded_layer.get_thread_author("t1") == ""


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

class TestMisc:
    @pytest.mark.asyncio
    async def test_build_debug_url(self, data_layer):
        assert await data_layer.build_debug_url() == ""

    @pytest.mark.asyncio
    async def test_close(self, data_layer):
        await data_layer.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_get_favorite_steps(self, data_layer):
        assert await data_layer.get_favorite_steps("user1") == []


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestCosmosContainerConfig:
    def test_sessions_default(self):
        from app.config import config
        assert config.cosmos_sessions_container == "agent-sessions"

    def test_conversations_default(self):
        from app.config import config
        assert config.cosmos_conversations_container == "conversations"

    def test_messages_default(self):
        from app.config import config
        assert config.cosmos_messages_container == "messages"

    def test_references_default(self):
        from app.config import config
        assert config.cosmos_references_container == "references"

    def test_sessions_from_env_var(self):
        import os
        from app.config import _load_config

        old = os.environ.get("COSMOS_SESSIONS_CONTAINER")
        try:
            os.environ["COSMOS_SESSIONS_CONTAINER"] = "custom-container"
            cfg = _load_config()
            assert cfg.cosmos_sessions_container == "custom-container"
        finally:
            if old is None:
                os.environ.pop("COSMOS_SESSIONS_CONTAINER", None)
            else:
                os.environ["COSMOS_SESSIONS_CONTAINER"] = old
