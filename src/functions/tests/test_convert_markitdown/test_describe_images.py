"""Tests for fn_convert_markitdown.describe_images — GPT-4.1 vision image descriptions.

Unit tests verifying the module's structure and helpers.
Integration tests that call GPT-4.1 are not included (they require
live Azure credentials and a deployed model).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fn_convert_markitdown.describe_images import IMAGE_PROMPT, describe_all_images


class TestImagePrompt:
    """Tests for the image analysis prompt."""

    def test_prompt_mentions_description(self):
        assert "Description" in IMAGE_PROMPT

    def test_prompt_mentions_ui_elements(self):
        assert "UIElements" in IMAGE_PROMPT

    def test_prompt_mentions_navigation_path(self):
        assert "NavigationPath" in IMAGE_PROMPT


class TestDescribeAllImages:
    """Tests for describe_all_images orchestration."""

    @patch("fn_convert_markitdown.describe_images.describe_image")
    def test_finds_images_in_images_subdir(self, mock_describe, tmp_path):
        """Verify it looks for images in staging_dir/images/ first."""
        mock_describe.return_value = "A description"

        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "images").mkdir()
        (staging / "images" / "shot.png").write_bytes(b"\x89PNG")

        result = describe_all_images(
            image_stems=["shot"],
            staging_dir=staging,
            endpoint="https://test.cognitiveservices.azure.com",
            deployment="gpt-4.1",
        )

        assert "shot" in result
        mock_describe.assert_called_once()

    @patch("fn_convert_markitdown.describe_images.describe_image")
    def test_fallback_to_root_dir(self, mock_describe, tmp_path):
        """Verify it falls back to staging_dir/ if images/ subdir has no match."""
        mock_describe.return_value = "Fallback description"

        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "shot.png").write_bytes(b"\x89PNG")

        result = describe_all_images(
            image_stems=["shot"],
            staging_dir=staging,
            endpoint="https://test.cognitiveservices.azure.com",
            deployment="gpt-4.1",
        )

        assert "shot" in result

    def test_missing_image_skipped(self, tmp_path):
        """Verify missing images are skipped without raising."""
        staging = tmp_path / "staging"
        staging.mkdir()

        result = describe_all_images(
            image_stems=["missing"],
            staging_dir=staging,
            endpoint="https://test.cognitiveservices.azure.com",
            deployment="gpt-4.1",
        )

        assert len(result) == 0

    @patch("fn_convert_markitdown.describe_images.describe_image")
    def test_multiple_images(self, mock_describe, tmp_path):
        """Verify multiple image stems are all described."""
        mock_describe.side_effect = ["Desc A", "Desc B"]

        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "images").mkdir()
        (staging / "images" / "a.png").write_bytes(b"\x89PNG")
        (staging / "images" / "b.png").write_bytes(b"\x89PNG")

        result = describe_all_images(
            image_stems=["a", "b"],
            staging_dir=staging,
            endpoint="https://test.cognitiveservices.azure.com",
            deployment="gpt-4.1",
        )

        assert len(result) == 2
        assert result["a"] == "Desc A"
        assert result["b"] == "Desc B"
