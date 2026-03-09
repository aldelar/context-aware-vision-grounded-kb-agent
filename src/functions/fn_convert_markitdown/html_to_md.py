"""HTML → Markdown conversion via MarkItDown.

Uses the ``markitdown`` library to convert an HTML file directly to clean
Markdown. No cloud API calls required — runs entirely locally.
"""

from __future__ import annotations

import logging
from pathlib import Path

from markitdown import MarkItDown

logger = logging.getLogger(__name__)


def convert_html(html_path: Path) -> str:
    """Convert an HTML file to Markdown using MarkItDown.

    Parameters
    ----------
    html_path:
        Path to the HTML file to convert.

    Returns
    -------
    str
        The extracted Markdown text.
    """
    md = MarkItDown()
    result = md.convert(str(html_path))
    markdown = result.text_content

    logger.debug("MarkItDown converted %s: %d chars", html_path.name, len(markdown))
    return markdown
