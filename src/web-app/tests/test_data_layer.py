"""Tests for the Cosmos DB data layer."""

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
def mock_container():
    """Create a mock Cosmos container."""
    return MagicMock()


@pytest.fixture
def data_layer(mock_container):
    """Create a CosmosDataLayer with a mocked container."""
    with patch("app.data_layer._get_cosmos_client") as mock_client:
        mock_db = MagicMock()
        mock_db.get_container_client.return_value = mock_container
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
    async def test_returns_user(self, data_layer, mock_container):
        """get_user now returns a non-persisted PersistedUser without Cosmos."""
        user = await data_layer.get_user("alice")
        assert user is not None
        assert user.identifier == "alice"
        # No Cosmos read for users anymore
        mock_container.read_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_user_even_without_cosmos(self, degraded_layer):
        user = await degraded_layer.get_user("alice")
        assert user is not None
        assert user.identifier == "alice"


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_creates_and_returns_user(self, data_layer, mock_container):
        from chainlit.user import User
        user = User(identifier="bob", display_name="Bob")
        result = await data_layer.create_user(user)
        assert result is not None
        assert result.identifier == "bob"
        # Users are no longer persisted to Cosmos
        mock_container.upsert_item.assert_not_called()


# ---------------------------------------------------------------------------
# Thread tests
# ---------------------------------------------------------------------------

class TestUpdateThread:
    @pytest.mark.asyncio
    async def test_creates_new_thread(self, data_layer, mock_container):
        # _read_session_doc returns CosmosResourceNotFoundError → new doc
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()

        await data_layer.update_thread(
            thread_id="t1",
            name="Test Thread",
            user_id="alice",
        )
        mock_container.upsert_item.assert_called_once()
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["id"] == "t1"
        assert "conversationId" not in doc
        assert doc["name"] == "Test Thread"
        assert doc["userId"] == "alice"

    @pytest.mark.asyncio
    async def test_updates_existing_thread(self, data_layer, mock_container):
        existing = {
            "id": "t1",
            "userId": "alice",
            "name": "Old",
            "createdAt": "2025-01-01",
            "steps": [],
            "elements": [],
        }
        mock_container.read_item.return_value = existing

        await data_layer.update_thread(thread_id="t1", name="New Name")
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["name"] == "New Name"


class TestGetThread:
    @pytest.mark.asyncio
    async def test_returns_thread(self, data_layer, mock_container):
        mock_container.read_item.return_value = {
            "id": "t1",
            "userId": "alice",
            "createdAt": "2025-01-01",
            "name": "Test",
            "steps": [{"type": "user_message", "output": "Hello"}],
            "elements": [],
        }

        thread = await data_layer.get_thread("t1")
        assert thread is not None
        assert thread["id"] == "t1"
        assert len(thread["steps"]) == 1

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, data_layer, mock_container):
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        thread = await data_layer.get_thread("missing")
        assert thread is None

    @pytest.mark.asyncio
    async def test_synthesizes_steps_from_session(self, data_layer, mock_container):
        """When no steps but session has messages, synthesize steps."""
        mock_container.read_item.return_value = {
            "id": "t1",
            "userId": "alice",
            "createdAt": "2025-01-01",
            "name": "Test",
            "steps": [],
            "elements": [],
            "session": {
                "state": {
                    "messages": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi there!"},
                    ]
                }
            },
        }
        thread = await data_layer.get_thread("t1")
        assert thread is not None
        assert len(thread["steps"]) == 2
        assert thread["steps"][0]["type"] == "user_message"
        assert thread["steps"][0]["output"] == "Hello"
        assert thread["steps"][1]["type"] == "assistant_message"
        assert thread["steps"][1]["output"] == "Hi there!"

    @pytest.mark.asyncio
    async def test_synthesizes_steps_from_content_parts(self, data_layer, mock_container):
        """Content as list of parts is handled correctly."""
        mock_container.read_item.return_value = {
            "id": "t1",
            "createdAt": "2025-01-01",
            "steps": [],
            "elements": [],
            "session": {
                "state": {
                    "messages": [
                        {"role": "user", "content": [
                            {"type": "text", "text": "Part 1"},
                            {"type": "image_url", "url": "..."},
                            {"type": "text", "text": "Part 2"},
                        ]},
                    ]
                }
            },
        }
        thread = await data_layer.get_thread("t1")
        assert thread["steps"][0]["output"] == "Part 1 Part 2"


class TestListThreads:
    @pytest.mark.asyncio
    async def test_lists_user_threads(self, data_layer, mock_container):
        mock_container.query_items.return_value = iter([
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
    async def test_paginates(self, data_layer, mock_container):
        # Return 3 items when page_size=2 → hasNextPage=True, only 2 returned
        items = [
            {"id": f"t{i}", "createdAt": "2025-01-01", "name": f"T{i}", "userId": "u"}
            for i in range(3)
        ]
        mock_container.query_items.return_value = iter(items)

        result = await data_layer.list_threads(
            pagination=Pagination(first=2),
            filters=ThreadFilter(userId="u"),
        )
        assert len(result.data) == 2
        assert result.pageInfo.hasNextPage is True


class TestDeleteThread:
    @pytest.mark.asyncio
    async def test_deletes_existing_thread(self, data_layer, mock_container):
        await data_layer.delete_thread("t1")
        mock_container.delete_item.assert_called_once_with(
            item="t1", partition_key="t1"
        )

    @pytest.mark.asyncio
    async def test_no_error_when_not_found(self, data_layer, mock_container):
        mock_container.delete_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.delete_thread("missing")
        mock_container.delete_item.assert_called_once()


class TestGetThreadAuthor:
    @pytest.mark.asyncio
    async def test_returns_clean_id_when_prefixed(self, data_layer, mock_container):
        """Legacy docs store userId as 'user:local-user'; author must be 'local-user'."""
        mock_container.read_item.return_value = {
            "id": "t1", "userId": "user:local-user", "steps": [], "elements": [],
        }
        author = await data_layer.get_thread_author("t1")
        assert author == "local-user"

    @pytest.mark.asyncio
    async def test_returns_clean_id_when_not_prefixed(self, data_layer, mock_container):
        mock_container.read_item.return_value = {
            "id": "t2", "userId": "local-user", "steps": [], "elements": [],
        }
        author = await data_layer.get_thread_author("t2")
        assert author == "local-user"

    @pytest.mark.asyncio
    async def test_returns_empty_when_not_found(self, data_layer, mock_container):
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        author = await data_layer.get_thread_author("missing")
        assert author == ""


# ---------------------------------------------------------------------------
# Step tests
# ---------------------------------------------------------------------------

class TestCreateStep:
    @pytest.mark.asyncio
    async def test_appends_step(self, data_layer, mock_container):
        existing = {
            "id": "t1", "userId": "alice", "steps": [], "elements": [],
        }
        mock_container.read_item.return_value = existing

        await data_layer.create_step({
            "threadId": "t1",
            "type": "user_message",
            "output": "Hello!",
            "id": "s1",
        })
        doc = mock_container.upsert_item.call_args[0][0]
        assert len(doc["steps"]) == 1
        assert doc["name"] == "Hello!"  # auto-title from first user message

    @pytest.mark.asyncio
    async def test_auto_creates_thread_when_not_found(self, data_layer, mock_container):
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.create_step({"threadId": "missing", "type": "user_message"})
        # Session is auto-created on the fly when document doesn't exist
        mock_container.upsert_item.assert_called_once()
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["id"] == "missing"
        assert "conversationId" not in doc
        assert len(doc["steps"]) == 1


class TestUpdateStep:
    @pytest.mark.asyncio
    async def test_replaces_existing_step(self, data_layer, mock_container):
        existing = {
            "id": "t1", "userId": "alice",
            "steps": [{"id": "s1", "output": "old"}],
            "elements": [],
        }
        mock_container.read_item.return_value = existing

        await data_layer.update_step({
            "threadId": "t1", "id": "s1", "output": "new",
        })
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["steps"][0]["output"] == "new"


# ---------------------------------------------------------------------------
# Feedback (no-op)
# ---------------------------------------------------------------------------

class TestNormalizeUserId:
    """Tests for the _normalize_user_id static helper."""

    def test_strips_user_prefix(self, data_layer):
        assert data_layer._normalize_user_id("user:alice") == "alice"

    def test_leaves_clean_id(self, data_layer):
        assert data_layer._normalize_user_id("alice") == "alice"

    def test_none_returns_default(self, data_layer):
        assert data_layer._normalize_user_id(None) == "local-user"

    def test_empty_returns_default(self, data_layer):
        assert data_layer._normalize_user_id("") == "local-user"


class TestUpdateThreadNormalization:
    """Verify update_thread strips the user: prefix before persisting."""

    @pytest.mark.asyncio
    async def test_strips_user_prefix_on_create(self, data_layer, mock_container):
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()

        await data_layer.update_thread(
            thread_id="t1",
            name="New",
            user_id="user:alice",
        )
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["userId"] == "alice"

    @pytest.mark.asyncio
    async def test_strips_user_prefix_on_update(self, data_layer, mock_container):
        existing = {
            "id": "t1",
            "userId": "user:alice",
            "name": "Old",
            "createdAt": "2025-01-01",
            "steps": [],
            "elements": [],
        }
        mock_container.read_item.return_value = existing

        await data_layer.update_thread(
            thread_id="t1",
            name="Updated",
            user_id="user:alice",
        )
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["userId"] == "alice"


class TestListThreadsCrossPartition:
    """Verify list_threads finds threads stored under both userId variants."""

    @pytest.mark.asyncio
    async def test_uses_cross_partition_query(self, data_layer, mock_container):
        mock_container.query_items.return_value = iter([
            {"id": "t1", "createdAt": "2025-01-01", "name": "T1", "userId": "alice"},
        ])

        await data_layer.list_threads(
            pagination=Pagination(first=20),
            filters=ThreadFilter(userId="alice"),
        )

        call_kwargs = mock_container.query_items.call_args[1]
        assert call_kwargs["enable_cross_partition_query"] is True
        # Query should use IN with both clean and prefixed variants
        params = {p["name"]: p["value"] for p in call_kwargs["parameters"]}
        assert params["@cleanId"] == "alice"
        assert params["@prefixedId"] == "user:alice"

    @pytest.mark.asyncio
    async def test_userIdentifier_strips_prefix(self, data_layer, mock_container):
        """A legacy doc with userId='user:bob' still gets clean userIdentifier."""
        mock_container.query_items.return_value = iter([
            {"id": "t1", "createdAt": "2025-01-01", "name": "T1", "userId": "user:bob"},
        ])

        result = await data_layer.list_threads(
            pagination=Pagination(first=20),
            filters=ThreadFilter(userId="bob"),
        )
        assert result.data[0]["userIdentifier"] == "bob"


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

class TestCosmosSessionsContainerConfig:
    def test_default_value(self):
        from app.config import config
        assert config.cosmos_sessions_container == "agent-sessions"

    def test_from_env_var(self):
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


# ---------------------------------------------------------------------------
# _read_session_doc tests
# ---------------------------------------------------------------------------

class TestReadSessionDoc:
    def test_uses_point_read_with_partition_key(self, data_layer, mock_container):
        mock_container.read_item.return_value = {"id": "t1"}
        doc = data_layer._read_session_doc("t1")
        mock_container.read_item.assert_called_once_with(item="t1", partition_key="t1")
        assert doc["id"] == "t1"

    def test_returns_none_on_not_found(self, data_layer, mock_container):
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        assert data_layer._read_session_doc("missing") is None

    def test_returns_none_in_degraded_mode(self, degraded_layer):
        assert degraded_layer._read_session_doc("t1") is None


# ---------------------------------------------------------------------------
# get_thread session synthesis edge cases
# ---------------------------------------------------------------------------

class TestGetThreadSessionEdgeCases:
    @pytest.mark.asyncio
    async def test_session_with_no_state_key(self, data_layer, mock_container):
        """Session dict without 'state' → empty steps."""
        mock_container.read_item.return_value = {
            "id": "t1", "createdAt": "2025-01-01",
            "steps": [], "elements": [],
            "session": {"other": "data"},
        }
        thread = await data_layer.get_thread("t1")
        assert thread["steps"] == []

    @pytest.mark.asyncio
    async def test_session_with_empty_messages(self, data_layer, mock_container):
        """Session with messages: [] → empty steps."""
        mock_container.read_item.return_value = {
            "id": "t1", "createdAt": "2025-01-01",
            "steps": [], "elements": [],
            "session": {"state": {"messages": []}},
        }
        thread = await data_layer.get_thread("t1")
        assert thread["steps"] == []

    @pytest.mark.asyncio
    async def test_non_dict_session(self, data_layer, mock_container):
        """Non-dict session value → empty steps, no crash."""
        mock_container.read_item.return_value = {
            "id": "t1", "createdAt": "2025-01-01",
            "steps": [], "elements": [],
            "session": "invalid-string-session",
        }
        thread = await data_layer.get_thread("t1")
        assert thread["steps"] == []

    @pytest.mark.asyncio
    async def test_none_content_produces_empty_output(self, data_layer, mock_container):
        mock_container.read_item.return_value = {
            "id": "t1", "createdAt": "2025-01-01",
            "steps": [], "elements": [],
            "session": {"state": {"messages": [
                {"role": "user", "content": None},
            ]}},
        }
        thread = await data_layer.get_thread("t1")
        assert len(thread["steps"]) == 1
        assert thread["steps"][0]["output"] == ""

    @pytest.mark.asyncio
    async def test_integer_content_produces_empty_output(self, data_layer, mock_container):
        mock_container.read_item.return_value = {
            "id": "t1", "createdAt": "2025-01-01",
            "steps": [], "elements": [],
            "session": {"state": {"messages": [
                {"role": "user", "content": 42},
            ]}},
        }
        thread = await data_layer.get_thread("t1")
        assert len(thread["steps"]) == 1
        assert thread["steps"][0]["output"] == ""

    @pytest.mark.asyncio
    async def test_mixed_roles_classification(self, data_layer, mock_container):
        """Non-'user' roles all become assistant_message."""
        mock_container.read_item.return_value = {
            "id": "t1", "createdAt": "2025-01-01",
            "steps": [], "elements": [],
            "session": {"state": {"messages": [
                {"role": "system", "content": "You are a helper."},
                {"role": "user", "content": "Hi"},
                {"role": "tool", "content": "lookup result"},
                {"role": "assistant", "content": "Here you go"},
            ]}},
        }
        thread = await data_layer.get_thread("t1")
        assert len(thread["steps"]) == 4
        assert thread["steps"][0]["type"] == "assistant_message"
        assert thread["steps"][1]["type"] == "user_message"
        assert thread["steps"][2]["type"] == "assistant_message"
        assert thread["steps"][3]["type"] == "assistant_message"

    @pytest.mark.asyncio
    async def test_existing_steps_skips_synthesis(self, data_layer, mock_container):
        """When Chainlit steps exist, session messages are NOT synthesized."""
        mock_container.read_item.return_value = {
            "id": "t1", "createdAt": "2025-01-01",
            "steps": [{"id": "s1", "type": "user_message", "output": "real"}],
            "elements": [],
            "session": {"state": {"messages": [
                {"role": "user", "content": "ignored"},
                {"role": "assistant", "content": "also ignored"},
            ]}},
        }
        thread = await data_layer.get_thread("t1")
        assert len(thread["steps"]) == 1
        assert thread["steps"][0]["output"] == "real"

    @pytest.mark.asyncio
    async def test_synthesized_step_ids_are_sequential(self, data_layer, mock_container):
        mock_container.read_item.return_value = {
            "id": "t1", "createdAt": "2025-01-01",
            "steps": [], "elements": [],
            "session": {"state": {"messages": [
                {"role": "user", "content": "a"},
                {"role": "assistant", "content": "b"},
            ]}},
        }
        thread = await data_layer.get_thread("t1")
        assert thread["steps"][0]["id"] == "session-msg-0"
        assert thread["steps"][1]["id"] == "session-msg-1"


# ---------------------------------------------------------------------------
# Element tests
# ---------------------------------------------------------------------------

class TestCreateElement:
    @pytest.mark.asyncio
    async def test_appends_element(self, data_layer, mock_container):
        mock_container.read_item.return_value = {
            "id": "t1", "steps": [], "elements": [],
        }
        await data_layer.create_element({"id": "e1", "threadId": "t1", "type": "text"})
        doc = mock_container.upsert_item.call_args[0][0]
        assert len(doc["elements"]) == 1
        assert doc["elements"][0]["id"] == "e1"

    @pytest.mark.asyncio
    async def test_replaces_existing_element_by_id(self, data_layer, mock_container):
        mock_container.read_item.return_value = {
            "id": "t1", "steps": [],
            "elements": [{"id": "e1", "content": "old"}],
        }
        await data_layer.create_element({"id": "e1", "threadId": "t1", "content": "new"})
        doc = mock_container.upsert_item.call_args[0][0]
        assert len(doc["elements"]) == 1
        assert doc["elements"][0]["content"] == "new"

    @pytest.mark.asyncio
    async def test_skips_when_no_thread_id(self, data_layer, mock_container):
        await data_layer.create_element({"id": "e1", "type": "text"})
        mock_container.upsert_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_thread_not_found(self, data_layer, mock_container):
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.create_element({"id": "e1", "threadId": "t1"})
        mock_container.upsert_item.assert_not_called()


class TestGetElement:
    @pytest.mark.asyncio
    async def test_returns_element_when_found(self, data_layer, mock_container):
        mock_container.read_item.return_value = {
            "id": "t1", "steps": [],
            "elements": [{"id": "e1", "content": "found"}],
        }
        el = await data_layer.get_element("t1", "e1")
        assert el is not None
        assert el["content"] == "found"

    @pytest.mark.asyncio
    async def test_returns_none_when_element_missing(self, data_layer, mock_container):
        mock_container.read_item.return_value = {
            "id": "t1", "steps": [],
            "elements": [{"id": "e2"}],
        }
        assert await data_layer.get_element("t1", "e1") is None

    @pytest.mark.asyncio
    async def test_returns_none_when_thread_missing(self, data_layer, mock_container):
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        assert await data_layer.get_element("missing", "e1") is None


class TestDeleteElement:
    @pytest.mark.asyncio
    async def test_removes_element(self, data_layer, mock_container):
        mock_container.read_item.return_value = {
            "id": "t1", "steps": [],
            "elements": [{"id": "e1"}, {"id": "e2"}],
        }
        await data_layer.delete_element("e1", thread_id="t1")
        doc = mock_container.upsert_item.call_args[0][0]
        assert len(doc["elements"]) == 1
        assert doc["elements"][0]["id"] == "e2"

    @pytest.mark.asyncio
    async def test_skips_when_no_thread_id(self, data_layer, mock_container):
        await data_layer.delete_element("e1")
        mock_container.upsert_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_thread_not_found(self, data_layer, mock_container):
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.delete_element("e1", thread_id="missing")
        mock_container.upsert_item.assert_not_called()


# ---------------------------------------------------------------------------
# Update step auto-create
# ---------------------------------------------------------------------------

class TestUpdateStepAutoCreate:
    @pytest.mark.asyncio
    async def test_auto_creates_session_without_conversationId(self, data_layer, mock_container):
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.update_step({"threadId": "new-t", "id": "s1", "output": "hello"})
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["id"] == "new-t"
        assert "conversationId" not in doc
        assert len(doc["steps"]) == 1


# ---------------------------------------------------------------------------
# Update thread — no conversationId in new docs
# ---------------------------------------------------------------------------

class TestUpdateThreadNoConversationId:
    @pytest.mark.asyncio
    async def test_new_doc_has_no_conversationId(self, data_layer, mock_container):
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.update_thread(thread_id="t1", name="New")
        doc = mock_container.upsert_item.call_args[0][0]
        assert "conversationId" not in doc

    @pytest.mark.asyncio
    async def test_existing_doc_untouched(self, data_layer, mock_container):
        mock_container.read_item.return_value = {
            "id": "t1", "userId": "alice",
            "createdAt": "2025-01-01", "steps": [], "elements": [],
        }
        await data_layer.update_thread(thread_id="t1", name="Updated")
        doc = mock_container.upsert_item.call_args[0][0]
        assert "conversationId" not in doc


# ---------------------------------------------------------------------------
# Degraded mode (no Cosmos connection)
# ---------------------------------------------------------------------------

class TestDegradedMode:
    @pytest.mark.asyncio
    async def test_get_user_returns_user(self, degraded_layer):
        """get_user returns a non-persisted user even in degraded mode."""
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


# ---------------------------------------------------------------------------
# Degraded mode (no Cosmos connection) — additional coverage
# ---------------------------------------------------------------------------

class TestDegradedModeExtended:
    """Additional degraded-mode tests for non-persisted user methods."""

    @pytest.mark.asyncio
    async def test_create_user_returns_non_persisted(self, degraded_layer):
        from chainlit.user import User
        user = User(identifier="alice", display_name="Alice")
        result = await degraded_layer.create_user(user)
        assert result is not None
        assert result.identifier == "alice"

    @pytest.mark.asyncio
    async def test_get_user_returns_user_in_degraded(self, degraded_layer):
        """get_user returns a non-persisted user even without Cosmos."""
        user = await degraded_layer.get_user("alice")
        assert user is not None
        assert user.identifier == "alice"

    @pytest.mark.asyncio
    async def test_list_threads_returns_empty(self, degraded_layer):
        result = await degraded_layer.list_threads(
            pagination=Pagination(first=20),
            filters=ThreadFilter(userId="alice"),
        )
        assert result.data == []
        assert result.pageInfo.hasNextPage is False

    @pytest.mark.asyncio
    async def test_get_thread_returns_none(self, degraded_layer):
        assert await degraded_layer.get_thread("t1") is None

    @pytest.mark.asyncio
    async def test_update_thread_no_error(self, degraded_layer):
        await degraded_layer.update_thread(thread_id="t1", name="Test")

    @pytest.mark.asyncio
    async def test_create_step_no_error(self, degraded_layer):
        await degraded_layer.create_step({"threadId": "t1", "type": "user_message"})

    @pytest.mark.asyncio
    async def test_delete_thread_no_error(self, degraded_layer):
        await degraded_layer.delete_thread("t1")


# ---------------------------------------------------------------------------
# Story 10: Schema cleanup — conversationId removal edge cases
# ---------------------------------------------------------------------------

class TestNoConversationIdInAnyCodePath:
    """Verify that NO code path injects a 'conversationId' field."""

    @pytest.mark.asyncio
    async def test_create_step_auto_create_no_conversationId(
        self, data_layer, mock_container
    ):
        """create_step auto-creates a session doc without conversationId."""
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.create_step({
            "threadId": "auto-t1", "type": "assistant_message", "id": "s1",
        })
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["id"] == "auto-t1"
        assert "conversationId" not in doc

    @pytest.mark.asyncio
    async def test_update_step_auto_create_no_conversationId(
        self, data_layer, mock_container
    ):
        """update_step auto-creates a session doc without conversationId."""
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.update_step({
            "threadId": "auto-t2", "id": "s1", "output": "hello",
        })
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["id"] == "auto-t2"
        assert "conversationId" not in doc

    @pytest.mark.asyncio
    async def test_update_thread_new_doc_no_conversationId(
        self, data_layer, mock_container
    ):
        """update_thread creating a new thread has no conversationId."""
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.update_thread(
            thread_id="new-t1", name="Thread", user_id="alice",
        )
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["id"] == "new-t1"
        assert "conversationId" not in doc

    @pytest.mark.asyncio
    async def test_update_thread_with_prefixed_user_no_conversationId(
        self, data_layer, mock_container
    ):
        """Even with 'user:' prefix, new thread doc has no conversationId."""
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.update_thread(
            thread_id="new-t2", name="Thread", user_id="user:alice",
        )
        doc = mock_container.upsert_item.call_args[0][0]
        assert "conversationId" not in doc
        assert doc["userId"] == "alice"


class TestUserMethodsNoCosmosIO:
    """get_user and create_user must NOT touch Cosmos at all."""

    @pytest.mark.asyncio
    async def test_get_user_never_calls_cosmos(self, data_layer, mock_container):
        """get_user returns a PersistedUser without any Cosmos read."""
        user = await data_layer.get_user("test-user")
        mock_container.read_item.assert_not_called()
        mock_container.query_items.assert_not_called()
        assert user is not None
        assert user.id == "user:test-user"
        assert user.identifier == "test-user"

    @pytest.mark.asyncio
    async def test_get_user_returns_correct_structure(self, data_layer):
        """get_user returns PersistedUser with expected field types."""
        user = await data_layer.get_user("alice")
        assert user.display_name is None
        assert user.metadata == {}
        assert user.createdAt is not None

    @pytest.mark.asyncio
    async def test_create_user_never_calls_cosmos(self, data_layer, mock_container):
        """create_user returns a PersistedUser without any Cosmos write."""
        from chainlit.user import User
        user = User(identifier="bob", display_name="Bob", metadata={"role": "admin"})
        result = await data_layer.create_user(user)
        mock_container.upsert_item.assert_not_called()
        mock_container.create_item.assert_not_called()
        assert result is not None
        assert result.id == "user:bob"
        assert result.identifier == "bob"
        assert result.display_name == "Bob"
        assert result.metadata == {"role": "admin"}

    @pytest.mark.asyncio
    async def test_get_user_returns_none_type_is_persisted_user(self, data_layer):
        """get_user must return PersistedUser (not None or raw dict)."""
        from chainlit.user import PersistedUser
        user = await data_layer.get_user("anyone")
        assert isinstance(user, PersistedUser)


class TestReadSessionDocRename:
    """Verify the rename from _read_thread_doc → _read_session_doc."""

    def test_read_session_doc_exists(self, data_layer):
        """_read_session_doc method must exist on CosmosDataLayer."""
        assert hasattr(data_layer, "_read_session_doc")
        assert callable(data_layer._read_session_doc)

    def test_read_thread_doc_does_not_exist(self, data_layer):
        """Old _read_thread_doc name must NOT exist."""
        assert not hasattr(data_layer, "_read_thread_doc")


class TestSessionSynthesisWithoutConversationId:
    """Session synthesis works correctly even when documents lack conversationId."""

    @pytest.mark.asyncio
    async def test_synthesis_from_doc_without_conversationId(
        self, data_layer, mock_container
    ):
        """Document schema post-migration (no conversationId) synthesizes steps."""
        mock_container.read_item.return_value = {
            "id": "t1",
            "userId": "alice",
            "createdAt": "2025-06-01",
            "steps": [],
            "elements": [],
            "session": {
                "state": {
                    "messages": [
                        {"role": "user", "content": "What is AI Search?"},
                        {"role": "assistant", "content": "AI Search is..."},
                    ]
                }
            },
        }
        thread = await data_layer.get_thread("t1")
        assert thread is not None
        assert len(thread["steps"]) == 2
        assert "conversationId" not in mock_container.read_item.return_value


class TestListThreadsStillWorks:
    """list_threads with cross-partition query works after schema changes."""

    @pytest.mark.asyncio
    async def test_list_threads_returns_threads_without_conversationId(
        self, data_layer, mock_container
    ):
        """Threads without conversationId are listed normally."""
        mock_container.query_items.return_value = iter([
            {"id": "t1", "createdAt": "2025-06-01", "name": "Thread 1",
             "userId": "alice"},
            {"id": "t2", "createdAt": "2025-06-02", "name": "Thread 2",
             "userId": "alice"},
        ])

        result = await data_layer.list_threads(
            pagination=Pagination(first=20),
            filters=ThreadFilter(userId="alice"),
        )
        assert len(result.data) == 2
        # Threads in response also should not have conversationId
        for t in result.data:
            assert "conversationId" not in t

    @pytest.mark.asyncio
    async def test_list_threads_normalizes_prefixed_user(
        self, data_layer, mock_container
    ):
        """list_threads handles user: prefix correctly."""
        mock_container.query_items.return_value = iter([])

        await data_layer.list_threads(
            pagination=Pagination(first=20),
            filters=ThreadFilter(userId="user:alice"),
        )

        params = {
            p["name"]: p["value"]
            for p in mock_container.query_items.call_args[1]["parameters"]
        }
        assert params["@cleanId"] == "alice"
        assert params["@prefixedId"] == "user:alice"


class TestAutoCreateDocFields:
    """Verify the fields in auto-created session docs are correct."""

    @pytest.mark.asyncio
    async def test_create_step_auto_doc_has_required_fields(
        self, data_layer, mock_container
    ):
        """Auto-created doc from create_step has id, userId, timestamps, arrays."""
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.create_step({
            "threadId": "auto-1", "type": "user_message", "id": "s1",
            "output": "hi",
        })
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["id"] == "auto-1"
        assert doc["userId"] == "local-user"
        assert "createdAt" in doc
        assert "updatedAt" in doc
        assert isinstance(doc["steps"], list)
        assert isinstance(doc["elements"], list)
        assert len(doc["steps"]) == 1
        assert "conversationId" not in doc

    @pytest.mark.asyncio
    async def test_update_step_auto_doc_has_required_fields(
        self, data_layer, mock_container
    ):
        """Auto-created doc from update_step has correct structure."""
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.update_step({
            "threadId": "auto-2", "id": "s1", "output": "updated",
        })
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["id"] == "auto-2"
        assert doc["userId"] == "local-user"
        assert "createdAt" in doc
        assert "updatedAt" in doc
        assert len(doc["steps"]) == 1
        assert "conversationId" not in doc

    @pytest.mark.asyncio
    async def test_update_thread_new_doc_has_required_fields(
        self, data_layer, mock_container
    ):
        """New doc from update_thread has correct structure."""
        mock_container.read_item.side_effect = CosmosResourceNotFoundError()
        await data_layer.update_thread(
            thread_id="auto-3", name="Test", user_id="user:bob",
        )
        doc = mock_container.upsert_item.call_args[0][0]
        assert doc["id"] == "auto-3"
        assert doc["userId"] == "bob"
        assert "createdAt" in doc
        assert "updatedAt" in doc
        assert isinstance(doc["steps"], list)
        assert isinstance(doc["elements"], list)
        assert "conversationId" not in doc
