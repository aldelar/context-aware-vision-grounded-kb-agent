#!/usr/bin/env python3
"""Spike 003: Validate MarkItDown output quality against CU and Mistral.

Converts all articles in kb/staging/ to Markdown using MarkItDown and writes
output to kb/serving-spike-003/. Then compares against kb_snapshot/ reference
outputs from CU and Mistral pipelines.

Usage:
    cd src/functions && uv run python ../spikes/003-markitdown/run.py
"""

from __future__ import annotations

import re
from pathlib import Path

from markitdown import MarkItDown

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
STAGING_DIR = REPO_ROOT / "kb" / "staging"
OUTPUT_DIR = REPO_ROOT / "kb" / "serving-spike-003"
SNAPSHOT_CU = REPO_ROOT / "kb_snapshot" / "serving_content-understanding"
SNAPSHOT_MISTRAL = REPO_ROOT / "kb_snapshot" / "serving_mistral-doc-ai"


def find_html(article_dir: Path) -> Path:
    """Find the primary HTML file in an article directory."""
    index = article_dir / "index.html"
    if index.exists():
        return index
    html_files = [
        f for f in article_dir.glob("*.html")
        if "base64" not in f.name and ":" not in f.name
    ]
    if html_files:
        return sorted(html_files)[0]
    raise FileNotFoundError(f"No HTML file found in {article_dir}")


def extract_images_from_html(html_path: Path) -> list[str]:
    """Extract image filename stems from <img> tags in the HTML."""
    html = html_path.read_text(encoding="utf-8")
    img_pattern = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']', re.IGNORECASE)
    stems = []
    for m in img_pattern.finditer(html):
        src = m.group(1)
        stem = Path(src).stem
        stems.append(stem)
    return stems


def count_headings(md: str) -> int:
    """Count Markdown headings (lines starting with #)."""
    return len(re.findall(r"^#{1,6}\s+", md, re.MULTILINE))


def count_links(md: str) -> int:
    """Count Markdown links [text](url)."""
    return len(re.findall(r"\[([^\]]+)\]\(([^)]+)\)", md))


def count_tables(md: str) -> int:
    """Count lines that start with | (table rows)."""
    return len(re.findall(r"^\|.+\|$", md, re.MULTILINE))


def convert_article(article_dir: Path) -> tuple[str, list[str]]:
    """Convert a single article using MarkItDown.

    Returns (markdown_text, image_stems).
    """
    html_file = find_html(article_dir)
    md = MarkItDown()
    result = md.convert(str(html_file))
    markdown = result.text_content

    image_stems = extract_images_from_html(html_file)
    return markdown, image_stems


def load_snapshot(snapshot_dir: Path, article_id: str) -> str | None:
    """Load article.md from a snapshot directory."""
    path = snapshot_dir / article_id / "article.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Spike 003: MarkItDown Quality Validation")
    print("=" * 70)

    results = []

    for article_dir in sorted(STAGING_DIR.iterdir()):
        if not article_dir.is_dir():
            continue
        article_id = article_dir.name

        print(f"\n--- {article_id} ---")

        # Convert
        markdown, image_stems = convert_article(article_dir)

        # Write output
        out_dir = OUTPUT_DIR / article_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "article.md").write_text(markdown, encoding="utf-8")
        print(f"  Output: {out_dir / 'article.md'} ({len(markdown)} chars)")

        # Load reference snapshots
        cu_md = load_snapshot(SNAPSHOT_CU, article_id)
        mistral_md = load_snapshot(SNAPSHOT_MISTRAL, article_id)

        row = {
            "article": article_id,
            "markitdown_chars": len(markdown),
            "markitdown_headings": count_headings(markdown),
            "markitdown_links": count_links(markdown),
            "markitdown_table_rows": count_tables(markdown),
            "markitdown_images": len(image_stems),
            "cu_chars": len(cu_md) if cu_md else 0,
            "cu_headings": count_headings(cu_md) if cu_md else 0,
            "cu_links": count_links(cu_md) if cu_md else 0,
            "cu_table_rows": count_tables(cu_md) if cu_md else 0,
            "mistral_chars": len(mistral_md) if mistral_md else 0,
            "mistral_headings": count_headings(mistral_md) if mistral_md else 0,
            "mistral_links": count_links(mistral_md) if mistral_md else 0,
            "mistral_table_rows": count_tables(mistral_md) if mistral_md else 0,
        }
        results.append(row)

        print(f"  Images found in HTML: {len(image_stems)} ({', '.join(image_stems)})")
        print(f"  Headings: markitdown={row['markitdown_headings']}, "
              f"cu={row['cu_headings']}, mistral={row['mistral_headings']}")
        print(f"  Links: markitdown={row['markitdown_links']}, "
              f"cu={row['cu_links']}, mistral={row['mistral_links']}")
        print(f"  Table rows: markitdown={row['markitdown_table_rows']}, "
              f"cu={row['cu_table_rows']}, mistral={row['mistral_table_rows']}")
        print(f"  Chars: markitdown={row['markitdown_chars']}, "
              f"cu={row['cu_chars']}, mistral={row['mistral_chars']}")

    # Print summary table
    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)
    header = f"{'Metric':<25} {'Article':<50} {'MarkItDown':>10} {'CU':>10} {'Mistral':>10}"
    print(header)
    print("-" * len(header))
    for row in results:
        short = row["article"][:48]
        for metric in ["chars", "headings", "links", "table_rows"]:
            print(f"{metric:<25} {short:<50} {row[f'markitdown_{metric}']:>10} "
                  f"{row[f'cu_{metric}']:>10} {row[f'mistral_{metric}']:>10}")
        print()


if __name__ == "__main__":
    main()
