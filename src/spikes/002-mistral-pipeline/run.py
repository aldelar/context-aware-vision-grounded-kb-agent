"""Orchestrator: process all KB articles through the Mistral Document AI pipeline.

Usage:
    cd src/spikes/002-mistral-pipeline
    uv run python run.py
"""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from step1_render_pdf import render_pdf
from step2_mistral_ocr import ocr_pdf
from step3_map_images import find_image_markers
from step4_describe_images import describe_all_images
from step5_merge import extract_link_map, merge_article

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
STAGING_DIR = PROJECT_ROOT / "kb" / "staging"
OUTPUT_DIR = PROJECT_ROOT / "kb" / "serving-spike-002"


def _load_env() -> None:
    """Load .env from src/functions/.env."""
    env_file = PROJECT_ROOT / "src" / "functions" / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)
        logger.info("Loaded env from %s", env_file)
    else:
        logger.warning("No .env found at %s — relying on existing env vars", env_file)


def _find_html(article_dir: Path) -> Path:
    """Find the HTML file in an article directory.

    Tries index.html first, then the first sorted *.html file (excluding
    files with base64 or colon in their names).
    """
    index = article_dir / "index.html"
    if index.exists():
        return index

    candidates = sorted(
        f
        for f in article_dir.glob("*.html")
        if "base64" not in f.name and ":" not in f.name and not f.name.startswith("_")
    )
    if not candidates:
        raise FileNotFoundError(f"No HTML file found in {article_dir}")
    return candidates[0]


def run() -> None:
    """Process all staging articles through the Mistral pipeline."""
    _load_env()

    endpoint = os.environ.get("AI_SERVICES_ENDPOINT", "")
    if not endpoint:
        logger.error("AI_SERVICES_ENDPOINT not set. Run 'make dev-setup-env' or set it manually.")
        sys.exit(1)

    gpt_deployment = os.environ.get(
        "CU_COMPLETION_DEPLOYMENT_NAME",
        os.environ.get("AGENT_DEPLOYMENT_NAME", "gpt-4.1"),
    )
    mistral_deployment = os.environ.get("MISTRAL_DEPLOYMENT_NAME", "mistral-document-ai-2512")

    logger.info("Endpoint: %s", endpoint)
    logger.info("GPT deployment: %s", gpt_deployment)
    logger.info("Mistral deployment: %s", mistral_deployment)

    articles = sorted(d for d in STAGING_DIR.iterdir() if d.is_dir())
    if not articles:
        logger.error("No articles found in %s", STAGING_DIR)
        sys.exit(1)

    logger.info("Found %d articles to process", len(articles))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mistral-spike-") as tmp:
        tmp_dir = Path(tmp)

        for article_dir in articles:
            article_id = article_dir.name
            print(f"\n{'='*60}")
            print(f"Processing: {article_id}")
            print(f"{'='*60}")

            try:
                _process_article(
                    article_dir=article_dir,
                    article_id=article_id,
                    tmp_dir=tmp_dir,
                    endpoint=endpoint,
                    gpt_deployment=gpt_deployment,
                    mistral_deployment=mistral_deployment,
                )
            except Exception:
                logger.exception("Failed to process %s", article_id)
                continue

    print(f"\nDone. Output in: {OUTPUT_DIR}")


def _process_article(
    article_dir: Path,
    article_id: str,
    tmp_dir: Path,
    endpoint: str,
    gpt_deployment: str,
    mistral_deployment: str,
) -> None:
    """Run the 5-step pipeline for a single article."""
    article_tmp = tmp_dir / article_id
    article_tmp.mkdir(parents=True, exist_ok=True)

    # Ensure output dir exists early so we can persist artefacts
    output_article_dir = OUTPUT_DIR / article_id
    output_article_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: HTML → PDF with markers  (persist in output dir)
    html_path = _find_html(article_dir)
    pdf_path = output_article_dir / "article.pdf"
    print(f"  Step 1: Rendering PDF from {html_path.name} ...")
    render_pdf(html_path, pdf_path)
    print(f"  Step 1: PDF saved ({pdf_path.stat().st_size:,} bytes)")

    # Step 2: PDF → Mistral OCR
    print(f"  Step 2: Sending to Mistral OCR ({mistral_deployment}) ...")
    ocr_response = ocr_pdf(pdf_path, endpoint, mistral_deployment)

    # Save OCR response for debugging (alongside the PDF)
    ocr_debug_path = output_article_dir / "ocr_response.json"
    ocr_debug_path.write_text(json.dumps(ocr_response, indent=2), encoding="utf-8")
    print(f"  Step 2: OCR response saved ({ocr_debug_path.name})")

    # Extract per-page markdown
    pages = ocr_response.get("pages", [])
    if not pages:
        raise ValueError("OCR response has no pages")
    pages_markdown = [p.get("markdown", "") for p in pages]
    print(f"  Step 2: Got {len(pages)} pages")

    # Extract hyperlinks from HTML for later recovery
    link_map = extract_link_map(html_path)
    print(f"  Step 2: Extracted {len(link_map)} hyperlinks from HTML")

    # Step 3: Scan OCR markdown for [[IMG:...]] markers
    print("  Step 3: Scanning for image markers ...")
    full_markdown, source_filenames = find_image_markers(pages_markdown)
    unique_filenames = list(dict.fromkeys(source_filenames))  # preserve order, dedupe
    print(f"  Step 3: Found {len(source_filenames)} markers "
          f"({len(unique_filenames)} unique): {unique_filenames}")

    # Step 4: Describe unique images with GPT-4.1
    #   describe_all_images expects {placeholder: source_filename}
    image_mapping = {f: f for f in unique_filenames}
    print(f"  Step 4: Describing {len(image_mapping)} images with GPT-4.1 ...")
    descriptions = describe_all_images(
        image_mapping=image_mapping,
        staging_dir=article_dir,
        endpoint=endpoint,
        deployment=gpt_deployment,
    )
    print(f"  Step 4: Got {len(descriptions)} descriptions")

    # Step 5: Merge into final output
    print(f"  Step 5: Merging to {output_article_dir} ...")
    merge_article(
        ocr_markdown=full_markdown,
        source_filenames=unique_filenames,
        descriptions=descriptions,
        staging_dir=article_dir,
        output_dir=output_article_dir,
        link_map=link_map,
    )
    print(f"  Done: {article_id}")


if __name__ == "__main__":
    run()
