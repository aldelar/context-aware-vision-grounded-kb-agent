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
from azure.identity import DefaultAzureCredential
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
# Agent client — plain HTTP (internal Container App or local)
# ---------------------------------------------------------------------------

# Placeholder group injected for every authenticated user until a future epic
# adds a persona-switcher UI.  The agent's simulated group_resolver maps any
# non-empty group list to departments=["engineering"].
_DEFAULT_USER_GROUP = "00000000-0000-0000-0000-000000000001"


def _get_user_groups() -> list[str]:
    """Extract the current user's Entra group GUIDs from session metadata.

    When Entra doesn't provide groups (groupMembershipClaims not configured),
    falls back to a hardcoded placeholder so the security filter pipeline
    always resolves at least one department.
    """
    try:
        user = cl.user_session.get("user")
        if user:
            groups = getattr(user, "metadata", {}).get("groups", []) or []
            if groups:
                return groups
            # Authenticated but no Entra groups — inject default
            return [_DEFAULT_USER_GROUP]
    except Exception:
        pass
    return []


def _create_agent_client(user_groups: list[str] | None = None) -> OpenAI:
    """Create an OpenAI client pointing at the agent endpoint.

    - ``http://`` endpoints (local dev, internal FQDN): plain HTTP, no auth
    - ``https://`` endpoints (registered APIM proxy URL): Entra bearer token
      via DefaultAzureCredential with scope ``https://ai.azure.com/.default``

    When *user_groups* is provided, passes them as ``X-User-Groups`` header
    so the agent can apply department-scoped security filters.
    """
    endpoint = config.agent_endpoint.rstrip("/")

    # Build extra headers for user context propagation
    extra_headers: dict[str, str] = {}
    if user_groups:
        extra_headers["X-User-Groups"] = ",".join(user_groups)

    if endpoint.startswith("https://"):
        credential = DefaultAzureCredential()
        token = credential.get_token("https://ai.azure.com/.default")
        client = OpenAI(
            base_url=endpoint,
            api_key=token.token,
            default_headers=extra_headers or None,
        )
        logger.info("Agent client → %s (Entra auth, groups=%s)", endpoint, user_groups)
    else:
        client = OpenAI(
            base_url=endpoint,
            api_key="local",
            default_headers=extra_headers or None,
        )
        logger.info("Agent client → %s (no auth, groups=%s)", endpoint, user_groups)
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

    # Increase Socket.IO ping timeout — the agent can take 60-120s during
    # tool-calling before the first text token streams back.  The default
    # 20s causes "Could not reach the server" in the browser.
    _sio = cl.server.sio
    if hasattr(_sio, "eio"):
        _sio.eio.ping_timeout = 120
        _sio.eio.ping_interval = 30
        logger.info("Socket.IO ping_timeout set to %ds", _sio.eio.ping_timeout)
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
            groups = raw_user_data.get("groups", [])
            return cl.User(
                identifier=oid,
                metadata={
                    "provider": "azure-ad",
                    "display_name": display,
                    "email": raw_user_data.get("email", ""),
                    "groups": groups,
                },
            )
        return None


@cl.header_auth_callback
async def header_auth_callback(headers: dict) -> cl.User | None:
    """Authenticate the user from request headers.

    - **Azure (Easy Auth):** trusts ``X-MS-CLIENT-PRINCIPAL-ID``.
      Decodes ``X-MS-CLIENT-PRINCIPAL`` (Base64 JSON) to extract the
      friendly display name from the claims.
    - **Local dev:** auto-creates a ``local-user`` identity.

    Returning a ``cl.User`` enables Chainlit's login requirement, which
    in turn activates the conversation history sidebar.
    """
    principal = headers.get("x-ms-client-principal-id")
    if principal:
        display = headers.get("x-ms-client-principal-name", principal)
        groups: list[str] = []
        # Easy Auth encodes claims in X-MS-CLIENT-PRINCIPAL (Base64 JSON).
        # Extract the friendly "name" claim and group memberships.
        encoded = headers.get("x-ms-client-principal")
        if encoded:
            try:
                import base64
                payload = json.loads(base64.b64decode(encoded))
                raw_claims = payload.get("claims", [])
                # "groups" is multi-value: each group is a separate entry
                groups = [c["val"] for c in raw_claims if c.get("typ") == "groups"]
                claims_map = {c["typ"]: c["val"] for c in raw_claims}
                display = claims_map.get("name", display)
            except Exception:
                pass
        return cl.User(
            identifier=display,
            metadata={"provider": "azure-ad", "oid": principal, "groups": groups},
        )
    # Local dev — no auth headers, auto-accept as local-user
    return cl.User(identifier="local-user", metadata={"provider": "header", "groups": []})


# ---------------------------------------------------------------------------
# User identity helper
# ---------------------------------------------------------------------------

def _get_user_id() -> str:
    """Extract user identity for the current session.

    Prefers the Chainlit-authenticated user (set by ``header_auth_callback``).
    Uses the stable OID from metadata when available, falling back to identifier.
    """
    try:
        user = cl.user_session.get("user")
        if user:
            # Prefer the stable Entra object-ID stored in metadata
            oid = getattr(user, "metadata", {}).get("oid")
            if oid:
                return oid
            if hasattr(user, "identifier") and user.identifier:
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
    user_groups = _get_user_groups()
    client = _create_agent_client(user_groups=user_groups)
    cl.user_session.set("client", client)
    cl.user_session.set("user_id", _get_user_id())
    logger.info("New chat session started (agent endpoint: %s, groups=%s)", config.agent_endpoint, user_groups)


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict) -> None:
    """Resume a previous conversation from the data layer.

    The agent owns conversation history via conversation_id, so we only
    need to re-create the client — no local messages rebuild needed.

    Element content is persisted in Cosmos (custom ``content`` field) but
    the ``chainlitKey`` used by the frontend to fetch file content is
    ephemeral.  Re-hydrate each element by writing its content back to
    the session file store so the frontend can retrieve it.
    """
    user_groups = _get_user_groups()
    client = _create_agent_client(user_groups=user_groups)
    cl.user_session.set("client", client)
    cl.user_session.set("user_id", _get_user_id())

    # Re-hydrate element content so Refs work after resume
    session = cl.context.session
    elements = thread.get("elements", [])
    logger.info("Resume: found %d elements in thread", len(elements))
    for el in elements:
        logger.info("Resume element: name=%s, type=%s, keys=%s, content_len=%s",
                     el.get("name"), el.get("type"), list(el.keys()),
                     len(el.get("content", "")) if el.get("content") else 0)
        content = el.get("content")
        if not content:
            continue
        name = el.get("name", "element")
        mime = el.get("mime") or "text/plain"
        ref = await session.persist_file(name=name, content=content, mime=mime)
        el["chainlitKey"] = ref["id"]
        # The frontend's resume_thread handler does NOT resolve
        # chainlitKey → URL (unlike the element/set_sidebar_elements
        # handlers), so we must set the URL explicitly.
        el["url"] = f"/project/file/{ref['id']}?session_id={session.id}"
        logger.info("Resume element persisted: name=%s, chainlitKey=%s, url=%s",
                     name, ref["id"], el["url"])

    logger.info("Chat resumed: thread=%s", thread.get("id", "?"))


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle an incoming user message — stream the agent answer."""
    client: OpenAI = cl.user_session.get("client")  # type: ignore[assignment]
    thread_id = cl.context.session.thread_id

    # Create the response message and stream tokens into it
    msg = cl.Message(content="")
    await msg.send()  # renders the bubble with the thinking indicator

    try:
        response = client.responses.create(
            model="kb-agent",
            input=message.content,
            stream=True,
            extra_body={"conversation": {"id": thread_id}},
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
                        parsed = json.loads(output_str)
                        # Structured output: {"results": [...], "summary": "..."}
                        if isinstance(parsed, dict) and "results" in parsed:
                            for r in parsed["results"]:
                                raw_citations.append(r)
                        elif isinstance(parsed, list):
                            for r in parsed:
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
        logger.info("Attached %d citation references to message", len(elements))

    await msg.update()
