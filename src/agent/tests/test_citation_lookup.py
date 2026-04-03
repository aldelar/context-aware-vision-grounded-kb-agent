"""Tests for transcript-scoped citation lookup endpoint wiring."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.testclient import TestClient

import pytest

from main import _create_citation_lookup_app


class _FakeSessionRepository:
    def __init__(self, serialized_session):
        self.serialized_session = serialized_session

    async def read_from_storage(self, conversation_id: str):
        return self.serialized_session if conversation_id == "thread-123" else None


class TestCitationLookupEndpoint:
    def test_mount_enforces_auth_when_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REQUIRE_AUTH", "true")

        app = Starlette()
        app.mount("/citations", _create_citation_lookup_app(_FakeSessionRepository(None)))
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/citations/thread-123/tool-call-1/1")

        assert response.status_code == 401
        assert response.json()["detail"]["error"] == "unauthorized"

    def test_returns_ready_when_chunk_is_reloaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REQUIRE_AUTH", "false")

        serialized_session = {
            "state": {
                "messages": [
                    {
                        "id": "tool-1",
                        "role": "tool",
                        "toolCallId": "tool-call-1",
                        "toolName": "search_knowledge_base",
                        "content": {
                            "results": [
                                {
                                    "ref_number": 1,
                                    "chunk_id": "article-1_0",
                                    "article_id": "article-1",
                                    "chunk_index": 0,
                                    "indexed_at": "2026-04-01T00:00:00Z",
                                    "title": "Overview",
                                    "section_header": "Intro",
                                    "summary": "Stored summary",
                                    "content": "Stored summary",
                                    "content_source": "summary",
                                },
                            ],
                            "summary": "1 result covering: Overview",
                        },
                    },
                ],
            },
        }

        app = Starlette()
        app.mount("/citations", _create_citation_lookup_app(_FakeSessionRepository(serialized_session)))

        class _Chunk:
            id = "article-1_0"
            article_id = "article-1"
            chunk_index = 0
            content = "Full chunk content loaded on demand."
            title = "Overview"
            section_header = "Intro"
            summary = "Fresh summary"
            indexed_at = "2026-04-01T00:00:00Z"
            image_urls = ["images/overview.png"]

        client = TestClient(app, raise_server_exceptions=False)
        with pytest.MonkeyPatch.context() as route_patch:
            route_patch.setattr("main.get_chunk_by_id", lambda document_id, security_filter=None: _Chunk())
            response = client.get("/citations/thread-123/tool-call-1/1")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "citation": {
                "ref_number": 1,
                "chunk_id": "article-1_0",
                "article_id": "article-1",
                "chunk_index": 0,
                "indexed_at": "2026-04-01T00:00:00Z",
                "title": "Overview",
                "section_header": "Intro",
                "summary": "Fresh summary",
                "content": "Full chunk content loaded on demand.",
                "content_source": "full",
                "image_urls": ["images/overview.png"],
                "images": [{"name": "overview.png", "url": "/api/images/article-1/images/overview.png"}],
            },
        }

    def test_returns_stale_when_indexed_timestamp_changes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REQUIRE_AUTH", "false")

        serialized_session = {
            "state": {
                "messages": [
                    {
                        "id": "tool-1",
                        "role": "tool",
                        "toolCallId": "tool-call-1",
                        "toolName": "search_knowledge_base",
                        "content": {
                            "results": [
                                {
                                    "ref_number": 1,
                                    "chunk_id": "article-1_0",
                                    "indexed_at": "2026-04-01T00:00:00Z",
                                    "summary": "Stored summary",
                                    "content": "Stored summary",
                                    "content_source": "summary",
                                },
                            ],
                        },
                    },
                ],
            },
        }

        app = Starlette()
        app.mount("/citations", _create_citation_lookup_app(_FakeSessionRepository(serialized_session)))

        class _Chunk:
            id = "article-1_0"
            article_id = "article-1"
            chunk_index = 0
            content = "Full chunk content loaded on demand."
            title = "Overview"
            section_header = "Intro"
            summary = "Fresh summary"
            indexed_at = "2026-04-02T00:00:00Z"
            image_urls = []

        client = TestClient(app, raise_server_exceptions=False)
        with pytest.MonkeyPatch.context() as route_patch:
            route_patch.setattr("main.get_chunk_by_id", lambda document_id, security_filter=None: _Chunk())
            response = client.get("/citations/thread-123/tool-call-1/1")

        assert response.status_code == 200
        assert response.json()["status"] == "stale"

    def test_reapplies_department_filter_before_chunk_reload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REQUIRE_AUTH", "false")

        serialized_session = {
            "state": {
                "messages": [
                    {
                        "id": "tool-1",
                        "role": "tool",
                        "toolCallId": "tool-call-1",
                        "toolName": "search_knowledge_base",
                        "content": {
                            "results": [
                                {
                                    "ref_number": 1,
                                    "chunk_id": "article-1_0",
                                    "summary": "Stored summary",
                                    "content": "Stored summary",
                                    "content_source": "summary",
                                },
                            ],
                        },
                    },
                ],
            },
        }

        app = Starlette()
        app.mount("/citations", _create_citation_lookup_app(_FakeSessionRepository(serialized_session)))

        class _Chunk:
            id = "article-1_0"
            article_id = "article-1"
            chunk_index = 0
            content = "Full chunk content loaded on demand."
            title = "Overview"
            section_header = "Intro"
            summary = "Fresh summary"
            indexed_at = "2026-04-02T00:00:00Z"
            image_urls = []

        captured: dict[str, str | None] = {}
        client = TestClient(app, raise_server_exceptions=False)
        with pytest.MonkeyPatch.context() as route_patch:
            route_patch.setattr("main.resolve_departments", lambda groups: ["engineering", "marketing"])

            def _fake_get_chunk(document_id: str, security_filter: str | None = None):
                captured["document_id"] = document_id
                captured["security_filter"] = security_filter
                return _Chunk()

            route_patch.setattr("main.get_chunk_by_id", _fake_get_chunk)
            response = client.get(
                "/citations/thread-123/tool-call-1/1",
                headers={"x-user-groups": "group-a,group-b"},
            )

        assert response.status_code == 200
        assert captured == {
            "document_id": "article-1_0",
            "security_filter": "search.in(department, 'engineering,marketing', ',')",
        }

    def test_returns_missing_when_transcript_handle_is_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REQUIRE_AUTH", "false")

        app = Starlette()
        app.mount("/citations", _create_citation_lookup_app(_FakeSessionRepository({"state": {"messages": []}})))
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/citations/thread-123/tool-call-1/1")

        assert response.status_code == 200
        assert response.json() == {"status": "missing"}