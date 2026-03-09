"""Azure Functions v2 entry point.

Registers fn-convert (CU), fn-convert-mistral, fn-convert-markitdown, and fn-index
as HTTP-triggered functions.
All convert functions read/write via Azure Blob Storage (staging + serving containers).
For local development, use the shell scripts in scripts/functions/ instead.
"""

import json
import logging
import shutil
import tempfile
from pathlib import Path

import azure.functions as func

from shared.blob_storage import download_article, list_articles, upload_article
from shared.config import config

import fn_convert_cu
import fn_convert_markitdown
import fn_convert_mistral
import fn_index

logger = logging.getLogger(__name__)

app = func.FunctionApp()


@app.function_name("fn_convert")
@app.route(route="convert", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def http_convert(req: func.HttpRequest) -> func.HttpResponse:
    """Convert articles from staging blob to serving blob.

    POST /api/convert
    Optional body: {"article_id": "specific-article-id"}
    If no article_id, processes ALL articles in the staging container.
    """
    logging.basicConfig(level=logging.INFO)

    # Determine which articles to process
    article_ids = _get_article_ids(req, config.staging_blob_endpoint, "staging")
    if not article_ids:
        return func.HttpResponse(
            json.dumps({"error": "No articles found in staging container"}),
            status_code=404,
            mimetype="application/json",
        )

    results = []
    for article_id in article_ids:
        try:
            # Download from staging blob → temp/<article_id>/
            tmp_root = Path(tempfile.mkdtemp(prefix="kb-convert-"))
            staging_dir = tmp_root / article_id
            download_article(
                config.staging_blob_endpoint, "staging", article_id, staging_dir
            )
            # Create output dir preserving article_id as dir name
            out_root = Path(tempfile.mkdtemp(prefix="kb-out-"))
            serving_dir = out_root / article_id
            serving_dir.mkdir()

            # Run the CU convert logic
            fn_convert_cu.run(str(staging_dir), str(serving_dir))

            # Upload results to serving blob
            count = upload_article(
                config.serving_blob_endpoint, "serving", article_id, serving_dir
            )

            results.append({"article_id": article_id, "status": "ok", "blobs_uploaded": count})

            # Cleanup temp dirs
            shutil.rmtree(tmp_root, ignore_errors=True)
            shutil.rmtree(out_root, ignore_errors=True)

        except Exception as e:
            logger.exception("fn-convert failed for %s", article_id)
            results.append({"article_id": article_id, "status": "error", "error": str(e)})

    return func.HttpResponse(
        json.dumps({"results": results}, indent=2),
        mimetype="application/json",
    )


@app.function_name("fn_convert_mistral")
@app.route(route="convert-mistral", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def http_convert_mistral(req: func.HttpRequest) -> func.HttpResponse:
    """Convert articles using Mistral Document AI (staging blob → serving blob).

    POST /api/convert-mistral
    Optional body: {"article_id": "specific-article-id"}
    If no article_id, processes ALL articles in the staging container.
    """
    logging.basicConfig(level=logging.INFO)

    article_ids = _get_article_ids(req, config.staging_blob_endpoint, "staging")
    if not article_ids:
        return func.HttpResponse(
            json.dumps({"error": "No articles found in staging container"}),
            status_code=404,
            mimetype="application/json",
        )

    results = []
    for article_id in article_ids:
        try:
            tmp_root = Path(tempfile.mkdtemp(prefix="kb-convert-mistral-"))
            staging_dir = tmp_root / article_id
            download_article(
                config.staging_blob_endpoint, "staging", article_id, staging_dir
            )
            out_root = Path(tempfile.mkdtemp(prefix="kb-out-"))
            serving_dir = out_root / article_id
            serving_dir.mkdir()

            # Run the Mistral convert logic
            fn_convert_mistral.run(str(staging_dir), str(serving_dir))

            count = upload_article(
                config.serving_blob_endpoint, "serving", article_id, serving_dir
            )

            results.append({"article_id": article_id, "status": "ok", "blobs_uploaded": count})

            shutil.rmtree(tmp_root, ignore_errors=True)
            shutil.rmtree(out_root, ignore_errors=True)

        except Exception as e:
            logger.exception("fn-convert-mistral failed for %s", article_id)
            results.append({"article_id": article_id, "status": "error", "error": str(e)})

    return func.HttpResponse(
        json.dumps({"results": results}, indent=2),
        mimetype="application/json",
    )


@app.function_name("fn_convert_markitdown")
@app.route(route="convert-markitdown", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def http_convert_markitdown(req: func.HttpRequest) -> func.HttpResponse:
    """Convert articles using MarkItDown (staging blob -> serving blob).

    POST /api/convert-markitdown
    Optional body: {"article_id": "specific-article-id"}
    If no article_id, processes ALL articles in the staging container.
    """
    logging.basicConfig(level=logging.INFO)

    article_ids = _get_article_ids(req, config.staging_blob_endpoint, "staging")
    if not article_ids:
        return func.HttpResponse(
            json.dumps({"error": "No articles found in staging container"}),
            status_code=404,
            mimetype="application/json",
        )

    results = []
    for article_id in article_ids:
        try:
            tmp_root = Path(tempfile.mkdtemp(prefix="kb-convert-markitdown-"))
            staging_dir = tmp_root / article_id
            download_article(
                config.staging_blob_endpoint, "staging", article_id, staging_dir
            )
            out_root = Path(tempfile.mkdtemp(prefix="kb-out-"))
            serving_dir = out_root / article_id
            serving_dir.mkdir()

            fn_convert_markitdown.run(str(staging_dir), str(serving_dir))

            count = upload_article(
                config.serving_blob_endpoint, "serving", article_id, serving_dir
            )

            results.append({"article_id": article_id, "status": "ok", "blobs_uploaded": count})

            shutil.rmtree(tmp_root, ignore_errors=True)
            shutil.rmtree(out_root, ignore_errors=True)

        except Exception as e:
            logger.exception("fn-convert-markitdown failed for %s", article_id)
            results.append({"article_id": article_id, "status": "error", "error": str(e)})

    return func.HttpResponse(
        json.dumps({"results": results}, indent=2),
        mimetype="application/json",
    )


@app.function_name("fn_index")
@app.route(route="index", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def http_index(req: func.HttpRequest) -> func.HttpResponse:
    """Index articles from serving blob into Azure AI Search.

    POST /api/index
    Optional body: {"article_id": "specific-article-id"}
    If no article_id, processes ALL articles in the serving container.
    """
    logging.basicConfig(level=logging.INFO)

    # Determine which articles to process
    article_ids = _get_article_ids(req, config.serving_blob_endpoint, "serving")
    if not article_ids:
        return func.HttpResponse(
            json.dumps({"error": "No articles found in serving container"}),
            status_code=404,
            mimetype="application/json",
        )

    results = []
    for article_id in article_ids:
        try:
            # Download from serving blob → temp/<article_id>/
            tmp_root = Path(tempfile.mkdtemp(prefix="kb-index-"))
            serving_dir = tmp_root / article_id
            download_article(
                config.serving_blob_endpoint, "serving", article_id, serving_dir
            )

            # Run the existing index logic
            fn_index.run(str(serving_dir))

            results.append({"article_id": article_id, "status": "ok"})

            # Cleanup
            shutil.rmtree(tmp_root, ignore_errors=True)

        except Exception as e:
            logger.exception("fn-index failed for %s", article_id)
            results.append({"article_id": article_id, "status": "error", "error": str(e)})

    return func.HttpResponse(
        json.dumps({"results": results}, indent=2),
        mimetype="application/json",
    )


def _get_article_ids(
    req: func.HttpRequest,
    blob_endpoint: str,
    container_name: str,
) -> list[str]:
    """Extract article IDs from request body, or list all from blob container."""
    try:
        body = req.get_json()
        article_id = body.get("article_id")
        if article_id:
            return [article_id]
    except (ValueError, AttributeError):
        pass

    # No specific article — list all from blob
    return list_articles(blob_endpoint, container_name)

