"""JWT authentication middleware for Entra ID token validation.

Validates bearer tokens on incoming requests using Microsoft Entra ID
JWKS (JSON Web Key Set).  Skips auth for health probe endpoints and
when ``REQUIRE_AUTH`` is ``false`` (local development).

Supports user context propagation via ``X-User-Groups`` header.  When the
JWT ``groups`` claim is empty (e.g. managed-identity / service tokens),
the middleware reads comma-separated group GUIDs from the header instead.
This allows the web app to forward end-user identity through APIM.
"""

from __future__ import annotations

import logging
import os

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from middleware.request_context import user_claims_var

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_JWKS_URL = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
_DEFAULT_AUDIENCE = "https://ai.azure.com"
_HEALTH_PATHS = {"/liveness", "/readiness", "/health"}
_VALID_ISSUER_PREFIXES = (
    "https://sts.windows.net/",
    "https://login.microsoftonline.com/",
)

# ---------------------------------------------------------------------------
# JWKS client (singleton — cached keys with 5-minute lifespan)
# ---------------------------------------------------------------------------

_jwks_client = PyJWKClient(_JWKS_URL, cache_keys=True, lifespan=300)


class UnauthorizedError(Exception):
    """Raised when a request fails JWT authentication."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _get_header_groups(request: Request) -> list[str]:
    header_groups = request.headers.get("x-user-groups", "")
    return [group.strip() for group in header_groups.split(",") if group.strip()]


def _set_dev_claims(request: Request) -> None:
    user_claims_var.set({
        "user_id": "dev-user",
        "tenant_id": "dev-tenant",
        "groups": _get_header_groups(request) or ["dev-group-guid"],
        "roles": ["contributor"],
    })


def _validate_request(request: Request) -> None:
    """Validate the request and populate the request-scoped claims ContextVar."""
    require_auth = os.environ.get("REQUIRE_AUTH", "true")
    if require_auth.lower() == "false":
        _set_dev_claims(request)
        return

    if request.url.path in _HEALTH_PATHS:
        return

    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")

    token = auth_header[7:]
    audiences = [_DEFAULT_AUDIENCE]
    app_uri = os.environ.get("AGENT_APP_URI")
    if app_uri:
        audiences.append(app_uri)

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audiences,
            options={"verify_iss": False},
        )

        issuer = claims.get("iss", "")
        if not any(issuer.startswith(prefix) for prefix in _VALID_ISSUER_PREFIXES):
            raise UnauthorizedError(f"Invalid issuer: {issuer}")

    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Token has expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise UnauthorizedError("Invalid audience") from exc
    except jwt.PyJWTError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise UnauthorizedError(str(exc)) from exc

    groups = claims.get("groups", [])
    if not groups:
        groups = _get_header_groups(request)

    user_claims_var.set({
        "user_id": claims.get("oid", ""),
        "tenant_id": claims.get("tid", ""),
        "groups": groups,
        "roles": claims.get("roles", []),
    })


async def require_jwt_auth(request: Request) -> None:
    """FastAPI dependency that enforces the same JWT logic as the Starlette middleware."""
    try:
        _validate_request(request)
    except UnauthorizedError as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "detail": exc.detail},
        ) from exc


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that validates Entra ID JWT bearer tokens."""

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        try:
            _validate_request(request)
        except UnauthorizedError as exc:
            return _unauthorized(exc.detail)

        return await call_next(request)


def _unauthorized(detail: str) -> JSONResponse:
    """Return a 401 JSON response."""
    return JSONResponse(
        status_code=401,
        content={"error": "unauthorized", "detail": detail},
    )
