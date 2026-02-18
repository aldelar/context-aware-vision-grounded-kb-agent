"""Vision-Grounded Knowledge Agent — Chainlit entry point."""

from __future__ import annotations

import logging
import re

import chainlit as cl
from agent_framework import AgentThread
from starlette.responses import Response

from app.agent.image_service import download_image
from app.agent.kb_agent import AgentResponse, Citation, KBAgent

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
for _name in ("azure.core", "azure.identity", "httpx", "watchfiles"):
    logging.getLogger(_name).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
# Matches any markdown image syntax — used to strip stray images the LLM may emit
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\s*\([^)]*\)")
_REF_MARKER_RE = re.compile(r"\[Ref\s+(#\d+(?:\s*,\s*#\d+)*)\]")
# Matches [Image: name](images/file.png) references produced by the convert pipeline
_CONTENT_IMAGE_RE = re.compile(
    r"\[Image:\s*([^\]]+)\]\(images/([^)]+\.(?:png|jpg|jpeg|gif|svg|webp))\)"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_ref_map(citations: list[Citation]) -> list[Citation]:
    """De-duplicate citations by (article_id, section_header) preserving order."""
    seen: set[str] = set()
    unique: list[Citation] = []
    for c in citations:
        key = f"{c.article_id}:{c.section_header}"
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def _expand_ref_markers(text: str) -> str:
    r"""Expand ``[Ref #N]`` and ``[Ref #N, #M]`` markers into bare tokens.

    Chainlit auto-links element names that appear literally in the message
    content.  The elements are named ``Ref #1``, ``Ref #2``, etc., so we
    strip the surrounding brackets and split combined refs.

    Examples
    --------
    - ``[Ref #1]``       → ``Ref #1``
    - ``[Ref #1, #5]``   → ``Ref #1, Ref #5``
    """
    def _expand(m: re.Match) -> str:
        inner = m.group(1)
        nums = re.findall(r"#(\d+)", inner)
        return ", ".join(f"Ref #{n}" for n in nums)

    return _REF_MARKER_RE.sub(_expand, text)


def _strip_md_images(text: str) -> str:
    """Remove any stray ``![alt](url)`` markdown images the LLM may emit."""
    return _MD_IMAGE_RE.sub("", text).strip()


def _rewrite_image_refs(content: str, article_id: str) -> str:
    """Rewrite ``[Image: name](images/file.png)`` refs to markdown images via proxy."""

    def _replace(m: re.Match) -> str:
        alt = m.group(1)
        img_file = m.group(2)
        return f"![{alt}](/api/images/{article_id}/images/{img_file})"

    return _CONTENT_IMAGE_RE.sub(_replace, content)


# ---------------------------------------------------------------------------
# Inline-image normalisation
#
# During streaming Chainlit renders ``![alt](/api/images/...)`` markdown
# natively — the browser GETs the image from our same-origin proxy
# endpoint and it works perfectly.
#
# Post-processing must NOT convert these to <img> / base64 because
# ``msg.update()`` causes Chainlit to re-render and it strips or breaks
# HTML <img> tags, producing grey boxes.
#
# Instead we *normalise* every ``![alt](url)`` in the LLM output so that
# the URL always resolves to our proxy endpoint ``/api/images/...``.
# The LLM is creative with URLs — observed patterns include:
#   • /api/images/ARTICLE/images/FILE         (correct)
#   • api/images/ARTICLE/images/FILE          (missing leading /)
#   • https://learn.microsoft.com/api/images/ARTICLE/images/FILE  (hallucinated domain)
#   • https://learn.microsoft.com/en-us/azure/search/media/FILE   (original MS Learn URL)
#   • attachment:/api/images/ARTICLE/images/FILE   (attachment: with full path)
#   • attachment:FILE                              (attachment: with just filename)
# The normaliser handles ALL of these by:
#   1. Stripping ``attachment:`` prefix if present.
#   2. Looking for ``api/images/...`` anywhere in the URL → rewrite to ``/api/images/...``
#   3. Falling back to filename lookup from citations.
# ---------------------------------------------------------------------------

# Match ANY markdown image: ![alt text](url)
_ANY_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\s*\(\s*([^)\s]+)\s*\)")

# Extracts the api/images/... path from any URL that contains it
_API_PATH_RE = re.compile(r"/?api/images/(.+)")


def _build_filename_lookup(citations: list[Citation]) -> dict[str, str]:
    """Build a filename → proxy-URL lookup from citations."""
    from app.agent.image_service import get_image_url

    lookup: dict[str, str] = {}
    for cit in citations:
        for path in cit.image_urls:
            filename = path.split("/")[-1]
            if filename not in lookup:
                lookup[filename] = get_image_url(cit.article_id, path)
    return lookup


def _normalise_inline_images(text: str, citations: list[Citation]) -> str:
    """Normalise every ``![alt](url)`` so the URL is a clean proxy path.

    Handles all observed LLM URL patterns (see block comment above).
    Does NOT convert to HTML ``<img>`` — Chainlit renders native markdown
    images via the proxy endpoint.
    """
    lookup = _build_filename_lookup(citations)
    count = 0

    def _normalise(m: re.Match) -> str:
        nonlocal count
        alt, raw_url = m.group(1), m.group(2)

        # 1. Strip attachment: prefix if present
        url = raw_url
        if url.lower().startswith("attachment:"):
            url = url[len("attachment:"):]

        # 2. Try to find api/images/... path anywhere in the URL
        api_match = _API_PATH_RE.search(url)
        if api_match:
            clean_url = f"/api/images/{api_match.group(1)}"
            count += 1
            if clean_url != raw_url:
                logger.info("Normalised image URL: %s → %s", raw_url, clean_url)
            return f"![{alt}]({clean_url})"

        # 3. Fall back to filename lookup from citations
        filename = url.rsplit("/", 1)[-1]
        proxy_url = lookup.get(filename)
        if proxy_url:
            count += 1
            logger.info("Resolved image by filename: %s → %s", raw_url, proxy_url)
            return f"![{alt}]({proxy_url})"

        # Can't resolve — log warning and render as italic text
        logger.warning("Could not resolve inline image: %s", raw_url)
        return f"*[Image: {alt}]*"

    text = _ANY_IMAGE_RE.sub(_normalise, text)
    logger.info("_normalise_inline_images: normalised %d image(s)", count)
    return text


def _build_citation_content(cit: Citation, idx: int) -> str:
    """Build rich Markdown content for a citation side-panel element."""
    # Rewrite image link-style refs to proper markdown images served via proxy
    content = _rewrite_image_refs(cit.content, cit.article_id)
    lines = [
        f"### Ref #{idx} — {cit.title}",
        f"**Section:** {cit.section_header}",
        "",
        content,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Image proxy endpoint
#
# Chainlit registers a catch-all ``/{full_path:path}`` that serves the SPA.
# Routes added with ``@app.get(...)`` are appended *after* this catch-all
# and therefore never match.  We work around this by defining the route on
# a dedicated APIRouter, removing the catch-all from the route list,
# including our router (so it gets higher priority), and then re-appending
# the catch-all.
# ---------------------------------------------------------------------------

from starlette.routing import Route
from fastapi import APIRouter

_image_router = APIRouter()


@_image_router.get("/api/images/{article_id}/{image_path:path}")
async def image_proxy(article_id: str, image_path: str) -> Response:
    """Proxy an image blob from Azure Storage through the local server.

    This avoids sending SAS URLs to the browser where they would be blocked
    by Content Security Policy or CORS restrictions.
    """
    blob = download_image(article_id, image_path)
    if blob is None:
        return Response(status_code=404, content="Image not found")
    return Response(
        content=blob.data,
        media_type=blob.content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


# Pop the catch-all, include our router, then re-add the catch-all.
_app = cl.server.app
_catchall = [r for r in _app.routes if isinstance(r, Route) and getattr(r, "path", "") == "/{full_path:path}"]
for r in _catchall:
    _app.routes.remove(r)
_app.include_router(_image_router)
for r in _catchall:
    _app.routes.append(r)


# ---------------------------------------------------------------------------
# Chainlit lifecycle hooks
# ---------------------------------------------------------------------------

@cl.set_starters
async def set_starters() -> list[cl.Starter]:
    """Provide suggested conversation starters on the welcome screen."""
    return [
        cl.Starter(
            label="Content Understanding",
            message="What are the key components of Azure Content Understanding?",
        ),
        cl.Starter(
            label="Agentic Retrieval",
            message="How does agentic retrieval work in Azure AI Search?",
        ),
        cl.Starter(
            label="Search Security",
            message="What are the network security options for Azure AI Search?",
        ),
    ]


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initialise per-session agent and conversation thread."""
    agent = KBAgent()
    thread = AgentThread()
    cl.user_session.set("agent", agent)
    cl.user_session.set("thread", thread)
    logger.info("New chat session started")


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle an incoming user message — stream the agent answer."""
    agent: KBAgent = cl.user_session.get("agent")  # type: ignore[assignment]
    thread: AgentThread = cl.user_session.get("thread")  # type: ignore[assignment]

    # Create the response message and stream tokens into it
    msg = cl.Message(content="")

    response: AgentResponse | None = None

    async for chunk in agent.chat_stream(message.content, thread=thread):
        if isinstance(chunk, AgentResponse):
            response = chunk
        else:
            await msg.stream_token(chunk)

    if response is None:
        await msg.send()
        return

    # ---- Post-process: expand refs, convert inline images to HTML ----
    # Debug: log raw LLM output to diagnose image markdown format
    _img_lines = [ln for ln in msg.content.splitlines() if "![" in ln or "/api/images/" in ln]
    if _img_lines:
        for ln in _img_lines:
            logger.info("LLM image line: %s", ln.strip())
    else:
        logger.info("LLM output contains no image references")

    msg.content = _expand_ref_markers(msg.content)
    msg.content = _normalise_inline_images(msg.content, response.citations)

    elements: list[cl.Element] = []

    # ---- Build citation elements (cl.Text with display="side") ----
    unique_citations = _build_ref_map(response.citations)
    for idx, cit in enumerate(unique_citations, 1):
        elements.append(
            cl.Text(
                name=f"Ref #{idx}",
                content=_build_citation_content(cit, idx),
                display="side",
            )
        )

    # ---- Attach elements and send final update ----
    msg.elements = elements
    await msg.update()
