"""Step 3: Extract image markers from OCR markdown.

During PDF rendering (step 1), each ``<img>`` tag is replaced with a visible
text marker ``[[IMG:<filename>]]``.  Mistral OCR preserves these markers in
the extracted Markdown.  This module scans for them and returns an ordered
list of source filenames found in the document.
"""

import re

# Pattern that matches markers as they appear in OCR markdown.
# OCR may add whitespace, line breaks, or minor formatting around the brackets.
MARKER_RE = re.compile(r"\[\[IMG:([^\]]+?)\]\]")


def find_image_markers(pages_markdown: list[str]) -> tuple[str, list[str]]:
    """Concatenate page markdowns and extract image source filenames from markers.

    Args:
        pages_markdown: List of markdown strings, one per page.

    Returns:
        tuple[str, list[str]]: A tuple of:
            - full_markdown: All pages joined with double-newline separators.
            - source_filenames: Ordered list of source filenames found in
              ``[[IMG:...]]`` markers (may contain duplicates if the same
              image appears multiple times).
    """
    full_markdown = "\n\n".join(pages_markdown)
    source_filenames = [m.group(1).strip() for m in MARKER_RE.finditer(full_markdown)]
    return full_markdown, source_filenames
