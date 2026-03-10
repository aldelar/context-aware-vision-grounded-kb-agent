"""CU text extraction — send HTML to prebuilt-documentSearch, return Markdown.

Sends a local HTML file to the Azure Content Understanding
``prebuilt-documentSearch`` analyzer and returns the extracted Markdown and
an AI-generated summary.

Prerequisites:
    - ``text-embedding-3-large`` and ``gpt-4.1-mini`` must be deployed and
      registered as CU defaults (``manage_analyzers setup``).  Without them
      the API silently returns 0 contents.

Usage:
    from fn_convert.cu_text import extract_text
    markdown, summary = extract_text(Path("kb/staging/article/index.html"))
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from fn_convert_cu.cu_client import get_cu_client

logger = logging.getLogger(__name__)

ANALYZER_ID = "prebuilt-documentSearch"
CONTENT_TYPE = "text/html"


@dataclass
class CuTextResult:
    """Result of CU text extraction from an HTML document."""

    markdown: str
    summary: str


def extract_text(html_path: Path) -> CuTextResult:
    """Send *html_path* to CU ``prebuilt-documentSearch`` and return Markdown.

    Parameters
    ----------
    html_path:
        Absolute or relative path to a local HTML file.

    Returns
    -------
    CuTextResult
        ``markdown`` — the full Markdown text extracted from the HTML.
        ``summary`` — an AI-generated summary of the document.

    Raises
    ------
    FileNotFoundError
        If *html_path* does not exist.
    RuntimeError
        If CU returns 0 contents (usually means ``text-embedding-3-large``
        is not deployed or not registered in CU defaults).
    """
    html_path = Path(html_path)
    if not html_path.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    logger.info("Sending %s to CU %s", html_path.name, ANALYZER_ID)

    client = get_cu_client()
    poller = client.begin_analyze_binary(
        analyzer_id=ANALYZER_ID,
        binary_input=html_path.read_bytes(),
        content_type=CONTENT_TYPE,
    )
    result = poller.result()

    # Extract Markdown from all content blocks
    contents = result.contents or []
    if not contents:
        raise RuntimeError(
            f"CU returned 0 contents for {html_path.name}. "
            "Ensure text-embedding-3-large and gpt-4.1-mini are deployed "
            "and registered via 'manage_analyzers setup'."
        )

    parts: list[str] = []
    summary = ""
    for content in contents:
        md = content.get("markdown", "")
        if md:
            parts.append(md)

        # Extract Summary field (populated by documentSearch)
        fields = content.get("fields", {})
        summary_field = fields.get("Summary")
        if summary_field:
            summary = summary_field.get("valueString", "")

    markdown = "\n\n".join(parts)

    logger.info(
        "CU extracted %d chars of Markdown, summary %d chars from %s",
        len(markdown),
        len(summary),
        html_path.name,
    )

    return CuTextResult(markdown=markdown, summary=summary)
