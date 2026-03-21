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


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that validates Entra ID JWT bearer tokens."""

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        # Skip auth when disabled (local dev)
        require_auth = os.environ.get("REQUIRE_AUTH", "true")
        if require_auth.lower() == "false":
            # Set default dev claims so tools receive security context.
            # Honour X-User-Groups header even in dev mode so local testing
            # of the header propagation path works end-to-end.
            dev_groups = ["dev-group-guid"]
            header_groups = request.headers.get("x-user-groups", "")
            if header_groups:
                dev_groups = [g.strip() for g in header_groups.split(",") if g.strip()]
            user_claims_var.set({
                "user_id": "dev-user",
                "tenant_id": "dev-tenant",
                "groups": dev_groups,
                "roles": ["contributor"],
            })
            return await call_next(request)

        # Skip auth for health probes
        if request.url.path in _HEALTH_PATHS:
            return await call_next(request)

        # Extract bearer token
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return _unauthorized("Missing or invalid Authorization header")

        token = auth_header[7:]  # Strip "Bearer "

        # Build accepted audiences
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
                options={"verify_iss": False},  # manual issuer check below
            )

            # Validate issuer prefix (multi-tenant)
            issuer = claims.get("iss", "")
            if not any(issuer.startswith(p) for p in _VALID_ISSUER_PREFIXES):
                return _unauthorized(f"Invalid issuer: {issuer}")

        except jwt.ExpiredSignatureError:
            return _unauthorized("Token has expired")
        except jwt.InvalidAudienceError:
            return _unauthorized("Invalid audience")
        except jwt.PyJWTError as exc:
            logger.warning("JWT validation failed: %s", exc)
            return _unauthorized(str(exc))

        # Propagate validated claims to downstream tools via ContextVar.
        # When the JWT has no groups claim (service-to-service token from
        # the web app's managed identity), fall back to X-User-Groups header
        # which the web app sets from the end-user's Easy Auth / OAuth claims.
        groups = claims.get("groups", [])
        if not groups:
            header_groups = request.headers.get("x-user-groups", "")
            if header_groups:
                groups = [g.strip() for g in header_groups.split(",") if g.strip()]

        user_claims_var.set({
            "user_id": claims.get("oid", ""),
            "tenant_id": claims.get("tid", ""),
            "groups": groups,
            "roles": claims.get("roles", []),
        })

        return await call_next(request)


def _unauthorized(detail: str) -> JSONResponse:
    """Return a 401 JSON response."""
    return JSONResponse(
        status_code=401,
        content={"error": "unauthorized", "detail": detail},
    )
