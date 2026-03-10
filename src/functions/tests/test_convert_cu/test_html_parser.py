"""Tests for fn_convert_cu.html_parser — HTML DOM parsing for image/link maps.

Pure-local tests (no Azure calls). Runs against the sample articles in
``kb/staging/`` and synthetic HTML fragments for edge cases.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fn_convert_cu.html_parser import extract_image_map, extract_link_map

# ---------------------------------------------------------------------------
# Paths (computed once, no fixture dependency)
# ---------------------------------------------------------------------------

_STAGING = Path(__file__).resolve().parent.parent.parent.parent.parent / "kb" / "staging"
_CLEAN_DIR = _STAGING / "content-understanding-overview-html_en-us"

_CLEAN_HTML = _CLEAN_DIR / "content-understanding-overview.html"


# ---------------------------------------------------------------------------
# Image map tests
# ---------------------------------------------------------------------------


class TestExtractImageMap:
    """Tests for extract_image_map()."""

    @pytest.mark.skipif(not _CLEAN_HTML.exists(), reason="Clean HTML article not in staging")
    def test_clean_html_image_count(self) -> None:
        """Clean HTML article has 2 image references (same image used twice)."""
        image_map = extract_image_map(_CLEAN_HTML)
        assert len(image_map) == 2

    @pytest.mark.skipif(not _CLEAN_HTML.exists(), reason="Clean HTML article not in staging")
    def test_clean_html_image_filename(self) -> None:
        """Clean HTML image stem is content-understanding-framework-2025."""
        image_map = extract_image_map(_CLEAN_HTML)
        for _, stem in image_map:
            assert stem == "content-understanding-framework-2025"

    @pytest.mark.skipif(not _CLEAN_HTML.exists(), reason="Clean HTML article not in staging")
    def test_clean_html_preceding_text_differs(self) -> None:
        """Each occurrence of the same image has different preceding text."""
        image_map = extract_image_map(_CLEAN_HTML)
        texts = [text for text, _ in image_map]
        assert len(set(texts)) == 2, "Same image used twice should have 2 distinct preceding texts"

    def test_no_images(self, tmp_path: Path) -> None:
        """HTML with no images returns empty list."""
        html = tmp_path / "no_images.html"
        html.write_text("<html><body><p>Hello world</p></body></html>")
        assert extract_image_map(html) == []

    def test_malformed_html(self, tmp_path: Path) -> None:
        """Malformed HTML doesn't crash."""
        html = tmp_path / "bad.html"
        html.write_text("<html><body><img src='test.png'><p>no close tags")
        result = extract_image_map(html)
        # Should still find the image (BeautifulSoup is lenient)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Link map tests
# ---------------------------------------------------------------------------


class TestExtractLinkMap:
    """Tests for extract_link_map()."""

    @pytest.mark.skipif(not _CLEAN_HTML.exists(), reason="Clean HTML article not in staging")
    def test_clean_html_link_count(self) -> None:
        """Clean HTML article has many links."""
        link_map = extract_link_map(_CLEAN_HTML)
        assert len(link_map) >= 5

    @pytest.mark.skipif(not _CLEAN_HTML.exists(), reason="Clean HTML article not in staging")
    def test_clean_html_excludes_image_links(self) -> None:
        """Links wrapping images are excluded from the link map."""
        link_map = extract_link_map(_CLEAN_HTML)
        urls = [url for _, url in link_map]
        # The <a> tags wrapping images point to .png files
        assert not any(url.endswith(".png") for url in urls)

    @pytest.mark.skipif(not _CLEAN_HTML.exists(), reason="Clean HTML article not in staging")
    def test_clean_html_link_urls(self) -> None:
        """Links have valid URLs."""
        link_map = extract_link_map(_CLEAN_HTML)
        for _, url in link_map:
            assert url.startswith("http"), f"Expected http URL, got: {url!r}"

    def test_no_links(self, tmp_path: Path) -> None:
        """HTML with no links returns empty list."""
        html = tmp_path / "no_links.html"
        html.write_text("<html><body><p>No links here</p></body></html>")
        assert extract_link_map(html) == []

    def test_anchor_links_excluded(self, tmp_path: Path) -> None:
        """Internal anchor links (#section) are excluded."""
        html = tmp_path / "anchors.html"
        html.write_text(
            '<html><body>'
            '<a href="#section1">Section 1</a>'
            '<a href="https://example.com">External</a>'
            '</body></html>'
        )
        link_map = extract_link_map(html)
        assert len(link_map) == 1
        assert link_map[0] == ("External", "https://example.com")
