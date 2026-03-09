"""Extract image map from HTML DOM.

Parses source HTML articles to extract an ordered list of
``(preceding_text, image_filename_stem)`` pairs — used to position image
description blocks in the MarkItDown output Markdown.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

logger = logging.getLogger(__name__)


def extract_image_map(html_path: Path) -> list[tuple[str, str]]:
    """Return ordered ``(preceding_text, image_filename_stem)`` pairs.

    ``preceding_text`` is a snippet of text that appears in the document
    just before the image — used for position-matching in the Markdown.

    ``image_filename_stem`` is the filename without extension (e.g.
    ``content-understanding-framework-2025`` from
    ``content-understanding-framework-2025.png``).
    """
    soup = _parse(html_path)
    result: list[tuple[str, str]] = []

    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src:
            continue

        stem = Path(src).stem
        preceding = _find_preceding_text(img)

        if preceding:
            result.append((preceding, stem))
        else:
            # Use empty string as fallback — image will be appended at end
            logger.warning("No preceding text found for image %s in %s", stem, html_path.name)
            result.append(("", stem))

    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse(html_path: Path) -> BeautifulSoup:
    """Parse an HTML file into a BeautifulSoup tree."""
    return BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")


def _normalize(text: str) -> str:
    """Collapse all whitespace (including ``\\xa0``) and strip."""
    return re.sub(r"[\s\xa0]+", " ", text).strip()


def _is_image_only(tag: Tag) -> bool:
    """Return True if the tag contains only an image and no meaningful text."""
    text = _normalize(tag.get_text())
    return len(text) <= 5 and tag.find("img") is not None


def _find_preceding_text(img: Tag) -> str:
    """Find text that precedes *img* for position-matching in Markdown.

    Strategy 1 — **DITA step structure**: if the image is inside a
    ``div.itemgroup.info`` block within a ``li.step``, use the step
    command text (``span.ph.cmd``).

    Strategy 2 — **General**: walk up the DOM tree and, at each level,
    scan previous siblings for the nearest element with meaningful text.
    """
    # ── Strategy 1: DITA step ──────────────────────────────────────────
    step_li = img.find_parent("li", class_=lambda c: c and "step" in c)
    if step_li:
        cmd = step_li.find("span", class_=lambda c: c and "cmd" in c)
        if cmd:
            return _normalize(cmd.get_text())

    # ── Strategy 2: Walk up + back ─────────────────────────────────────
    for ancestor in img.parents:
        if ancestor.name in ("body", "html", "[document]"):
            break

        for sibling in ancestor.previous_siblings:
            if isinstance(sibling, NavigableString):
                continue
            if isinstance(sibling, Tag) and _is_image_only(sibling):
                continue
            text = _normalize(sibling.get_text())
            if len(text) > 10:
                return text[-200:]

    # ── Fallback at body level ─────────────────────────────────────────
    container = img.parent
    if container:
        for sibling in container.previous_siblings:
            if isinstance(sibling, NavigableString):
                continue
            if isinstance(sibling, Tag):
                text = _normalize(sibling.get_text())
                if len(text) > 10:
                    return text[-200:]

    return ""
