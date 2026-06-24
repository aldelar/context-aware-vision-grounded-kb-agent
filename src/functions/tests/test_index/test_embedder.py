"""Unit tests for fn_index.embedder."""

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from fn_index.chunker import Chunk
from fn_index.embedder import embed_chunks, embed_text


class TestEmbedText:
    """Test single-text embedding."""

    @patch("fn_index.embedder._get_client")
    def test_returns_vector(self, mock_get_client):
        mock_backend = MagicMock()
        mock_backend.embed.return_value = [[0.1, 0.2, 0.3]]
        mock_get_client.return_value = mock_backend

        vector = embed_text("Hello world, this is a test sentence.")

        assert vector == [0.1, 0.2, 0.3]
        mock_backend.embed.assert_called_once_with(["Hello world, this is a test sentence."])

    @patch("fn_index.embedder._get_client")
    def test_non_empty_vectors(self, mock_get_client):
        mock_backend = MagicMock()
        mock_backend.embed.return_value = [[0.0, 0.5, 0.0]]
        mock_get_client.return_value = mock_backend

        vector = embed_text("Azure AI Search enables vector search.")

        assert any(v != 0.0 for v in vector)


class TestEmbedChunks:
    """Test batch chunk embedding."""

    @patch("fn_index.embedder._get_client")
    def test_prod_uses_batch_embedding(self, mock_get_client, monkeypatch):
        monkeypatch.setattr(
            "fn_index.embedder.config",
            SimpleNamespace(is_dev=False, embedding_deployment_name="test-embedding"),
        )
        mock_backend = MagicMock()
        mock_backend.embed.return_value = [
            [0.1, 0.2],
            [0.3, 0.4],
        ]
        mock_get_client.return_value = mock_backend

        chunks = [
            Chunk(content="First chunk.", title="Test", section_header="", image_refs=[]),
            Chunk(content="Second chunk.", title="Test", section_header="S2", image_refs=["img.png"]),
        ]
        results = embed_chunks(chunks)
        assert len(results) == 2
        assert results[0]["content_vector"] == [0.1, 0.2]
        assert results[1]["content_vector"] == [0.3, 0.4]
        mock_backend.embed.assert_called_once_with(["First chunk.", "Second chunk."])

    @patch("fn_index.embedder._get_client")
    def test_dev_embeds_chunks_one_at_a_time(self, mock_get_client, monkeypatch):
        monkeypatch.setattr(
            "fn_index.embedder.config",
            SimpleNamespace(is_dev=True, embedding_deployment_name="test-embedding"),
        )
        mock_backend = MagicMock()
        mock_backend.embed.side_effect = [
            [[0.1, 0.2]],
            [[0.3, 0.4]],
        ]
        mock_get_client.return_value = mock_backend

        chunks = [
            Chunk(content="First chunk.", title="Test", section_header="", image_refs=[]),
            Chunk(content="Second chunk.", title="Test", section_header="S2", image_refs=["img.png"]),
        ]
        results = embed_chunks(chunks)

        assert [r["content_vector"] for r in results] == [[0.1, 0.2], [0.3, 0.4]]
        assert mock_backend.embed.call_args_list == [
            call(["First chunk."]),
            call(["Second chunk."]),
        ]

    def test_dev_dimensions_default_to_1024(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "dev")
        monkeypatch.delenv("EMBEDDING_VECTOR_DIMENSIONS", raising=False)

        import shared.config as cfg_mod

        cfg_mod._config = None
        assert cfg_mod.get_config().embedding_vector_dimensions == 1024


