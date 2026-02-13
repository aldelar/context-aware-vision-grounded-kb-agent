"""Convert an HTML KB article to PDF using Playwright (headless Chromium).

Handles articles with images referenced via absolute or relative paths by
intercepting resource requests and serving files from the article directory.

Usage:
    uv run python convert_html_to_pdf.py --article content-understanding-html_en-us
    uv run python convert_html_to_pdf.py --article ymr1770823224196_en-us
"""

import argparse
import mimetypes
from pathlib import Path

from playwright.sync_api import sync_playwright, Route

KB_ROOT = Path(__file__).parent.parent / "kb"
HTML_DIR = KB_ROOT / "1_html"
PDF_DIR = KB_ROOT / "2_pdf"


def find_html_file(article_dir: Path) -> Path:
    """Find the main HTML file in an article directory."""
    html_files = list(article_dir.glob("*.html")) + list(article_dir.glob("*.htm"))
    if not html_files:
        raise FileNotFoundError(f"No HTML files found in {article_dir}")
    # Prefer index.html if present
    for f in html_files:
        if f.name == "index.html":
            return f
    return html_files[0]


def guess_mime(file_path: Path) -> str:
    """Guess MIME type from extension or file magic bytes."""
    mime, _ = mimetypes.guess_type(file_path.name)
    if mime:
        return mime
    # Fall back to magic bytes for non-standard extensions (.image, etc.)
    try:
        header = file_path.read_bytes()[:8]
        if header[:4] == b"\x89PNG":
            return "image/png"
        if header[:2] == b"\xff\xd8":
            return "image/jpeg"
        if header[:4] == b"GIF8":
            return "image/gif"
        if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
            return "image/webp"
    except Exception:
        pass
    return "application/octet-stream"


def create_route_handler(article_dir: Path):
    """Create a Playwright route handler that serves local files for resource requests.

    - Existing local files (e.g. relative image paths) load normally via fallback.
    - Absolute server paths (e.g. /sites/KMSearch/...) are resolved by filename
      against the article directory.
    - Missing resources (CSS, JS from external paths) are aborted silently.
    """

    def handle(route: Route) -> None:
        url = route.request.url

        # Let existing local files (file:// URLs that exist) load normally
        if url.startswith("file://"):
            # Strip file:// prefix to get local path
            local_path = url[7:]  # file:///path -> /path
            if Path(local_path).exists():
                route.fallback()
                return

        # Try to find the resource by filename in the article directory
        filename = url.split("/")[-1].split("?")[0]
        local_file = article_dir / filename
        if local_file.is_file():
            route.fulfill(path=str(local_file), content_type=guess_mime(local_file))
        else:
            # Missing resource (CSS, JS, etc.) — abort silently
            route.abort()

    return handle


def convert_html_to_pdf(article_id: str) -> Path:
    """Convert an HTML article to PDF using Playwright."""
    article_dir = HTML_DIR / article_id
    if not article_dir.is_dir():
        raise FileNotFoundError(f"Article directory not found: {article_dir}")

    html_file = find_html_file(article_dir)
    output_dir = PDF_DIR / article_id
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / html_file.with_suffix(".pdf").name

    print(f"Article: {article_id}")
    print(f"HTML: {html_file}")
    print(f"Output: {pdf_path}")
    print("-" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Intercept resource requests to serve local images
        page.route("**/*", create_route_handler(article_dir))

        # Navigate and wait for resources to settle
        page.goto(f"file://{html_file.resolve()}", wait_until="networkidle")

        # Generate PDF
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"},
        )
        browser.close()

    size = pdf_path.stat().st_size
    print(f"PDF created: {pdf_path} ({size:,} bytes)")
    return pdf_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert HTML KB articles to PDF using Playwright"
    )
    parser.add_argument(
        "--article",
        type=str,
        required=True,
        help="Article folder name under kb/1_html/",
    )
    args = parser.parse_args()

    convert_html_to_pdf(args.article)


if __name__ == "__main__":
    main()
