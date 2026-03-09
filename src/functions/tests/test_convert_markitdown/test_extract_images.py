"""Tests for fn_convert_markitdown.extract_images — HTML DOM image extraction.

Pure-local tests (no Azure calls). Runs against the sample articles in
``kb/staging/`` and synthetic HTML for edge cases.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fn_convert_markitdown.extract_images import extract_image_map

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_STAGING = Path(__file__).resolve().parent.parent.parent.parent.parent / "kb" / "staging"
_CU_DIR = _STAGING / "content-understanding-overview-html_en-us"
_CU_HTML = _CU_DIR / "content-understanding-overview.html"


# ---------------------------------------------------------------------------
# Tests against sample articles
# ---------------------------------------------------------------------------


class TestExtractImageMapSampleArticles:
    """Tests that extract_image_map finds images in sample articles."""

    @pytest.mark.skipif(not _CU_HTML.exists(), reason="CU HTML article not in staging")
    def test_cu_article_image_count(self) -> None:
        """CU HTML article has 2 image references (same image used twice)."""
        image_map = extract_image_map(_CU_HTML)
        assert len(image_map) == 2

    @pytest.mark.skipif(not _CU_HTML.exists(), reason="CU HTML article not in staging")
    def test_cu_article_image_stem(self) -> None:
        """CU HTML image stems are content-understanding-framework-2025."""
        image_map = extract_image_map(_CU_HTML)
        for _, stem in image_map:
            assert stem == "content-understanding-framework-2025"

    @pytest.mark.skipif(not _CU_HTML.exists(), reason="CU HTML article not in staging")
    def test_cu_article_preceding_text_differs(self) -> None:
        """Each occurrence of the same image has different preceding text."""
        image_map = extract_image_map(_CU_HTML)
        texts = [text for text, _ in image_map]
        assert len(set(texts)) == 2, "Same image used twice should have 2 distinct preceding texts"

    @pytest.mark.skipif(not _CU_HTML.exists(), reason="CU HTML article not in staging")
    def test_returns_tuples(self) -> None:
        """Each entry is a (preceding_text, stem) tuple."""
        image_map = extract_image_map(_CU_HTML)
        for item in image_map:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)
            assert isinstance(item[1], str)


# ---------------------------------------------------------------------------
# Edge cases with synthetic HTML
# ---------------------------------------------------------------------------


class TestExtractImageMapEdgeCases:
    """Tests with synthetic HTML fragments."""

    def test_no_images(self, tmp_path: Path) -> None:
        html = tmp_path / "no_images.html"
        html.write_text("<html><body><p>Hello world</p></body></html>")
        assert extract_image_map(html) == []

    def test_single_image(self, tmp_path: Path) -> None:
        html = tmp_path / "one_img.html"
        html.write_text(
            "<html><body>"
            "<p>Some preceding text here</p>"
            '<img src="images/shot.png">'
            "</body></html>"
        )
        result = extract_image_map(html)
        assert len(result) == 1
        assert result[0][1] == "shot"

    def test_image_without_src_skipped(self, tmp_path: Path) -> None:
        html = tmp_path / "no_src.html"
        html.write_text("<html><body><img></body></html>")
        assert extract_image_map(html) == []

    def test_image_stem_strips_extension(self, tmp_path: Path) -> None:
        html = tmp_path / "ext.html"
        html.write_text(
            '<html><body><p>Context text for position matching</p>'
            '<img src="images/my-diagram.png"></body></html>'
        )
        result = extract_image_map(html)
        assert result[0][1] == "my-diagram"

    def test_multiple_images(self, tmp_path: Path) -> None:
        html = tmp_path / "multi.html"
        html.write_text(
            "<html><body>"
            "<p>First paragraph with enough text</p>"
            '<img src="images/a.png">'
            "<p>Second paragraph with enough text</p>"
            '<img src="images/b.png">'
            "</body></html>"
        )
        result = extract_image_map(html)
        assert len(result) == 2
        stems = [stem for _, stem in result]
        assert "a" in stems
        assert "b" in stems

    def test_malformed_html_doesnt_crash(self, tmp_path: Path) -> None:
        html = tmp_path / "bad.html"
        html.write_text("<html><body><img src='test.png'><p>no close tags")
        result = extract_image_map(html)
        assert isinstance(result, list)
