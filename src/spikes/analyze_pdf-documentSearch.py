"""Analyze a PDF document using prebuilt-documentSearch.

Reads PDF from kb/2_pdf/<article>/, outputs markdown + JSON to kb/3_md/<article>/.
Figure detection and description is supported for PDF input.

Usage:
    uv run python analyze_pdf-documentSearch.py --article content-understanding-html_en-us
"""

import argparse
import json
from pathlib import Path

from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.ai.contentunderstanding.models import AnalyzeResult

from config import load_config, get_credential

KB_ROOT = Path(__file__).parent.parent / "kb"
PDF_DIR = KB_ROOT / "2_pdf"
MD_DIR = KB_ROOT / "3_md" / "analyze-pdf-documentSearch"

ANALYZER_ID = "prebuilt-documentSearch"


def find_pdf_file(article_dir: Path) -> Path:
    """Find the PDF file in an article directory."""
    pdf_files = list(article_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {article_dir}")
    return pdf_files[0]


def analyze(file_path: Path) -> AnalyzeResult:
    """Analyze a PDF file using prebuilt-documentSearch."""
    config = load_config()
    credential = get_credential(config)

    client = ContentUnderstandingClient(
        endpoint=config["CONTENTUNDERSTANDING_ENDPOINT"],
        credential=credential,
    )

    print(f"Analyzer: {ANALYZER_ID}")
    print(f"Mode: Binary upload (PDF)")
    print(f"Analyzing: {file_path}")
    print(f"File size: {file_path.stat().st_size:,} bytes")
    print("-" * 60)

    poller = client.begin_analyze_binary(
        analyzer_id=ANALYZER_ID,
        binary_input=file_path.read_bytes(),
        content_type="application/pdf",
    )
    return poller.result()


def print_result(result: AnalyzeResult) -> None:
    """Print analysis result details."""
    print(f"\nAnalyzer: {result.analyzer_id}")
    print(f"Contents extracted: {len(result.contents)}")

    for i, content in enumerate(result.contents):
        print(f"\n--- Content [{i}] ---")
        print(f"  kind: {content.get('kind', 'N/A')}")
        print(f"  markdown length: {len(content.get('markdown', '')):,} chars")

        figures = content.get("figures", [])
        if figures:
            print(f"  figures: {len(figures)}")
            for j, fig in enumerate(figures):
                desc = fig.get("description", "")
                print(f"    [{j}] description={desc[:200]}...")
        else:
            print(f"  figures: none")

        fields = content.get("fields", {})
        if fields:
            print(f"  fields: {list(fields.keys())}")
            for key, val in fields.items():
                val_str = val.get("valueString", "")[:200] if isinstance(val, dict) else str(val)[:200]
                print(f"    {key}: {val_str}...")

        hyperlinks = content.get("hyperlinks", [])
        if hyperlinks:
            print(f"  hyperlinks: {len(hyperlinks)}")

    if not result.contents:
        print("\nNo contents returned — check that text-embedding-3-large is deployed.")


def save_outputs(result: AnalyzeResult, output_dir: Path, stem: str, suffix: str) -> None:
    """Save markdown and raw JSON to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    parts = [c.get("markdown", "") for c in result.contents if c.get("markdown")]
    combined = "\n\n".join(parts)
    md_path = output_dir / f"{stem}-{suffix}.md"
    md_path.write_text(combined, encoding="utf-8")
    print(f"Markdown saved to: {md_path} ({len(combined):,} chars)")

    json_path = output_dir / f"{stem}-{suffix}.result.json"
    with open(json_path, "w") as f:
        json.dump(result.as_dict(), f, indent=2, default=str)
    print(f"Raw JSON saved to: {json_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze PDF documents with prebuilt-documentSearch"
    )
    parser.add_argument(
        "--article",
        type=str,
        required=True,
        help="Article folder name under kb/2_pdf/",
    )
    args = parser.parse_args()

    article_dir = PDF_DIR / args.article
    if not article_dir.is_dir():
        print(f"Error: Article directory not found: {article_dir}")
        print("Run 'make html-to-pdf' first to convert HTML articles to PDF.")
        return

    pdf_file = find_pdf_file(article_dir)
    result = analyze(pdf_file)
    print_result(result)

    output_dir = MD_DIR / args.article
    save_outputs(result, output_dir, pdf_file.stem, "result")


if __name__ == "__main__":
    main()
