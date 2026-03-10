"""Tests for fn_convert_cu.cu_images — CU image analysis via kb_image_analyzer.

Integration tests calling the live Azure Content Understanding endpoint.
Requires:
    - ``kb_image_analyzer`` deployed (``manage_analyzers deploy``)
    - ``gpt-4.1`` registered as CU default
    - ``az login`` with Cognitive Services User role

Image analysis results are cached per module to avoid redundant CU calls.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fn_convert_cu.cu_images import ImageAnalysisResult, analyze_image

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_STAGING = Path(__file__).resolve().parent.parent.parent.parent.parent / "kb" / "staging"
_CLEAN_DIR = _STAGING / "content-understanding-overview-html_en-us"


def _find_image_files(article_dir: Path) -> list[Path]:
    """Return all image files in an article directory."""
    images: list[Path] = []
    # .image files in root
    images.extend(sorted(article_dir.glob("*.image")))
    # .png/.jpg files in images/ subdir
    images_subdir = article_dir / "images"
    if images_subdir.exists():
        images.extend(sorted(images_subdir.glob("*.png")))
        images.extend(sorted(images_subdir.glob("*.jpg")))
    return images


# ---------------------------------------------------------------------------
# Module-scoped cache — one CU call per image
# ---------------------------------------------------------------------------

_result_cache: dict[str, ImageAnalysisResult] = {}

_CLEAN_IMAGES = _find_image_files(_CLEAN_DIR) if _CLEAN_DIR.exists() else []
_CLEAN_IMAGE = _CLEAN_IMAGES[0] if _CLEAN_IMAGES else None


def _get_cached_result(image_path: Path) -> ImageAnalysisResult:
    """Analyze once and cache."""
    key = str(image_path)
    if key not in _result_cache:
        _result_cache[key] = analyze_image(image_path)
    return _result_cache[key]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAnalyzeImage:
    """Integration tests for analyze_image()."""

    @pytest.mark.skipif(_CLEAN_IMAGE is None, reason="No clean HTML images in staging")
    def test_returns_image_analysis_result(self) -> None:
        """analyze_image returns an ImageAnalysisResult."""
        result = _get_cached_result(_CLEAN_IMAGE)  # type: ignore[arg-type]
        assert isinstance(result, ImageAnalysisResult)

    @pytest.mark.skipif(_CLEAN_IMAGE is None, reason="No clean HTML images in staging")
    def test_description_is_nonempty(self) -> None:
        """Description should be a meaningful string for a UI screenshot."""
        result = _get_cached_result(_CLEAN_IMAGE)  # type: ignore[arg-type]
        assert len(result.description) > 20, (
            f"Description too short ({len(result.description)} chars)"
        )

    @pytest.mark.skipif(_CLEAN_IMAGE is None, reason="No clean HTML images in staging")
    def test_ui_elements_is_list(self) -> None:
        """UIElements should be a list of strings."""
        result = _get_cached_result(_CLEAN_IMAGE)  # type: ignore[arg-type]
        assert isinstance(result.ui_elements, list)

    @pytest.mark.skipif(_CLEAN_IMAGE is None, reason="No clean HTML images in staging")
    def test_navigation_path_is_string(self) -> None:
        """NavigationPath should be a string."""
        result = _get_cached_result(_CLEAN_IMAGE)  # type: ignore[arg-type]
        assert isinstance(result.navigation_path, str)

    @pytest.mark.skipif(_CLEAN_IMAGE is None, reason="No clean HTML images in staging")
    def test_filename_stem_set(self) -> None:
        """filename_stem should match the image file's stem."""
        result = _get_cached_result(_CLEAN_IMAGE)  # type: ignore[arg-type]
        assert result.filename_stem == _CLEAN_IMAGE.stem  # type: ignore[union-attr]

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """analyze_image raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            analyze_image(tmp_path / "nonexistent.png")
