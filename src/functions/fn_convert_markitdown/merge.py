"""Merge MarkItDown markdown with image descriptions into final article.md.

Replaces MarkItDown's ``[![alt](images/…)](images/…)`` image references with
styled image blocks containing GPT-generated descriptions, copies source
images to the output directory, and writes the final ``article.md``.

Unlike the CU and Mistral merge modules, no hyperlink recovery is needed
because MarkItDown preserves links natively.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Regex for MarkItDown image references: [![alt text](images/stem.ext)](images/stem.ext)
# Captures the image path (group 1) so we can extract the stem.
_MARKITDOWN_IMAGE_RE = re.compile(
    r"\[!\[[^\]]*\]\(([^)]+)\)\]\([^)]+\)"
)

# Regex to extract structured sections from GPT image descriptions.
_SECTION_RE = re.compile(
    r"(?:^|\n)\s*(?:\d+\.\s*)?(?:\*\*([^*]+)\*\*|(Description|UIElements|NavigationPath))\s*:[ \t]*",
    re.IGNORECASE,
)


def _clean_description(raw: str) -> str:
    """Extract meaningful content from a structured GPT image description.

    The GPT prompt returns text in the form::

        1. **Description**: ...
        2. **UIElements**: None.
        3. **NavigationPath**: N/A.

    This function keeps Description always and only includes UIElements /
    NavigationPath when they contain actual content.
    """
    parts = _SECTION_RE.split(raw)

    if len(parts) < 4:  # noqa: PLR2004
        return raw.strip()

    sections: dict[str, str] = {}
    for i in range(1, len(parts) - 2, 3):
        header = (parts[i] or parts[i + 1] or "").strip().lower()
        body = parts[i + 2].strip().rstrip(".")
        if header:
            sections[header] = body

    description = sections.get("description", "").strip()
    if not description:
        return raw.strip()

    lines = [description]

    ui_elements = sections.get("uielements", "").strip()
    if ui_elements and ui_elements.lower() not in ("none", "n/a", ""):
        lines.append(f"**UI Elements**: {ui_elements}")

    nav_path = sections.get("navigationpath", "").strip()
    if nav_path and nav_path.lower() not in ("none", "n/a", ""):
        lines.append(f"**Navigation Path**: {nav_path}")

    return "\n".join(lines)


def merge_article(
    markdown: str,
    image_map: list[tuple[str, str]],
    descriptions: dict[str, str],
    staging_dir: Path,
    output_dir: Path,
) -> None:
    """Merge MarkItDown markdown with image descriptions and produce the final article.

    Replaces ``[![alt](images/stem.ext)](images/stem.ext)`` patterns with
    styled image description blocks, copies source images to the output
    directory, and writes the final ``article.md``.

    Args:
        markdown: Raw MarkItDown markdown text.
        image_map: List of ``(preceding_text, stem)`` pairs from HTML DOM parsing.
        descriptions: Mapping from image stem to description text.
        staging_dir: Directory containing the original staged images.
        output_dir: Directory where the final article and images will be written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    images_out = output_dir / "images"
    images_out.mkdir(parents=True, exist_ok=True)

    # Collect all stems referenced in the markdown
    referenced_stems: set[str] = set()
    for match in _MARKITDOWN_IMAGE_RE.finditer(markdown):
        img_path = match.group(1)
        referenced_stems.add(Path(img_path).stem)

    # Also include stems from image_map
    all_stems = list(dict.fromkeys(
        [stem for _, stem in image_map] + list(referenced_stems)
    ))

    # Replace MarkItDown image references with styled blocks
    def _replace_image(match: re.Match) -> str:
        img_path = match.group(1)
        stem = Path(img_path).stem
        raw_description = descriptions.get(stem, "No description available.")
        description = _clean_description(raw_description)

        desc_lines = description.split("\n")
        quoted = "\n".join(f"> {line}" for line in desc_lines)
        return f"> **[Image: {stem}](images/{stem}.png)**\n{quoted}"

    article = _MARKITDOWN_IMAGE_RE.sub(_replace_image, markdown)

    # Copy source images to output
    for stem in all_stems:
        source_path = _find_source_image(staging_dir, stem)
        if source_path:
            dest = images_out / f"{stem}.png"
            shutil.copy2(source_path, dest)
        else:
            logger.warning("Source image not found for stem: %s", stem)

    # Write final article
    (output_dir / "article.md").write_text(article, encoding="utf-8")
    logger.info("Article written: %s (%d chars)", output_dir / "article.md", len(article))


def _find_source_image(staging_dir: Path, stem: str) -> Path | None:
    """Find a source image by stem in common locations and extensions."""
    extensions = [".png", ".jpg", ".jpeg", ".gif", ".image"]
    for search_dir in [staging_dir / "images", staging_dir]:
        for ext in extensions:
            candidate = search_dir / f"{stem}{ext}"
            if candidate.exists():
                return candidate
    return None
