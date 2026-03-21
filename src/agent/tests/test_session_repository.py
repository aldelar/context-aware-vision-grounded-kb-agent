"""Unit tests for CosmosAgentSessionRepository."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError

from agent.session_repository import CosmosAgentSessionRepository


@pytest.fixture
def repo():
    """Create a repository with mocked credential."""
    with patch(
        "agent.session_repository.DefaultAzureCredential", return_value=MagicMock()
    ):
        return CosmosAgentSessionRepository(
            endpoint="https://test-cosmos.documents.azure.com:443/",
            database_name="kb-agent",
            container_name="agent-sessions",
        )


@pytest.fixture
def mock_container():
    """Create a mock Cosmos container client."""
    return AsyncMock()


@pytest.fixture
def repo_with_container(repo, mock_container):
    """Repo wired to a mock container (bypasses lazy init)."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_client.get_database_client.return_value = mock_db
    mock_db.get_container_client.return_value = mock_container
    repo._client = mock_client
    return repo


# ── Happy-path tests (from @coder) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_read_returns_session_when_document_exists(
    repo_with_container, mock_container
):
    session_data = {"messages": [{"role": "user", "content": "hello"}], "state": {}}
    mock_container.read_item.return_value = {
        "id": "conv-123",
        "session": session_data,
    }

    result = await repo_with_container.read_from_storage("conv-123")

    assert result == session_data
    mock_container.read_item.assert_awaited_once_with(
        item="conv-123", partition_key="conv-123"
    )


@pytest.mark.asyncio
async def test_read_returns_none_when_not_found(
    repo_with_container, mock_container
):
    mock_container.read_item.side_effect = CosmosResourceNotFoundError(
        status_code=404, message="Not Found"
    )

    result = await repo_with_container.read_from_storage("unknown-conv")

    assert result is None


@pytest.mark.asyncio
async def test_read_returns_none_for_empty_conversation_id(repo_with_container):
    assert await repo_with_container.read_from_storage(None) is None
    assert await repo_with_container.read_from_storage("") is None


@pytest.mark.asyncio
async def test_write_upserts_correct_document_structure(
    repo_with_container, mock_container
):
    session_data = {"messages": [], "state": {"key": "value"}}

    await repo_with_container.write_to_storage("conv-456", session_data)

    mock_container.upsert_item.assert_awaited_once_with(
        {
            "id": "conv-456",
            "session": session_data,
        }
    )


@pytest.mark.asyncio
async def test_write_skips_for_empty_conversation_id(
    repo_with_container, mock_container
):
    await repo_with_container.write_to_storage(None, {"state": {}})
    await repo_with_container.write_to_storage("", {"state": {}})
    mock_container.upsert_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_write_direct_upsert_no_read(
    repo_with_container, mock_container
):
    """Write must NOT read before writing — agent is sole owner."""
    new_session = {"messages": [{"role": "user", "content": "hi"}]}
    await repo_with_container.write_to_storage("conv-789", new_session)

    # No read_item call — direct upsert only
    mock_container.read_item.assert_not_awaited()
    upserted = mock_container.upsert_item.call_args[0][0]
    assert upserted == {"id": "conv-789", "session": new_session}


@pytest.mark.asyncio
async def test_roundtrip_write_then_read(repo_with_container, mock_container):
    """Write a session, then read it back — the same dict is returned."""
    session_data = {
        "messages": [{"role": "assistant", "content": "Hi there!"}],
        "state": {"counter": 42},
    }

    await repo_with_container.write_to_storage("conv-rt", session_data)
    upserted_doc = mock_container.upsert_item.call_args[0][0]

    # Simulate read returning the upserted document
    mock_container.read_item.return_value = upserted_doc
    result = await repo_with_container.read_from_storage("conv-rt")

    assert result == session_data


# ── Lazy-init pattern ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lazy_init_client_is_none_before_first_use(repo):
    """Client must be None immediately after construction."""
    assert repo._client is None


@pytest.mark.asyncio
async def test_lazy_init_creates_client_on_first_call(repo):
    """First call to _get_container() should create the CosmosClient."""
    with patch("agent.session_repository.CosmosClient") as mock_cosmos_cls:
        mock_cosmos_cls.return_value = MagicMock()
        await repo._get_container()

        mock_cosmos_cls.assert_called_once_with(
            url=repo._endpoint,
            credential=repo._credential,
        )
        assert repo._client is not None


@pytest.mark.asyncio
async def test_lazy_init_reuses_client_on_subsequent_calls(repo):
    """Subsequent calls to _get_container() must NOT create a new client."""
    with patch("agent.session_repository.CosmosClient") as mock_cosmos_cls:
        mock_cosmos_cls.return_value = MagicMock()
        await repo._get_container()
        await repo._get_container()

        # Still only one client instantiation
        mock_cosmos_cls.assert_called_once()


# ── DefaultAzureCredential verification ──────────────────────────────────


def test_uses_default_azure_credential():
    """Constructor must use DefaultAzureCredential (managed identity)."""
    with patch(
        "agent.session_repository.DefaultAzureCredential"
    ) as mock_cred_cls:
        mock_cred_cls.return_value = MagicMock()
        repo = CosmosAgentSessionRepository(
            endpoint="https://test.documents.azure.com:443/",
            database_name="db",
        )
        mock_cred_cls.assert_called_once()
        assert repo._credential is mock_cred_cls.return_value


def test_default_container_name():
    """Container name defaults to 'agent-sessions' when not specified."""
    with patch(
        "agent.session_repository.DefaultAzureCredential", return_value=MagicMock()
    ):
        repo = CosmosAgentSessionRepository(
            endpoint="https://test.documents.azure.com:443/",
            database_name="db",
        )
        assert repo._container_name == "agent-sessions"


# ── Error propagation ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_propagates_non_404_cosmos_errors(
    repo_with_container, mock_container
):
    """Non-404 Cosmos errors (e.g., 503 Service Unavailable) must bubble up."""
    mock_container.read_item.side_effect = CosmosHttpResponseError(
        status_code=503, message="Service Unavailable"
    )

    with pytest.raises(CosmosHttpResponseError):
        await repo_with_container.read_from_storage("conv-err")


@pytest.mark.asyncio
async def test_write_propagates_cosmos_errors(
    repo_with_container, mock_container
):
    """Write errors (e.g., 429 throttle) must bubble up, not be swallowed."""
    # read_item returns 404 (new doc), but upsert fails
    mock_container.read_item.side_effect = CosmosResourceNotFoundError(
        status_code=404, message="Not Found"
    )
    mock_container.upsert_item.side_effect = CosmosHttpResponseError(
        status_code=429, message="Too Many Requests"
    )

    with pytest.raises(CosmosHttpResponseError):
        await repo_with_container.write_to_storage("conv-err", {"data": 1})


# ── Edge cases ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_returns_none_when_session_key_missing(
    repo_with_container, mock_container
):
    """If a Cosmos doc exists but has no 'session' key, read returns None."""
    mock_container.read_item.return_value = {
        "id": "conv-no-session",
    }

    result = await repo_with_container.read_from_storage("conv-no-session")
    assert result is None


@pytest.mark.asyncio
async def test_write_large_session_payload(repo_with_container, mock_container):
    """Large sessions (many messages) are passed through to Cosmos upsert."""
    messages = [
        {"role": "user", "content": f"message-{i}" * 100}
        for i in range(500)
    ]
    large_session = {"messages": messages, "state": {"big": "x" * 10_000}}

    # No existing doc
    mock_container.read_item.side_effect = CosmosResourceNotFoundError(
        status_code=404, message="Not Found"
    )

    await repo_with_container.write_to_storage("conv-large", large_session)

    upserted = mock_container.upsert_item.call_args[0][0]
    assert upserted["session"] is large_session
    assert len(upserted["session"]["messages"]) == 500


@pytest.mark.asyncio
async def test_concurrent_writes_same_conversation_id(
    repo_with_container, mock_container
):
    """Multiple writes to the same conversation_id each produce an upsert."""
    session_v1 = {"messages": [], "state": {"v": 1}}
    session_v2 = {"messages": [{"role": "user", "content": "hi"}], "state": {"v": 2}}

    # First write — no existing doc
    mock_container.read_item.side_effect = CosmosResourceNotFoundError(
        status_code=404, message="Not Found"
    )
    await repo_with_container.write_to_storage("conv-dup", session_v1)

    # Second write — doc exists now
    mock_container.read_item.side_effect = None
    mock_container.read_item.return_value = {
        "id": "conv-dup",
        "session": session_v1,
    }
    await repo_with_container.write_to_storage("conv-dup", session_v2)

    assert mock_container.upsert_item.await_count == 2
    # Last upsert wins — verify the second call has v2
    last_doc = mock_container.upsert_item.call_args_list[-1][0][0]
    assert last_doc["session"]["state"]["v"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conversation_id",
    [None, "", "   "],
    ids=["none", "empty-string", "whitespace-only"],
)
async def test_read_returns_none_for_falsy_conversation_ids(
    repo_with_container, mock_container, conversation_id
):
    """All falsy / whitespace-only conversation_ids return None without
    hitting Cosmos."""
    result = await repo_with_container.read_from_storage(conversation_id)
    assert result is None
    mock_container.read_item.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conversation_id",
    [None, "", "   "],
    ids=["none", "empty-string", "whitespace-only"],
)
async def test_write_skips_for_falsy_conversation_ids(
    repo_with_container, mock_container, conversation_id
):
    """All falsy / whitespace-only conversation_ids skip upsert."""
    await repo_with_container.write_to_storage(conversation_id, {"s": 1})
    mock_container.upsert_item.assert_not_awaited()


# ── Write direct-upsert — no read step ───────────────────────────────────


@pytest.mark.asyncio
async def test_write_does_not_read_before_upsert(
    repo_with_container, mock_container
):
    """Direct upsert pattern — write must not call read_item."""
    await repo_with_container.write_to_storage("conv-err", {"data": 1})
    mock_container.read_item.assert_not_awaited()
    mock_container.upsert_item.assert_awaited_once()


# ── Story 10: conversationId removal — edge cases ───────────────────────


@pytest.mark.asyncio
async def test_new_doc_has_no_conversationId_field(
    repo_with_container, mock_container
):
    """New document must only contain 'id' — NO 'conversationId' key."""
    await repo_with_container.write_to_storage("conv-new", {"m": []})

    upserted = mock_container.upsert_item.call_args[0][0]
    assert upserted["id"] == "conv-new"
    assert "conversationId" not in upserted


@pytest.mark.asyncio
async def test_direct_upsert_does_not_inject_conversationId(
    repo_with_container, mock_container
):
    """Direct upsert must not add a 'conversationId' key."""
    await repo_with_container.write_to_storage(
        "conv-existing", {"messages": []}
    )

    upserted = mock_container.upsert_item.call_args[0][0]
    assert "conversationId" not in upserted
    assert upserted == {"id": "conv-existing", "session": {"messages": []}}


@pytest.mark.asyncio
async def test_write_with_uuid_conversation_id(
    repo_with_container, mock_container
):
    """UUID-format conversation_id (typical in production) works correctly."""
    conv_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    await repo_with_container.write_to_storage(conv_id, {"state": {}})

    upserted = mock_container.upsert_item.call_args[0][0]
    assert upserted["id"] == conv_id
    assert "conversationId" not in upserted


@pytest.mark.asyncio
async def test_read_with_uuid_conversation_id(
    repo_with_container, mock_container
):
    """UUID-format conversation_id reads correctly (partition_key == id)."""
    conv_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    mock_container.read_item.return_value = {
        "id": conv_id,
        "session": {"state": {"counter": 1}},
    }

    result = await repo_with_container.read_from_storage(conv_id)

    assert result == {"state": {"counter": 1}}
    mock_container.read_item.assert_awaited_once_with(
        item=conv_id, partition_key=conv_id,
    )


@pytest.mark.asyncio
async def test_roundtrip_without_conversationId_in_stored_doc(
    repo_with_container, mock_container
):
    """Full write→read round-trip: stored doc never gets conversationId."""
    session = {"messages": [{"role": "user", "content": "test"}]}

    # Write (new doc)
    mock_container.read_item.side_effect = CosmosResourceNotFoundError(
        status_code=404, message="Not Found"
    )
    await repo_with_container.write_to_storage("conv-rt2", session)
    upserted_doc = mock_container.upsert_item.call_args[0][0]
    assert "conversationId" not in upserted_doc

    # Read back from the upserted doc
    mock_container.read_item.side_effect = None
    mock_container.read_item.return_value = upserted_doc
    result = await repo_with_container.read_from_storage("conv-rt2")
    assert result == session


@pytest.mark.asyncio
async def test_write_replaces_entire_document(
    repo_with_container, mock_container
):
    """Direct upsert replaces the entire document — no field preservation."""
    await repo_with_container.write_to_storage(
        "conv-legacy", {"messages": []}
    )

    upserted = mock_container.upsert_item.call_args[0][0]
    # Only id and session — no legacy fields preserved
    assert upserted == {"id": "conv-legacy", "session": {"messages": []}}
