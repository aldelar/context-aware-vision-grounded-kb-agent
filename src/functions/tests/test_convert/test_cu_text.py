"""Tests for fn_convert.cu_text — CU text extraction via prebuilt-documentSearch.

These are integration tests that call the live Azure Content Understanding
endpoint.  They require:
    - A valid .env with AI_SERVICES_ENDPOINT
    - text-embedding-3-large and gpt-4.1-mini deployed and registered as CU defaults
    - ``az login`` with Cognitive Services User role on the AI Services resource

CU results are cached per article (module scope) so each article is sent to CU
only once (~30 s each) rather than once per test method.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fn_convert.cu_text import CuTextResult, extract_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_html_file(article_dir: Path) -> Path:
    """Return the first .html file in *article_dir* (skips metadata JSON)."""
    html_files = [
        f
        for f in article_dir.iterdir()
        if f.suffix == ".html" and ".metadata" not in f.name and "base64" not in f.name
    ]
    assert html_files, f"No HTML file found in {article_dir}"
    return html_files[0]


# ---------------------------------------------------------------------------
# Module-scoped result cache — one CU call per article, shared across tests
# ---------------------------------------------------------------------------

_ARTICLE_IDS = [
    "content-understanding-html_en-us",
    "ymr1770823224196_en-us",
]

# Repo root → kb/staging (computed once, no fixture dependency)
_STAGING = Path(__file__).resolve().parent.parent.parent.parent.parent / "kb" / "staging"

# Populated once by the module-scoped fixture; maps article_id → CuTextResult
_result_cache: dict[str, CuTextResult] = {}


@pytest.fixture(scope="module", params=_ARTICLE_IDS)
def cu_text_result(request: pytest.FixtureRequest) -> CuTextResult:
    """Call extract_text once per article and cache the result for the module.

    Subsequent test methods that use this fixture get the cached result
    without making another CU API call.
    """
    article_id: str = request.param
    if article_id in _result_cache:
        return _result_cache[article_id]

    article_dir = _STAGING / article_id
    if not article_dir.exists():
        pytest.skip(f"Article {article_id} not in staging")

    html_path = _find_html_file(article_dir)
    result = extract_text(html_path)
    _result_cache[article_id] = result
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExtractText:
    """Integration tests for extract_text()."""

    def test_returns_cu_text_result(self, cu_text_result: CuTextResult) -> None:
        """extract_text returns a CuTextResult with markdown and summary."""
        assert isinstance(cu_text_result, CuTextResult)

    def test_markdown_is_nonempty(self, cu_text_result: CuTextResult) -> None:
        """CU should produce non-trivial Markdown from both sample articles."""
        assert len(cu_text_result.markdown) > 500, (
            f"Markdown too short ({len(cu_text_result.markdown)} chars)"
        )

    def test_markdown_has_heading(self, cu_text_result: CuTextResult) -> None:
        """CU Markdown should contain at least one Markdown heading."""
        md = cu_text_result.markdown
        assert md.startswith("#") or "\n#" in md, (
            "Expected at least one Markdown heading in CU output"
        )

    def test_summary_is_nonempty(self, cu_text_result: CuTextResult) -> None:
        """prebuilt-documentSearch should produce a summary."""
        assert len(cu_text_result.summary) > 20, (
            f"Summary too short ({len(cu_text_result.summary)} chars)"
        )

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """extract_text raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            extract_text(tmp_path / "nonexistent.html")
