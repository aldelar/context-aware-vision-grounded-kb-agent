"""Tests for whitelist loading and URL validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from mcp_web_search.whitelist import is_url_whitelisted, load_whitelist


class TestLoadWhitelist:
    """Test whitelist configuration loading."""

    def test_loads_default_whitelist(self) -> None:
        sites = load_whitelist()

        assert isinstance(sites, list)
        assert len(sites) >= 1
        assert "learn.microsoft.com" in sites

    def test_sites_are_lowercase_stripped(self) -> None:
        sites = load_whitelist()

        for site in sites:
            assert site == site.lower().strip()

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Whitelist config not found"):
            load_whitelist(tmp_path / "nonexistent.yaml")

    def test_empty_allowed_sites_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("allowed_sites: []\n")

        with pytest.raises(ValueError, match="non-empty list"):
            load_whitelist(bad)

    def test_non_mapping_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("- item1\n- item2\n")

        with pytest.raises(ValueError, match="YAML mapping"):
            load_whitelist(bad)

    def test_non_string_site_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("allowed_sites:\n  - 123\n")

        with pytest.raises(ValueError, match="non-empty string"):
            load_whitelist(bad)

    def test_custom_path(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom.yaml"
        custom.write_text(textwrap.dedent("""\
            allowed_sites:
              - example.com
              - docs.example.org
        """))

        sites = load_whitelist(custom)
        assert sites == ["example.com", "docs.example.org"]


class TestIsUrlWhitelisted:
    """Test URL whitelist checking."""

    def test_exact_match(self) -> None:
        assert is_url_whitelisted("https://learn.microsoft.com/en-us/azure", ["learn.microsoft.com"])

    def test_subdomain_match(self) -> None:
        assert is_url_whitelisted("https://sub.learn.microsoft.com/page", ["learn.microsoft.com"])

    def test_non_matching_domain(self) -> None:
        assert not is_url_whitelisted("https://evil.com/page", ["learn.microsoft.com"])

    def test_partial_domain_no_match(self) -> None:
        assert not is_url_whitelisted("https://notlearn.microsoft.com/page", ["learn.microsoft.com"])

    def test_empty_whitelist(self) -> None:
        assert not is_url_whitelisted("https://learn.microsoft.com/page", [])

    def test_malformed_url(self) -> None:
        assert not is_url_whitelisted("not-a-url", ["learn.microsoft.com"])
