"""Display a summary of the AI Search index contents."""

import logging
from collections import Counter

logging.disable(logging.CRITICAL)

from azure.identity import DefaultAzureCredential  # noqa: E402
from azure.search.documents import SearchClient  # noqa: E402

from shared.config import config  # noqa: E402

client = SearchClient(
    endpoint=config.search_endpoint,
    index_name=config.search_index_name,
    credential=DefaultAzureCredential(),
)

docs = list(
    client.search(
        search_text="*",
        select=["id", "article_id", "title", "section_header", "image_urls"],
        top=100,
    )
)

print()
print(f"Index: {config.search_index_name}  ({len(docs)} documents)")
print("─" * 130)

for d in sorted(docs, key=lambda x: x["id"]):
    imgs = d.get("image_urls") or []
    hdr = d.get("section_header", "") or ""
    img_names = ", ".join(imgs) if imgs else ""
    print(f"  {d['id']:50s} | {hdr:60s} | images: {len(imgs)}  {img_names}")

print("─" * 130)

articles = Counter(d["article_id"] for d in docs)
print("Per-article chunk counts:")
for aid, cnt in sorted(articles.items()):
    print(f"  {aid}: {cnt} chunks")
print()
