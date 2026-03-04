"""Context Aware & Vision Grounded KB Agent — Chainlit entry point.

The web app is a thin Chainlit client that calls the standalone KB agent
via the OpenAI-compatible Responses API.  The agent runs as a separate
service (local ``make agent`` or deployed on Foundry).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import TYPE_CHECKING

import chainlit as cl
from openai import OpenAI
from starlette.responses import Response

from app.config import config
from app.image_service import download_image, get_image_url
from app.models import Citation

if TYPE_CHECKING:
    from chainlit.types import ThreadDict

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
for _name in ("azure.core", "azure.cosmos", "azure.identity", "httpx", "watchfiles", "openai"):
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

def _build_ref_map(citations: list[Citation]) -> tuple[list[Citation], dict[int, int]]:
    """De-duplicate citations by (article_id, section_header) preserving order.

    Returns
    -------
    tuple[list[Citation], dict[int, int]]
        The de-duplicated list and a mapping from old 1-based ref number
        to new 1-based ref number so the LLM output text can be rewritten.
    """
    seen: dict[str, int] = {}       # key → 1-based dedup index
    unique: list[Citation] = []
    old_to_new: dict[int, int] = {}  # old 1-based → new 1-based
    for old_idx, c in enumerate(citations, 1):
        key = f"{c.article_id}:{c.section_header}"
        if key not in seen:
            unique.append(c)
            seen[key] = len(unique)  # new 1-based index
        old_to_new[old_idx] = seen[key]
    return unique, old_to_new


def _remap_ref_numbers(text: str, old_to_new: dict[int, int]) -> str:
    r"""Rewrite ``Ref #N`` numbers so they match the de-duplicated citations.

    Handles both bracketed ``[Ref #4]`` and bare ``Ref #4`` occurrences.
    """
    if not old_to_new:
        return text

    # Match bare or bracketed forms: Ref #4, [Ref #4], [Ref #1, #4]
    _REF_NUM_RE = re.compile(r"(?<=#)(\d+)")

    def _rewrite(m: re.Match) -> str:
        old = int(m.group(1))
        new = old_to_new.get(old, old)
        return str(new)

    return _REF_NUM_RE.sub(_rewrite, text)


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
# Context window management
# ---------------------------------------------------------------------------
_MAX_CONTEXT_TOKENS = 128_000
_RESPONSE_HEADROOM = 8_000
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Estimate token count using a char-based heuristic (1 token ≈ 4 chars)."""
    return len(text) // _CHARS_PER_TOKEN


def _trim_context(messages: list[dict], max_tokens: int | None = None) -> list[dict]:
    """Trim oldest messages if estimated tokens exceed the context window.

    Messages are dropped from the front (oldest first).
    Cosmos DB is append-only — trimming only affects in-memory context sent
    to the agent.
    """
    limit = max_tokens or (_MAX_CONTEXT_TOKENS - _RESPONSE_HEADROOM)

    total = sum(_estimate_tokens(m.get("content", "")) for m in messages)
    if total <= limit:
        return messages

    dropped = 0
    trimmed = list(messages)
    while len(trimmed) > 1:
        est = sum(_estimate_tokens(m.get("content", "")) for m in trimmed)
        if est <= limit:
            break
        trimmed.pop(0)
        dropped += 1

    if dropped:
        logger.warning(
            "Context window trimmed: dropped %d oldest messages (estimated %d tokens remaining)",
            dropped,
            sum(_estimate_tokens(m.get("content", "")) for m in trimmed),
        )
    return trimmed


# ---------------------------------------------------------------------------
# Agent client — dual-mode (local HTTP / Foundry with Entra auth)
# ---------------------------------------------------------------------------

def _create_agent_client() -> OpenAI:
    """Create an OpenAI client pointing at the agent endpoint.

    - ``http://`` scheme → local agent, no auth needed.
    - ``https://`` scheme → Foundry hosted agent, Entra token auth.
    """
    endpoint = config.agent_endpoint.rstrip("/")

    if endpoint.startswith("https://"):
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://ai.azure.com/.default"
        )
        client = OpenAI(
            base_url=endpoint,
            api_key=token_provider(),
            default_query={"api-version": "2025-11-15-preview"},
        )
        logger.info("Agent client: Foundry mode (Entra auth) → %s", endpoint)
    else:
        client = OpenAI(
            base_url=endpoint,
            api_key="local",
        )
        logger.info("Agent client: local mode (no auth) → %s", endpoint)

    return client


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
# This block only runs when Chainlit is serving (not during test collection).
try:
    _app = cl.server.app
    _catchall = [r for r in _app.routes if isinstance(r, Route) and getattr(r, "path", "") == "/{full_path:path}"]
    for r in _catchall:
        _app.routes.remove(r)
    _app.include_router(_image_router)
    for r in _catchall:
        _app.routes.append(r)
except AttributeError:
    # Chainlit server not initialised — running in test/CLI context.
    pass


# ---------------------------------------------------------------------------
# Cosmos DB data layer (optional — enabled when COSMOS_ENDPOINT is set)
# ---------------------------------------------------------------------------

if config.cosmos_endpoint:
    @cl.data_layer
    def _get_data_layer():
        from app.data_layer import CosmosDataLayer
        return CosmosDataLayer()
else:
    logger.info("Cosmos DB not configured — conversation persistence disabled")


# ---------------------------------------------------------------------------
# Authentication — Entra ID OAuth + header-based fallback
# ---------------------------------------------------------------------------

def _is_oauth_configured() -> bool:
    """Return True if Chainlit Azure AD OAuth env vars are set.

    Chainlit auto-detects ``OAUTH_AZURE_AD_CLIENT_ID`` to enable the Azure AD
    login button.  When unset (local dev), we fall back to the
    ``header_auth_callback`` which auto-accepts as ``local-user``.
    """
    return bool(os.environ.get("OAUTH_AZURE_AD_CLIENT_ID"))


# Register OAuth callback only when env vars are set — Chainlit's decorator
# raises ValueError at import time if no OAuth provider env var is configured.
if _is_oauth_configured():
    @cl.oauth_callback
    async def oauth_callback(
        provider_id: str,
        token: str,
        raw_user_data: dict,
        default_user: cl.User,
    ) -> cl.User | None:
        """Handle Azure AD OAuth sign-in.

        Called by Chainlit when the user completes the Azure AD login flow.
        Uses the Entra object-ID (``oid``) as the stable user identifier and
        falls back to ``sub`` if ``oid`` is not present.
        """
        if provider_id == "azure-ad":
            oid = raw_user_data.get("oid") or raw_user_data.get("sub", "")
            display = raw_user_data.get("name", oid)
            return cl.User(
                identifier=oid,
                metadata={
                    "provider": "azure-ad",
                    "display_name": display,
                    "email": raw_user_data.get("email", ""),
                },
            )
        return None


@cl.header_auth_callback
async def header_auth_callback(headers: dict) -> cl.User | None:
    """Authenticate the user from request headers.

    - **Azure (Easy Auth):** trusts ``X-MS-CLIENT-PRINCIPAL-ID``.
    - **Local dev:** auto-creates a ``local-user`` identity.

    Returning a ``cl.User`` enables Chainlit's login requirement, which
    in turn activates the conversation history sidebar.
    """
    principal = headers.get("x-ms-client-principal-id")
    if principal:
        display = headers.get("x-ms-client-principal-name", principal)
        return cl.User(identifier=principal, metadata={"provider": "azure-ad", "display_name": display})
    # Local dev — no auth headers, auto-accept as local-user
    return cl.User(identifier="local-user", metadata={"provider": "header"})


# ---------------------------------------------------------------------------
# User identity helper
# ---------------------------------------------------------------------------

def _get_user_id() -> str:
    """Extract user identity for the current session.

    Prefers the Chainlit-authenticated user (set by ``header_auth_callback``).
    Falls back to Easy Auth header or ``"local-user"``.
    """
    try:
        user = cl.user_session.get("user")
        if user and hasattr(user, "identifier") and user.identifier:
            return user.identifier
    except Exception:
        pass
    try:
        headers = cl.user_session.get("http_headers") or {}
        principal = headers.get("x-ms-client-principal-id")
        if principal:
            return principal
    except Exception:
        pass
    return "local-user"


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
    """Initialise per-session agent client and conversation history."""
    client = _create_agent_client()
    cl.user_session.set("client", client)
    cl.user_session.set("messages", [])
    cl.user_session.set("user_id", _get_user_id())
    logger.info("New chat session started (agent endpoint: %s)", config.agent_endpoint)


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict) -> None:
    """Resume a previous conversation from the data layer.

    Rebuilds the in-memory messages list from the stored steps so the
    agent receives the correct conversation context.
    """
    client = _create_agent_client()
    cl.user_session.set("client", client)
    cl.user_session.set("user_id", _get_user_id())

    # Rebuild messages from stored steps
    messages: list[dict] = []
    for step in thread.get("steps", []):
        step_type = step.get("type", "")
        output = step.get("output", "")
        if step_type == "user_message":
            messages.append({"role": "user", "content": output})
        elif step_type == "assistant_message":
            messages.append({"role": "assistant", "content": output})

    cl.user_session.set("messages", messages)
    logger.info(
        "Chat resumed: thread=%s, messages=%d",
        thread.get("id", "?"),
        len(messages),
    )


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle an incoming user message — stream the agent answer."""
    client: OpenAI = cl.user_session.get("client")  # type: ignore[assignment]
    messages: list[dict] = cl.user_session.get("messages")  # type: ignore[assignment]

    # Append user message to conversation history
    messages.append({"role": "user", "content": message.content})

    # Build context: trim to fit context window
    context = _trim_context(messages)

    # Build conversation context string for the agent
    input_parts = []
    for msg_item in context[:-1]:  # All messages except the current one
        input_parts.append(f"[{msg_item['role']}]: {msg_item['content']}")
    conversation_context = "\n".join(input_parts) if input_parts else None

    # Create the response message and stream tokens into it
    msg = cl.Message(content="")
    await msg.send()  # renders the bubble with the thinking indicator

    try:
        user_id: str = cl.user_session.get("user_id") or _get_user_id()  # type: ignore[assignment]
        response = client.responses.create(
            model="kb-agent",
            input=message.content,
            instructions=conversation_context,
            metadata={"user_id": user_id},
            stream=True,
        )

        full_text = ""
        raw_citations: list[dict] = []  # populated from function call output events
        for event in response:
            event_type = getattr(event, "type", None)

            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", "")
                if delta:
                    full_text += delta
                    await msg.stream_token(delta)

            elif event_type == "response.output_item.done":
                # Extract citation data from search tool's function call output
                item = getattr(event, "item", None)
                if item and getattr(item, "type", None) == "function_call_output":
                    output_str = getattr(item, "output", "")
                    try:
                        results = json.loads(output_str)
                        if isinstance(results, list):
                            for r in results:
                                raw_citations.append(r)
                    except (json.JSONDecodeError, TypeError):
                        pass

            elif event_type == "response.completed":
                # Fallback: extract full text if streaming didn't capture it
                if not full_text:
                    resp = getattr(event, "response", None)
                    if resp:
                        for output in getattr(resp, "output", []):
                            for content_item in getattr(output, "content", []):
                                text = getattr(content_item, "text", "")
                                if text:
                                    full_text = text
                                    await msg.stream_token(text)

        if not full_text:
            msg.content = "I wasn't able to generate a response. Please try again."
            await msg.send()
            return

        # Append assistant response to history
        messages.append({"role": "assistant", "content": full_text})
        cl.user_session.set("messages", messages)

    except Exception as e:
        logger.error("Error calling agent: %s", e, exc_info=True)
        msg.content = f"Error communicating with the agent: {e}"
        await msg.send()
        return

    # ---- Post-process: expand refs, normalise inline images ----
    _img_lines = [ln for ln in msg.content.splitlines() if "![" in ln or "/api/images/" in ln]
    if _img_lines:
        for ln in _img_lines:
            logger.info("LLM image line: %s", ln.strip())
    else:
        logger.info("LLM output contains no image references")

    # Build Citation objects from the metadata returned by the agent
    citations: list[Citation] = []
    for c in raw_citations:
        citations.append(Citation(
            article_id=c.get("article_id", ""),
            title=c.get("title", ""),
            section_header=c.get("section_header", ""),
            chunk_index=c.get("chunk_index", 0),
            content=c.get("content", ""),
            image_urls=c.get("image_urls", []),
        ))

    # Expand ref markers so Chainlit can auto-link them
    # (no de-dup/remap — the agent assigns ref numbers 1..N directly)
    msg.content = _expand_ref_markers(msg.content)
    msg.content = _normalise_inline_images(msg.content, [])

    # Create cl.Text elements for each citation — Chainlit auto-links
    # element names that appear literally in the message content
    elements: list[cl.Text] = []
    for idx, cit in enumerate(citations, 1):
        content = _build_citation_content(cit, idx)
        elements.append(cl.Text(
            name=f"Ref #{idx}",
            content=content,
            display="side",
        ))
    if elements:
        msg.elements = elements  # type: ignore[assignment]
        logger.info("Attached %d citation elements to message", len(elements))

    await msg.update()
