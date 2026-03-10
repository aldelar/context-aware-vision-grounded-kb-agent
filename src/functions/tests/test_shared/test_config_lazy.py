"""Tests for shared.config lazy-loading behavior."""

import importlib

import pytest


def _no_env_file():
    """Prevent .env loading so monkeypatch controls all env vars."""
    return None


class TestImportDoesNotCrash:
    """Importing shared.config must not crash even without env vars."""

    def test_import_config_module_without_env_vars(self, monkeypatch):
        """Importing the module should succeed — no sys.exit, no KeyError."""
        for var in (
            "AI_SERVICES_ENDPOINT",
            "SEARCH_ENDPOINT",
            "STAGING_BLOB_ENDPOINT",
            "SERVING_BLOB_ENDPOINT",
        ):
            monkeypatch.delenv(var, raising=False)

        import shared.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "_find_env_file", _no_env_file)
        cfg_mod._config = None

        # The import itself must not raise
        importlib.reload(cfg_mod)

    def test_config_proxy_attribute_access_without_env_vars(self, monkeypatch):
        """The module-level `config` proxy must be accessible without crash."""
        for var in (
            "AI_SERVICES_ENDPOINT",
            "SEARCH_ENDPOINT",
            "STAGING_BLOB_ENDPOINT",
            "SERVING_BLOB_ENDPOINT",
        ):
            monkeypatch.delenv(var, raising=False)

        import shared.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "_find_env_file", _no_env_file)
        cfg_mod._config = None
        endpoint = cfg_mod.config.search_endpoint
        assert isinstance(endpoint, str)


class TestGetConfigDefaults:
    """get_config() returns a Config with empty-string defaults when env vars are unset."""

    def test_returns_empty_strings_without_env_vars(self, monkeypatch):
        for var in (
            "AI_SERVICES_ENDPOINT",
            "SEARCH_ENDPOINT",
            "STAGING_BLOB_ENDPOINT",
            "SERVING_BLOB_ENDPOINT",
            "SEARCH_INDEX_NAME",
            "EMBEDDING_DEPLOYMENT_NAME",
            "MISTRAL_DEPLOYMENT_NAME",
        ):
            monkeypatch.delenv(var, raising=False)

        import shared.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "_find_env_file", _no_env_file)
        cfg_mod._config = None
        cfg = cfg_mod.get_config()

        assert cfg.ai_services_endpoint == ""
        assert cfg.search_endpoint == ""
        assert cfg.staging_blob_endpoint == ""
        assert cfg.serving_blob_endpoint == ""

    def test_default_index_name(self, monkeypatch):
        monkeypatch.delenv("SEARCH_INDEX_NAME", raising=False)

        import shared.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "_find_env_file", _no_env_file)
        cfg_mod._config = None
        cfg = cfg_mod.get_config()
        assert cfg.search_index_name == "kb-articles"

    def test_default_embedding_deployment(self, monkeypatch):
        monkeypatch.delenv("EMBEDDING_DEPLOYMENT_NAME", raising=False)

        import shared.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "_find_env_file", _no_env_file)
        cfg_mod._config = None
        cfg = cfg_mod.get_config()
        assert cfg.embedding_deployment_name == "text-embedding-3-small"


class TestGetConfigPicksUpEnvVars:
    """get_config() reads env vars when they are set."""

    def test_reads_all_env_vars(self, monkeypatch):
        monkeypatch.setenv("AI_SERVICES_ENDPOINT", "https://ai.example.com")
        monkeypatch.setenv("SEARCH_ENDPOINT", "https://search.example.com")
        monkeypatch.setenv("STAGING_BLOB_ENDPOINT", "https://staging.blob.example.com")
        monkeypatch.setenv("SERVING_BLOB_ENDPOINT", "https://serving.blob.example.com")
        monkeypatch.setenv("SEARCH_INDEX_NAME", "custom-index")
        monkeypatch.setenv("EMBEDDING_DEPLOYMENT_NAME", "custom-embed")
        monkeypatch.setenv("MISTRAL_DEPLOYMENT_NAME", "custom-mistral")

        import shared.config as cfg_mod

        cfg_mod._config = None
        cfg = cfg_mod.get_config()

        assert cfg.ai_services_endpoint == "https://ai.example.com"
        assert cfg.search_endpoint == "https://search.example.com"
        assert cfg.staging_blob_endpoint == "https://staging.blob.example.com"
        assert cfg.serving_blob_endpoint == "https://serving.blob.example.com"
        assert cfg.search_index_name == "custom-index"
        assert cfg.embedding_deployment_name == "custom-embed"
        assert cfg.mistral_deployment_name == "custom-mistral"

    def test_is_azure_mode_when_blob_endpoints_set(self, monkeypatch):
        monkeypatch.setenv("STAGING_BLOB_ENDPOINT", "https://staging.blob.example.com")
        monkeypatch.setenv("SERVING_BLOB_ENDPOINT", "https://serving.blob.example.com")

        import shared.config as cfg_mod

        cfg_mod._config = None
        cfg = cfg_mod.get_config()
        assert cfg.is_azure_mode is True

    def test_not_azure_mode_without_blob_endpoints(self, monkeypatch):
        monkeypatch.delenv("STAGING_BLOB_ENDPOINT", raising=False)
        monkeypatch.delenv("SERVING_BLOB_ENDPOINT", raising=False)

        import shared.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "_find_env_file", _no_env_file)
        cfg_mod._config = None
        cfg = cfg_mod.get_config()
        assert cfg.is_azure_mode is False


class TestConfigProxy:
    """The module-level `config` proxy forwards attribute access to Config."""

    def test_proxy_forwards_search_endpoint(self, monkeypatch):
        monkeypatch.setenv("SEARCH_ENDPOINT", "https://proxy-test.example.com")

        import shared.config as cfg_mod

        cfg_mod._config = None
        assert cfg_mod.config.search_endpoint == "https://proxy-test.example.com"

    def test_proxy_forwards_index_name(self, monkeypatch):
        monkeypatch.setenv("SEARCH_INDEX_NAME", "proxy-index")

        import shared.config as cfg_mod

        cfg_mod._config = None
        assert cfg_mod.config.search_index_name == "proxy-index"

    def test_proxy_raises_on_nonexistent_attr(self, monkeypatch):
        import shared.config as cfg_mod

        cfg_mod._config = None
        with pytest.raises(AttributeError):
            _ = cfg_mod.config.this_does_not_exist


class TestAgentDeploymentNameRemoved:
    """agent_deployment_name must NOT be an attribute on Config."""

    def test_config_has_no_agent_deployment_name(self):
        from shared.config import Config

        assert not hasattr(Config, "agent_deployment_name")
        cfg = Config()
        assert not hasattr(cfg, "agent_deployment_name")
