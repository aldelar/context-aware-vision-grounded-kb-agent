"""fn-convert (MarkItDown) — Stage 1: HTML → Markdown + images via MarkItDown.

Orchestrates the conversion of a source KB article (HTML + images) into
clean Markdown with AI-generated image descriptions using MarkItDown for
text extraction and GPT-4.1 vision for image analysis.

Steps:
    1. Convert HTML to Markdown via MarkItDown (local, no API calls)
    2. Parse HTML DOM to extract image map (filename stems + positions)
    3. Describe each unique image via GPT-4.1 vision
    4. Merge: replace MarkItDown image refs with styled image blocks, copy images

This module shares the same input/output contract as ``fn_convert_cu``
and ``fn_convert_mistral``:
    - Input: ``article_path`` — folder containing HTML + images
    - Output: ``output_path`` — folder with ``article.md`` + ``images/``
"""

from __future__ import annotations

import logging
from pathlib import Path

from fn_convert_markitdown import describe_images, extract_images, html_to_md, merge
from shared.config import config

logger = logging.getLogger(__name__)


def run(article_path: str, output_path: str) -> None:
    """Convert a single KB article from HTML to Markdown using MarkItDown.

    Parameters
    ----------
    article_path:
        Path to the source article folder (contains HTML + image files).
    output_path:
        Path to write the processed article (``article.md`` + ``images/``).
    """
    article_dir = Path(article_path).resolve()
    output_dir = Path(output_path).resolve()

    logger.info("fn-convert (markitdown): %s → %s", article_dir.name, output_dir)

    endpoint = config.ai_services_endpoint
    gpt_deployment = "gpt-4.1"

    # ── 1. Convert HTML to Markdown via MarkItDown ────────────────────
    html_file = _find_html(article_dir)
    markdown = html_to_md.convert_html(html_file)
    logger.info("MarkItDown: %d chars extracted from %s", len(markdown), html_file.name)

    # ── 2. Extract image map from HTML DOM ────────────────────────────
    image_map = extract_images.extract_image_map(html_file)
    unique_stems = list(dict.fromkeys(stem for _, stem in image_map))
    logger.info("Found %d images (%d unique)", len(image_map), len(unique_stems))

    # ── 3. Describe images with GPT-4.1 vision ───────────────────────
    descriptions = describe_images.describe_all_images(
        image_stems=unique_stems,
        staging_dir=article_dir,
        endpoint=endpoint,
        deployment=gpt_deployment,
    )
    logger.info("Described %d images", len(descriptions))

    # ── 4. Merge: replace image refs, copy images, write article.md ──
    merge.merge_article(
        markdown=markdown,
        image_map=image_map,
        descriptions=descriptions,
        staging_dir=article_dir,
        output_dir=output_dir,
    )
    logger.info("fn-convert (markitdown) complete: %s", article_dir.name)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _find_html(article_dir: Path) -> Path:
    """Find the primary HTML file in an article directory.

    Checks ``index.html`` first, then falls back to the first ``.html`` file
    (excluding base64 variants and Windows security zone markers).
    """
    index = article_dir / "index.html"
    if index.exists():
        return index

    html_files = [
        f
        for f in article_dir.glob("*.html")
        if "base64" not in f.name and ":" not in f.name
    ]
    if html_files:
        return sorted(html_files)[0]

    raise FileNotFoundError(f"No HTML file found in {article_dir}")
