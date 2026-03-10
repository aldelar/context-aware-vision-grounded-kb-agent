"""Tests for main.py helper functions (context management, agent client)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.main import (
    Citation,  # re-exported from app.main
    _build_citation_content,
    _build_filename_lookup,
    _build_ref_map,
    _create_agent_client,
    _estimate_tokens,
    _expand_ref_markers,
    _get_user_id,
    _is_oauth_configured,
    _normalise_inline_images,
    _remap_ref_numbers,
    _rewrite_image_refs,
    _strip_md_images,
    _trim_context,
)


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

class TestEstimateTokens:
    """Test _estimate_tokens heuristic."""

    def test_empty_string(self) -> None:
        assert _estimate_tokens("") == 0

    def test_short_string(self) -> None:
        # 12 chars → 3 tokens
        assert _estimate_tokens("Hello world!") == 3

    def test_longer_string(self) -> None:
        text = "a" * 400
        assert _estimate_tokens(text) == 100


# ---------------------------------------------------------------------------
# Context trimming
# ---------------------------------------------------------------------------

class TestTrimContext:
    """Test _trim_context window management."""

    def test_no_trimming_when_under_limit(self) -> None:
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = _trim_context(messages, max_tokens=1000)
        assert len(result) == 2

    def test_trimming_when_over_limit(self) -> None:
        # Each message is 400 chars → 100 tokens.  Limit = 150 tokens.
        messages = [
            {"role": "user", "content": "a" * 400},
            {"role": "assistant", "content": "b" * 400},
            {"role": "user", "content": "c" * 400},
        ]
        result = _trim_context(messages, max_tokens=150)
        # Should drop oldest until under limit — keeps last 1 message
        assert len(result) < 3

    def test_never_trims_to_empty(self) -> None:
        messages = [{"role": "user", "content": "a" * 10000}]
        result = _trim_context(messages, max_tokens=1)
        assert len(result) == 1

    def test_returns_new_list(self) -> None:
        messages = [{"role": "user", "content": "test"}]
        result = _trim_context(messages, max_tokens=1000)
        assert result is messages  # No copy when no trimming needed


# ---------------------------------------------------------------------------
# Agent client creation
# ---------------------------------------------------------------------------

class TestCreateAgentClient:
    """Test _create_agent_client dual-mode factory."""

    @patch("app.main.config")
    def test_local_mode(self, mock_config: MagicMock) -> None:
        mock_config.agent_endpoint = "http://localhost:8088"

        client = _create_agent_client()

        assert client.api_key == "local"
        assert client.base_url.host == "localhost"

    @patch("app.main.config")
    def test_foundry_mode(self, mock_config: MagicMock) -> None:
        mock_config.agent_endpoint = "https://my-foundry.ai.azure.com/agents"

        with patch("app.main.OpenAI") as mock_openai:
            with patch("azure.identity.DefaultAzureCredential"):
                with patch("azure.identity.get_bearer_token_provider") as mock_token:
                    mock_token.return_value = lambda: "fake-token"
                    _create_agent_client()

                    mock_openai.assert_called_once()
                    call_kwargs = mock_openai.call_args[1]
                    assert call_kwargs["base_url"] == "https://my-foundry.ai.azure.com/agents"
                    assert call_kwargs["api_key"] == "fake-token"


# ---------------------------------------------------------------------------
# Ref mapping
# ---------------------------------------------------------------------------

class TestBuildRefMap:
    """Test citation de-duplication."""

    def test_deduplicates_same_section(self) -> None:
        cits = [
            Citation("a1", "Title", "Section 1", 0),
            Citation("a1", "Title", "Section 1", 1),
            Citation("a1", "Title", "Section 2", 0),
        ]
        unique, mapping = _build_ref_map(cits)
        assert len(unique) == 2
        assert mapping == {1: 1, 2: 1, 3: 2}

    def test_empty_list(self) -> None:
        unique, mapping = _build_ref_map([])
        assert unique == []
        assert mapping == {}


class TestRemapRefNumbers:
    """Test ref number rewriting."""

    def test_remaps_numbers(self) -> None:
        text = "See Ref #1 and [Ref #3] for details."
        mapping = {1: 1, 2: 1, 3: 2}
        result = _remap_ref_numbers(text, mapping)
        assert "Ref #1" in result
        assert "Ref #2" in result
        assert "#3" not in result


class TestExpandRefMarkers:
    """Test bracket removal and combined ref expansion."""

    def test_single_ref(self) -> None:
        assert _expand_ref_markers("[Ref #1]") == "Ref #1"

    def test_combined_refs(self) -> None:
        result = _expand_ref_markers("[Ref #1, #5]")
        assert result == "Ref #1, Ref #5"


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

class TestStripMdImages:
    """Test markdown image removal."""

    def test_strips_images(self) -> None:
        text = "Before ![alt](http://example.com/img.png) after"
        assert "![" not in _strip_md_images(text)

    def test_preserves_non_images(self) -> None:
        text = "No images here"
        assert _strip_md_images(text) == text


class TestRewriteImageRefs:
    """Test [Image: name](images/file.png) rewriting."""

    def test_rewrites_to_proxy(self) -> None:
        text = "[Image: diagram](images/arch.png)"
        result = _rewrite_image_refs(text, "my-article")
        assert result == "![diagram](/api/images/my-article/images/arch.png)"


class TestNormaliseInlineImages:
    """Test comprehensive image URL normalisation."""

    def test_normalises_api_path(self) -> None:
        text = "![fig](api/images/article/images/f.png)"
        result = _normalise_inline_images(text, [])
        assert result == "![fig](/api/images/article/images/f.png)"

    def test_strips_hallucinated_domain(self) -> None:
        text = "![fig](https://learn.microsoft.com/api/images/article/images/f.png)"
        result = _normalise_inline_images(text, [])
        assert result == "![fig](/api/images/article/images/f.png)"

    def test_unresolvable_becomes_italic(self) -> None:
        text = "![fig](https://unknown.example.com/random.png)"
        result = _normalise_inline_images(text, [])
        assert "*[Image: fig]*" in result


class TestBuildFilenameLooup:
    """Test filename → proxy URL map building."""

    def test_builds_lookup(self) -> None:
        cits = [
            Citation("a1", "T", "S", 0, image_urls=["images/fig1.png", "images/fig2.png"]),
        ]
        lookup = _build_filename_lookup(cits)
        assert "fig1.png" in lookup
        assert "fig2.png" in lookup
        assert lookup["fig1.png"] == "/api/images/a1/images/fig1.png"

    def test_empty_citations(self) -> None:
        assert _build_filename_lookup([]) == {}


# ---------------------------------------------------------------------------
# OAuth configuration detection
# ---------------------------------------------------------------------------


class TestIsOauthConfigured:

    def test_true_when_env_set(self) -> None:
        with patch.dict("os.environ", {"OAUTH_AZURE_AD_CLIENT_ID": "some-client-id"}):
            assert _is_oauth_configured() is True

    def test_false_when_env_unset(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("OAUTH_AZURE_AD_CLIENT_ID", None)
            assert _is_oauth_configured() is False

    def test_false_when_env_empty(self) -> None:
        with patch.dict("os.environ", {"OAUTH_AZURE_AD_CLIENT_ID": ""}):
            assert _is_oauth_configured() is False


# ---------------------------------------------------------------------------
# User identity helper  (_get_user_id)
# ---------------------------------------------------------------------------


class TestGetUserId:
    """Covers the three code paths in _get_user_id()."""

    def test_returns_chainlit_user_identifier(self) -> None:
        """Path 1: authenticated Chainlit user (OAuth or header callback)."""
        import chainlit as cl

        mock_user = MagicMock(spec=cl.User)
        mock_user.identifier = "oid-abc-123"
        mock_user.metadata = {}  # override MagicMock auto-attr so .get("oid") isn't truthy

        with patch("chainlit.user_session") as mock_session:
            mock_session.get.side_effect = lambda key: {
                "user": mock_user,
            }.get(key)
            assert _get_user_id() == "oid-abc-123"

    def test_returns_easy_auth_header(self) -> None:
        """Path 2: no Chainlit user, but Easy Auth header present."""
        with patch("chainlit.user_session") as mock_session:
            def side_effect(key):
                if key == "user":
                    return None
                if key == "http_headers":
                    return {"x-ms-client-principal-id": "header-principal-456"}
                return None
            mock_session.get.side_effect = side_effect
            assert _get_user_id() == "header-principal-456"

    def test_returns_local_user_fallback(self) -> None:
        """Path 3: no auth at all — local dev mode."""
        with patch("chainlit.user_session") as mock_session:
            mock_session.get.side_effect = lambda key: None
            assert _get_user_id() == "local-user"

    def test_returns_local_user_on_exception(self) -> None:
        """Edge: user_session raises — treat as local dev."""
        with patch("chainlit.user_session") as mock_session:
            mock_session.get.side_effect = RuntimeError("no session")
            assert _get_user_id() == "local-user"
