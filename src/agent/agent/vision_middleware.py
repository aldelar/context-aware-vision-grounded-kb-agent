"""Vision middleware — injects search-result images for GPT-4.1 vision.

When the ``search_knowledge_base`` tool returns results that include image
references, this :class:`ChatMiddleware` downloads the actual image bytes and
appends them to the conversation as a user message with ``Content.from_data()``
items.

The OpenAI chat client in the agent framework automatically converts
``Content`` items with image media types into the ``image_url`` content parts
that GPT-4.1's vision endpoint expects, so the model can *see* diagrams,
architecture charts, and other visuals — not just the text descriptions.
"""

from __future__ import annotations

import json
import logging
from urllib.parse import unquote

from agent_framework import ChatContext, ChatMiddleware, Content, Message

from agent.image_service import download_image

logger = logging.getLogger(__name__)

# Maximum number of images to send to the LLM per request to control token
# costs.  Each image consumes ~85-765+ vision tokens depending on detail.
MAX_VISION_IMAGES = 6


def _extract_result_items(payload: object) -> list[dict]:
    """Return search result items from legacy list or current dict payloads."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        results = payload.get("results")
        if isinstance(results, list):
            return [item for item in results if isinstance(item, dict)]

    return []


class VisionImageMiddleware(ChatMiddleware):
    """Inject images from search results so GPT-4.1 can reason about them.

    This middleware intercepts the chat messages *after* the search tool has
    returned results and *before* the LLM generates its final answer.  It:

    1. Scans messages for ``Content`` items where ``.type == "function_result"``.
    2. Downloads the referenced images from blob storage.
    3. Appends a user message with the images as ``Content.from_data()`` items
       (base64 data URIs) so the model receives them as vision inputs.

    Images are deduplicated by their blob path and capped at
    ``MAX_VISION_IMAGES`` to keep token usage reasonable.
    """

    async def process(self, context: ChatContext, next) -> None:  # noqa: A002
        """Intercept and inject images before the LLM call."""
        image_items: list[Content] = []
        seen_paths: set[str] = set()

        for msg in context.messages:
            for content in msg.contents:
                if content.type != "function_result":
                    continue
                if content.result is None:
                    continue

                # Parse the JSON tool result to find image references
                try:
                    parsed = json.loads(str(content.result))
                except (json.JSONDecodeError, TypeError):
                    continue

                results = _extract_result_items(parsed)
                if not results:
                    continue

                for result in results:
                    if len(image_items) >= MAX_VISION_IMAGES:
                        logger.info(
                            "Vision image cap reached (%d), skipping remaining images",
                            MAX_VISION_IMAGES,
                        )
                        break

                    for img_info in result.get("images", []):
                        url = img_info.get("url", "")
                        if "/api/images/" not in url:
                            continue

                        # Extract article_id and image_path from proxy URL
                        # Format: /api/images/{article_id}/{image_path}
                        try:
                            tail = url.split("/api/images/", 1)[1]
                            article_id, image_path = tail.split("/", 1)
                            article_id = unquote(article_id)
                            image_path = unquote(image_path)
                        except (IndexError, ValueError):
                            continue

                        # Deduplicate by blob path
                        blob_key = f"{article_id}/{image_path}"
                        if blob_key in seen_paths:
                            continue
                        seen_paths.add(blob_key)

                        # Respect the cap
                        if len(image_items) >= MAX_VISION_IMAGES:
                            break

                        blob = download_image(article_id, image_path)
                        if blob is None:
                            logger.warning(
                                "Vision: could not download %s/%s",
                                article_id,
                                image_path,
                            )
                            continue

                        image_items.append(
                            Content.from_data(data=blob.data, media_type=blob.content_type)
                        )
                        logger.info(
                            "Vision: attached %s (%d bytes, %s)",
                            blob_key,
                            len(blob.data),
                            blob.content_type,
                        )

        if image_items:
            # Append a user message with the images so the LLM can see them
            vision_msg = Message(
                role="user",
                contents=[
                    Content.from_text(
                        "[System] The images referenced in the search results "
                        "are attached below. Use them to provide more accurate "
                        "and visually-informed answers when relevant."
                    ),
                    *image_items,
                ],
            )
            context.messages.append(vision_msg)
            logger.info(
                "Vision middleware: injected %d image(s) into conversation",
                len(image_items),
            )

        await next()
