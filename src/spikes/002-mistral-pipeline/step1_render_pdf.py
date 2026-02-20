"""
Step 1 of the Mistral Document AI spike pipeline.

Replaces ``<img>`` tags with visible text markers (``[[IMG:<filename>]]``)
and renders the marked-up HTML to PDF via Playwright Chromium.

The markers are rendered in normal-size black text so Mistral OCR reliably
preserves them in the extracted Markdown.  The actual images are **not**
included in the PDF — we have the source files in the staging directory and
don't need OCR to detect them.
"""

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

# CSS injected before </head> to improve print fidelity.
_PRINT_CSS = """
<style>
  /* Prevent tiny orphan lines at page breaks */
  p, li, tr {
    orphans: 3;
    widows: 3;
  }
</style>
"""


def _inject_print_css(html: str) -> str:
    """Inject print-friendly CSS into the HTML ``<head>``."""
    if "</head>" in html:
        return html.replace("</head>", _PRINT_CSS + "</head>", 1)
    return _PRINT_CSS + html


def _replace_images_with_markers(html: str) -> str:
    """Replace each ``<img>`` (and its wrapping ``<a>`` if present) with a
    visible ``[[IMG:<filename>]]`` text marker.

    The marker is rendered in a ``<p>`` so it occupies a normal text line in
    the PDF and will survive OCR.
    """

    def _img_to_marker(match: re.Match) -> str:
        tag = match.group(0)
        src_match = re.search(r'src=["\']([^"\']+)["\']', tag)
        if not src_match:
            return tag
        filename = Path(src_match.group(1)).name
        return (
            f'<p style="margin:0.4em 0;font-size:14px;">'
            f'[[IMG:{filename}]]</p>'
        )

    # First, unwrap <a> tags that wrap <img> tags (lightbox links)
    html = re.sub(
        r'<a\b[^>]*>\s*(<img\b[^>]*>)\s*</a>',
        r'\1',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Then replace each <img> with a marker
    return re.sub(r'<img\b[^>]*>', _img_to_marker, html, flags=re.IGNORECASE)


def render_pdf(html_path: Path, output_pdf: Path) -> None:
    """Render *html_path* to *output_pdf* with images replaced by text markers.

    A temporary modified HTML file is written next to the source so that
    relative paths still resolve correctly during rendering.
    """
    html = html_path.read_text(encoding="utf-8")
    html = _inject_print_css(html)
    html = _replace_images_with_markers(html)

    temp_path = html_path.parent / "_print_temp.html"
    try:
        temp_path.write_text(html, encoding="utf-8")

        output_pdf.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(f"file://{temp_path.resolve()}")
            page.pdf(
                path=str(output_pdf),
                format="A4",
                print_background=True,
                margin={"top": "0.5in", "bottom": "0.5in",
                        "left": "0.4in", "right": "0.4in"},
            )
            browser.close()
    finally:
        temp_path.unlink(missing_ok=True)
