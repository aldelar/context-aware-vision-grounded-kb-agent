"""Tests for fn_convert_markitdown.merge — image block replacement and article assembly.

Tests the MarkItDown-specific merge logic: replacing ``[![alt](images/…)](images/…)``
patterns with styled image blocks, and the ``_clean_description`` helper.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from fn_convert_markitdown.merge import (
    _MARKITDOWN_IMAGE_RE,
    _clean_description,
    _find_source_image,
    merge_article,
)


# ---------------------------------------------------------------------------
# _MARKITDOWN_IMAGE_RE — regex tests
# ---------------------------------------------------------------------------


class TestMarkItDownImageRegex:
    """Tests for the regex that matches MarkItDown image references."""

    def test_matches_standard_pattern(self):
        text = "[![diagram](images/arch.png)](images/arch.png)"
        m = _MARKITDOWN_IMAGE_RE.search(text)
        assert m is not None
        assert m.group(1) == "images/arch.png"

    def test_matches_empty_alt(self):
        text = "[![](images/shot.png)](images/shot.png)"
        m = _MARKITDOWN_IMAGE_RE.search(text)
        assert m is not None

    def test_no_match_plain_image(self):
        """Plain markdown image (no link wrapper) should not match."""
        text = "![alt](images/shot.png)"
        m = _MARKITDOWN_IMAGE_RE.search(text)
        assert m is None

    def test_no_match_plain_text(self):
        assert _MARKITDOWN_IMAGE_RE.search("no images here") is None

    def test_captures_path(self):
        text = "[![alt text](images/my-diagram.png)](images/my-diagram.png)"
        m = _MARKITDOWN_IMAGE_RE.search(text)
        assert m.group(1) == "images/my-diagram.png"


# ---------------------------------------------------------------------------
# _clean_description
# ---------------------------------------------------------------------------


class TestCleanDescription:
    """Tests for the GPT description cleanup helper."""

    def test_structured_description_extracted(self):
        raw = (
            "1. **Description**: A diagram showing the data flow.\n"
            "2. **UIElements**: None.\n"
            "3. **NavigationPath**: N/A."
        )
        result = _clean_description(raw)
        assert result == "A diagram showing the data flow"

    def test_ui_elements_included_when_meaningful(self):
        raw = (
            "1. **Description**: A screenshot of the settings page.\n"
            "2. **UIElements**: Save button, Cancel button.\n"
            "3. **NavigationPath**: Settings > General."
        )
        result = _clean_description(raw)
        assert "A screenshot of the settings page" in result
        assert "Save button, Cancel button" in result
        assert "Settings > General" in result

    def test_none_ui_elements_excluded(self):
        raw = (
            "1. **Description**: An architecture diagram.\n"
            "2. **UIElements**: None.\n"
            "3. **NavigationPath**: N/A."
        )
        result = _clean_description(raw)
        assert "None" not in result
        assert "N/A" not in result

    def test_plain_text_passthrough(self):
        raw = "Just a plain description without structure."
        result = _clean_description(raw)
        assert result == raw.strip()


# ---------------------------------------------------------------------------
# _find_source_image
# ---------------------------------------------------------------------------


class TestFindSourceImage:
    """Tests for the source image finder."""

    def test_finds_png_in_images_subdir(self, tmp_path):
        (tmp_path / "images").mkdir()
        (tmp_path / "images" / "shot.png").write_bytes(b"\x89PNG")
        result = _find_source_image(tmp_path, "shot")
        assert result is not None
        assert result.name == "shot.png"

    def test_finds_jpg_in_images_subdir(self, tmp_path):
        (tmp_path / "images").mkdir()
        (tmp_path / "images" / "photo.jpg").write_bytes(b"\xff\xd8")
        result = _find_source_image(tmp_path, "photo")
        assert result is not None
        assert result.name == "photo.jpg"

    def test_finds_in_root_dir(self, tmp_path):
        (tmp_path / "shot.png").write_bytes(b"\x89PNG")
        result = _find_source_image(tmp_path, "shot")
        assert result is not None

    def test_returns_none_when_missing(self, tmp_path):
        result = _find_source_image(tmp_path, "nonexistent")
        assert result is None

    def test_prefers_images_subdir(self, tmp_path):
        """images/ subdir is checked before root."""
        (tmp_path / "images").mkdir()
        (tmp_path / "images" / "shot.png").write_bytes(b"in-images")
        (tmp_path / "shot.png").write_bytes(b"in-root")
        result = _find_source_image(tmp_path, "shot")
        assert result is not None
        assert "images" in str(result)


# ---------------------------------------------------------------------------
# merge_article — full assembly
# ---------------------------------------------------------------------------


class TestMergeArticle:
    """Tests for the full article assembly."""

    def test_image_ref_replaced_with_block(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "images").mkdir()
        (staging / "images" / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        output = tmp_path / "output"

        merge_article(
            markdown="Intro text\n\n[![screenshot](images/shot.png)](images/shot.png)\n\nMore text",
            image_map=[("Intro text", "shot")],
            descriptions={"shot": "A screenshot showing the dashboard."},
            staging_dir=staging,
            output_dir=output,
        )

        article = (output / "article.md").read_text()
        assert "> **[Image: shot](images/shot.png)**" in article
        assert "> A screenshot showing the dashboard." in article
        assert "[![screenshot]" not in article
        assert (output / "images" / "shot.png").exists()

    def test_structured_description_cleaned(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "images").mkdir()
        (staging / "images" / "arch.png").write_bytes(b"\x89PNG")

        output = tmp_path / "output"

        merge_article(
            markdown="Text before\n\n[![arch](images/arch.png)](images/arch.png)\n\nText after",
            image_map=[("Text before", "arch")],
            descriptions={
                "arch": (
                    "1. **Description**: Architecture overview diagram.\n"
                    "2. **UIElements**: None.\n"
                    "3. **NavigationPath**: N/A."
                )
            },
            staging_dir=staging,
            output_dir=output,
        )

        article = (output / "article.md").read_text()
        assert "> Architecture overview diagram" in article
        assert "UIElements" not in article

    def test_missing_image_warns_but_continues(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()

        output = tmp_path / "output"

        merge_article(
            markdown="[![missing](images/missing.png)](images/missing.png)",
            image_map=[("", "missing")],
            descriptions={"missing": "Missing image."},
            staging_dir=staging,
            output_dir=output,
        )

        article = (output / "article.md").read_text()
        assert "> **[Image: missing](images/missing.png)**" in article

    def test_no_images_passthrough(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()

        output = tmp_path / "output"

        merge_article(
            markdown="# Title\n\nJust text, no images.",
            image_map=[],
            descriptions={},
            staging_dir=staging,
            output_dir=output,
        )

        article = (output / "article.md").read_text()
        assert "# Title" in article
        assert "Just text, no images." in article

    def test_multiple_images(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "images").mkdir()
        (staging / "images" / "a.png").write_bytes(b"\x89PNG")
        (staging / "images" / "b.png").write_bytes(b"\x89PNG")

        output = tmp_path / "output"

        merge_article(
            markdown=(
                "Intro\n\n"
                "[![img a](images/a.png)](images/a.png)\n\n"
                "Middle\n\n"
                "[![img b](images/b.png)](images/b.png)\n\n"
                "End"
            ),
            image_map=[("Intro", "a"), ("Middle", "b")],
            descriptions={"a": "Image A desc.", "b": "Image B desc."},
            staging_dir=staging,
            output_dir=output,
        )

        article = (output / "article.md").read_text()
        assert "> **[Image: a](images/a.png)**" in article
        assert "> **[Image: b](images/b.png)**" in article
        assert (output / "images" / "a.png").exists()
        assert (output / "images" / "b.png").exists()

    def test_output_dir_created(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()

        output = tmp_path / "deeply" / "nested" / "output"

        merge_article(
            markdown="text",
            image_map=[],
            descriptions={},
            staging_dir=staging,
            output_dir=output,
        )

        assert (output / "article.md").exists()
