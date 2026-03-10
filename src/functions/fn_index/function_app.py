"""Per-function Azure Functions entry point for fn-index.

Standalone FunctionApp that can be deployed as its own container.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path

import azure.functions as func

from shared.blob_storage import download_article, get_article_ids
from shared.config import config

import fn_index

logger = logging.getLogger(__name__)

app = func.FunctionApp()


@app.function_name("fn_index")
@app.route(route="index", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def http_index(req: func.HttpRequest) -> func.HttpResponse:
    """Index articles from serving blob into Azure AI Search.

    POST /api/index
    Optional body: {"article_id": "specific-article-id"}
    If no article_id, processes ALL articles in the serving container.
    """
    logging.basicConfig(level=logging.INFO)

    article_ids = get_article_ids(req, config.serving_blob_endpoint, "serving")
    if not article_ids:
        return func.HttpResponse(
            json.dumps({"error": "No articles found in serving container"}),
            status_code=404,
            mimetype="application/json",
        )

    results = []
    for article_id in article_ids:
        try:
            tmp_root = Path(tempfile.mkdtemp(prefix="kb-index-"))
            serving_dir = tmp_root / article_id
            download_article(
                config.serving_blob_endpoint, "serving", article_id, serving_dir
            )

            fn_index.run(str(serving_dir))

            results.append({"article_id": article_id, "status": "ok"})

            shutil.rmtree(tmp_root, ignore_errors=True)

        except Exception as e:
            logger.exception("fn-index failed for %s", article_id)
            results.append({"article_id": article_id, "status": "error", "error": str(e)})

    return func.HttpResponse(
        json.dumps({"results": results}, indent=2),
        mimetype="application/json",
    )
