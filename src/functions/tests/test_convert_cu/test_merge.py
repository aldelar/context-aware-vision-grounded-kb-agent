"""Unit tests for fn_convert_cu.merge — link recovery and image block insertion."""

import pytest

from fn_convert_cu.cu_images import ImageAnalysisResult
from fn_convert_cu.merge import (
    _format_image_block,
    _insert_after_text,
    _normalize_for_match,
    insert_image_blocks,
    recover_links,
)


# ---------------------------------------------------------------------------
# recover_links
# ---------------------------------------------------------------------------


class TestRecoverLinks:
    """Tests for hyperlink re-injection into CU Markdown."""

    def test_single_link_injected(self):
        md = "For details, see Adding or Changing Roles in the help center."
        link_map = [("Adding or Changing Roles", "https://example.com/roles")]
        result = recover_links(md, link_map)
        assert "[Adding or Changing Roles](https://example.com/roles)" in result

    def test_existing_link_not_doubled(self):
        md = "See [Adding Roles](https://example.com/roles) for details."
        link_map = [("Adding Roles", "https://example.com/roles")]
        result = recover_links(md, link_map)
        # Should not create a nested link
        assert result.count("[Adding Roles]") == 1

    def test_multiple_links(self):
        md = "Use Feature A and Feature B for best results."
        link_map = [
            ("Feature A", "https://example.com/a"),
            ("Feature B", "https://example.com/b"),
        ]
        result = recover_links(md, link_map)
        assert "[Feature A](https://example.com/a)" in result
        assert "[Feature B](https://example.com/b)" in result

    def test_missing_text_skipped(self):
        md = "This text has no matching link labels."
        link_map = [("nonexistent", "https://example.com")]
        result = recover_links(md, link_map)
        assert result == md  # Unchanged

    def test_empty_link_map(self):
        md = "Some markdown text."
        result = recover_links(md, [])
        assert result == md

    def test_first_occurrence_only(self):
        md = "Use Feature A here. Also use Feature A there."
        link_map = [("Feature A", "https://example.com/a")]
        result = recover_links(md, link_map)
        # Only the first occurrence should be wrapped
        assert result.count("[Feature A](https://example.com/a)") == 1
        # Second occurrence remains plain
        assert "Also use Feature A there." in result


# ---------------------------------------------------------------------------
# insert_image_blocks
# ---------------------------------------------------------------------------


class TestInsertImageBlocks:
    """Tests for image block insertion at correct positions."""

    @pytest.fixture
    def sample_analysis(self):
        return ImageAnalysisResult(
            filename_stem="img001",
            description="Screenshot showing the settings page.",
            ui_elements=["Save button", "Cancel button"],
            navigation_path="Settings > General",
        )

    def test_image_inserted_after_matching_text(self, sample_analysis):
        md = "Go to Settings and configure:\n\nThen proceed to the next step."
        image_map = [("Go to Settings and configure:", "img001")]
        result = insert_image_blocks(md, image_map, [sample_analysis])
        assert "> **[Image: img001](images/img001.png)**" in result
        assert "> Screenshot showing the settings page." in result
        # Image should appear after the matching text
        settings_pos = result.index("Go to Settings and configure:")
        image_pos = result.index("[Image: img001]")
        assert image_pos > settings_pos

    def test_multiple_images_same_preceding(self, sample_analysis):
        analysis2 = ImageAnalysisResult(
            filename_stem="img002",
            description="Another screenshot.",
        )
        md = "Follow these steps:\n\nDo the next thing."
        image_map = [
            ("Follow these steps:", "img001"),
            ("Follow these steps:", "img002"),
        ]
        result = insert_image_blocks(md, image_map, [sample_analysis, analysis2])
        assert "[Image: img001]" in result
        assert "[Image: img002]" in result

    def test_no_match_appends_at_end(self, sample_analysis):
        md = "Some unrelated content here."
        image_map = [("text that does not exist anywhere", "img001")]
        result = insert_image_blocks(md, image_map, [sample_analysis])
        # Should still contain the image (appended at end)
        assert "[Image: img001]" in result

    def test_empty_image_map(self):
        md = "Some markdown."
        result = insert_image_blocks(md, [], [])
        assert result == md

    def test_missing_analysis_skipped(self):
        md = "Go to Settings.\n\nNext step."
        analysis = ImageAnalysisResult(
            filename_stem="other_img",
            description="Wrong image.",
        )
        image_map = [("Go to Settings.", "img001")]
        result = insert_image_blocks(md, image_map, [analysis])
        # img001 has no matching analysis → skipped
        assert "[Image: img001]" not in result


# ---------------------------------------------------------------------------
# _format_image_block
# ---------------------------------------------------------------------------


class TestFormatImageBlock:
    def test_basic_format(self):
        analysis = ImageAnalysisResult(
            filename_stem="test_img",
            description="A test image description.",
        )
        block = _format_image_block("test_img", analysis)
        assert block == (
            "> **[Image: test_img](images/test_img.png)**\n"
            "> A test image description."
        )

    def test_empty_description(self):
        analysis = ImageAnalysisResult(filename_stem="test_img", description="")
        block = _format_image_block("test_img", analysis)
        assert block == "> **[Image: test_img](images/test_img.png)**"


# ---------------------------------------------------------------------------
# _normalize_for_match
# ---------------------------------------------------------------------------


class TestNormalizeForMatch:
    def test_collapses_whitespace(self):
        assert _normalize_for_match("  hello   world  ") == "hello world"

    def test_removes_bold_markers(self):
        assert _normalize_for_match("**bold text**") == "bold text"

    def test_lowercases(self):
        assert _normalize_for_match("Hello World") == "hello world"

    def test_non_breaking_space(self):
        assert _normalize_for_match("hello\xa0world") == "hello world"


# ---------------------------------------------------------------------------
# _insert_after_text
# ---------------------------------------------------------------------------


class TestInsertAfterText:
    def test_inserts_after_match(self):
        md = "Line one.\nLine two.\nLine three."
        result = _insert_after_text(md, "Line two.", "> IMAGE")
        lines = result.split("\n")
        two_idx = next(i for i, l in enumerate(lines) if "Line two." in l)
        img_idx = next(i for i, l in enumerate(lines) if "> IMAGE" in l)
        assert img_idx > two_idx

    def test_no_match_appends(self):
        md = "Only content here."
        result = _insert_after_text(md, "nonexistent text", "> IMAGE")
        assert result.endswith("> IMAGE")

    def test_short_search_text_skipped(self):
        md = "Some content."
        result = _insert_after_text(md, "ab", "> IMAGE")
        # Too short to match — appended at end
        assert "> IMAGE" in result
