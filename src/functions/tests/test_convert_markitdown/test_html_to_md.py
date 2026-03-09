"""Tests for fn_convert_markitdown.html_to_md — HTML → Markdown via MarkItDown.

Pure-local tests (no Azure calls). Runs against the sample articles in
``kb/staging/`` and synthetic HTML for edge cases.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fn_convert_markitdown.html_to_md import convert_html

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_STAGING = Path(__file__).resolve().parent.parent.parent.parent.parent / "kb" / "staging"
_CU_DIR = _STAGING / "content-understanding-overview-html_en-us"
_CU_HTML = _CU_DIR / "content-understanding-overview.html"

_SEARCH_DIR = _STAGING / "search-security-overview-html_en-us"
_SEARCH_HTML = _SEARCH_DIR / "search-security-overview.html"


# ---------------------------------------------------------------------------
# Tests against sample articles
# ---------------------------------------------------------------------------


class TestConvertHtmlSampleArticles:
    """Tests that MarkItDown converts sample articles to non-trivial Markdown."""

    @pytest.mark.skipif(not _CU_HTML.exists(), reason="CU HTML article not in staging")
    def test_cu_article_produces_markdown(self) -> None:
        md = convert_html(_CU_HTML)
        assert len(md) > 1000, f"Expected substantial markdown, got {len(md)} chars"

    @pytest.mark.skipif(not _CU_HTML.exists(), reason="CU HTML article not in staging")
    def test_cu_article_preserves_headings(self) -> None:
        md = convert_html(_CU_HTML)
        assert "# " in md or "## " in md, "Expected at least one Markdown heading"

    @pytest.mark.skipif(not _CU_HTML.exists(), reason="CU HTML article not in staging")
    def test_cu_article_preserves_links(self) -> None:
        md = convert_html(_CU_HTML)
        assert "](http" in md, "Expected at least one Markdown hyperlink"

    @pytest.mark.skipif(not _SEARCH_HTML.exists(), reason="Search HTML article not in staging")
    def test_search_article_produces_markdown(self) -> None:
        md = convert_html(_SEARCH_HTML)
        assert len(md) > 1000


# ---------------------------------------------------------------------------
# Edge cases with synthetic HTML
# ---------------------------------------------------------------------------


class TestConvertHtmlEdgeCases:
    """Tests with synthetic HTML fragments."""

    def test_simple_html(self, tmp_path: Path) -> None:
        html = tmp_path / "simple.html"
        html.write_text("<html><body><h1>Title</h1><p>Hello world</p></body></html>")
        md = convert_html(html)
        assert "Title" in md
        assert "Hello" in md

    def test_html_with_table(self, tmp_path: Path) -> None:
        html = tmp_path / "table.html"
        html.write_text(
            "<html><body>"
            "<table><tr><th>Name</th><th>Value</th></tr>"
            "<tr><td>A</td><td>1</td></tr></table>"
            "</body></html>"
        )
        md = convert_html(html)
        assert "Name" in md
        assert "Value" in md

    def test_html_with_links(self, tmp_path: Path) -> None:
        html = tmp_path / "links.html"
        html.write_text(
            '<html><body><a href="https://example.com">Example</a></body></html>'
        )
        md = convert_html(html)
        assert "Example" in md
        assert "https://example.com" in md

    def test_empty_body(self, tmp_path: Path) -> None:
        html = tmp_path / "empty.html"
        html.write_text("<html><body></body></html>")
        md = convert_html(html)
        assert isinstance(md, str)

    def test_returns_string(self, tmp_path: Path) -> None:
        html = tmp_path / "basic.html"
        html.write_text("<html><body><p>Test</p></body></html>")
        result = convert_html(html)
        assert isinstance(result, str)
