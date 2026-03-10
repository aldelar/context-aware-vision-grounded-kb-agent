"""Per-function Azure Functions entry point for fn-convert-mistral.

Standalone FunctionApp that can be deployed as its own container.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path

import azure.functions as func

from shared.blob_storage import download_article, get_article_ids, upload_article
from shared.config import config

import fn_convert_mistral

logger = logging.getLogger(__name__)

app = func.FunctionApp()


@app.function_name("fn_convert_mistral")
@app.route(route="convert-mistral", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def http_convert_mistral(req: func.HttpRequest) -> func.HttpResponse:
    """Convert articles using Mistral Document AI (staging blob → serving blob).

    POST /api/convert-mistral
    Optional body: {"article_id": "specific-article-id"}
    If no article_id, processes ALL articles in the staging container.
    """
    logging.basicConfig(level=logging.INFO)

    article_ids = get_article_ids(req, config.staging_blob_endpoint, "staging")
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
