"""Step 5: Merge OCR markdown + image descriptions + recovered links into final article.md."""

import logging
import re
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hyperlink recovery
# ---------------------------------------------------------------------------

def extract_link_map(html_path: Path) -> list[tuple[str, str]]:
    """Extract ``(link_text, url)`` pairs from ``<a>`` tags in HTML.

    Skips anchors (``#``), image-wrapper links, and empty link text.
    Uses regex so we don't need a BeautifulSoup dependency in the spike.
    """
    html = html_path.read_text(encoding="utf-8")
    results: list[tuple[str, str]] = []

    # Match <a ...href="URL"...>text</a>  (non-greedy, DOTALL for multiline)
    a_pattern = re.compile(
        r'<a\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    for m in a_pattern.finditer(html):
        href = m.group(1).strip()
        inner_html = m.group(2).strip()

        # Skip anchors and javascript links
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        # Skip links that wrap images
        if "<img" in inner_html.lower():
            continue

        # Strip HTML tags from inner text
        text = re.sub(r"<[^>]+>", "", inner_html).strip()
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)

        if text and href:
            results.append((text, href))

    return results


def recover_links(markdown: str, link_map: list[tuple[str, str]]) -> str:
    """Re-inject hyperlinks into markdown using the link map.

    For each ``(link_text, url)`` pair, finds the *link_text* in *markdown*
    and wraps it as ``[link_text](url)``.  Skips texts that are already
    inside a Markdown link.  Only replaces the **first** occurrence.

    Uses word-boundary anchors at whichever end of the link text starts/ends
    with a word character, so ``"Foundry Tool"`` won't match inside
    ``"Foundry Tools"`` but ``"(RAG)"`` still matches when followed by
    a comma or period.
    """
    result = markdown
    for text, url in link_map:
        if not text or not url:
            continue

        escaped_text = re.escape(text)

        # Apply \b only where the link text starts/ends with a word char
        prefix = r"\b" if re.match(r"\w", text) else ""
        suffix = r"\b" if re.search(r"\w$", text) else ""

        # Also ensure we're not already inside a Markdown link [...](...)
        pattern = rf"(?<!\[){prefix}{escaped_text}{suffix}(?!\]\()"
        match = re.search(pattern, result)
        if match:
            replacement = f"[{text}]({url})"
            result = result[: match.start()] + replacement + result[match.end() :]
            logger.debug("Recovered link: %s → %s", text[:40], url[:60])
        else:
            logger.debug("Link text not found in markdown: %s", text[:40])

    return result


def merge_article(
    ocr_markdown: str,
    source_filenames: list[str],
    descriptions: dict[str, str],
    staging_dir: Path,
    output_dir: Path,
    link_map: list[tuple[str, str]] | None = None,
) -> None:
    """Merge OCR markdown with image descriptions and produce the final article.

    Replaces ``[[IMG:<filename>]]`` markers injected during PDF rendering with
    styled image blocks containing GPT-generated descriptions, recovers
    hyperlinks from the source HTML, copies source images to the output
    directory, and writes the final article.md.

    Args:
        ocr_markdown: Raw OCR markdown text with ``[[IMG:...]]`` markers.
        source_filenames: Unique list of source image filenames found via
            marker scanning.
        descriptions: Mapping from source filename to image description text.
        staging_dir: Directory containing the original staged images.
        output_dir: Directory where the final article and images will be written.
        link_map: Optional list of ``(text, url)`` pairs extracted from the
            source HTML for hyperlink recovery.
    """
    # 1. Create output directories
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "images").mkdir(parents=True, exist_ok=True)

    # 2. Start with ocr_markdown
    article = ocr_markdown

    # 3. Replace [[IMG:filename]] markers with description blocks
    #    and copy source images to output.
    for source_filename in source_filenames:
        stem = Path(source_filename).stem
        description = descriptions.get(source_filename, "No description available.")

        block = (
            f"> **[Image: {stem}](images/{stem}.png)**\n"
            f"> {description}"
        )

        # Replace ALL occurrences of this marker (handles same-file-twice)
        marker = f"[[IMG:{source_filename}]]"
        article = article.replace(marker, block)

        # Copy source image to output
        source_in_images = staging_dir / "images" / source_filename
        source_direct = staging_dir / source_filename
        dest = output_dir / "images" / f"{stem}.png"

        if source_in_images.exists():
            shutil.copy2(source_in_images, dest)
        elif source_direct.exists():
            shutil.copy2(source_direct, dest)
        else:
            logger.warning("Source image not found: %s", source_filename)

    # 4. Recover hyperlinks from the source HTML
    if link_map:
        article = recover_links(article, link_map)

    # 7. Write final article
    (output_dir / "article.md").write_text(article, encoding="utf-8")

    # 8. Print status
    print(f"Article written to {output_dir / 'article.md'} ({len(article)} chars)")
