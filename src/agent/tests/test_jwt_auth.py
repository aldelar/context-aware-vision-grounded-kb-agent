"""Tests for JWT authentication middleware.

Covers auth-disabled bypass, health probe bypass, missing/invalid headers,
token validation errors (expired, bad audience, bad issuer), valid tokens,
and custom ``AGENT_APP_URI`` audience.
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# RSA key pair for test token signing
# ---------------------------------------------------------------------------

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_key = _private_key.public_key()


def _public_key_obj():
    """Return the raw public key object (used by the mock signing key)."""
    return _public_key


def _encode_token(claims: dict, *, headers: dict | None = None) -> str:
    """Encode a JWT signed with the test RSA key."""
    return pyjwt.encode(
        claims,
        _private_key,
        algorithm="RS256",
        headers=headers,
    )


def _valid_claims(**overrides) -> dict:
    """Return a minimal set of valid JWT claims."""
    now = int(time.time())
    defaults = {
        "iss": "https://sts.windows.net/test-tenant-id/",
        "aud": "https://ai.azure.com",
        "iat": now - 60,
        "exp": now + 3600,
        "sub": "test-subject",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Helpers — build a fresh Starlette app with the middleware
# ---------------------------------------------------------------------------


async def _ok_endpoint(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def _build_app() -> Starlette:
    """Create a minimal Starlette app with JWTAuthMiddleware mounted.

    Must be called AFTER env vars are set because the middleware reads
    ``REQUIRE_AUTH`` at dispatch time and the module-level ``_jwks_client``
    is created at import time.
    """
    from middleware.jwt_auth import JWTAuthMiddleware

    app = Starlette(
        routes=[
            Route("/responses", _ok_endpoint),
            Route("/liveness", _ok_endpoint),
            Route("/readiness", _ok_endpoint),
            Route("/health", _ok_endpoint),
        ],
    )
    app.add_middleware(JWTAuthMiddleware)
    return app


def _mock_jwks():
    """Return a patcher that replaces the module-level _jwks_client."""
    mock_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = _public_key_obj()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
    return patch("middleware.jwt_auth._jwks_client", mock_client), mock_client


# ===========================================================================
# 1. Auth disabled (REQUIRE_AUTH=false)
# ===========================================================================


class TestAuthDisabled:
    """When REQUIRE_AUTH=false, all requests pass through without tokens."""

    def test_request_without_token_passes(self, monkeypatch):
        monkeypatch.setenv("REQUIRE_AUTH", "false")
        app = _build_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/responses")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_request_with_invalid_token_passes(self, monkeypatch):
        monkeypatch.setenv("REQUIRE_AUTH", "false")
        app = _build_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/responses",
            headers={"Authorization": "Bearer garbage"},
        )
        assert resp.status_code == 200

    @pytest.mark.parametrize("value", ["False", "FALSE", "fAlSe"])
    def test_case_insensitive(self, monkeypatch, value):
        monkeypatch.setenv("REQUIRE_AUTH", value)
        app = _build_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/responses")
        assert resp.status_code == 200


# ===========================================================================
# 2. Health probe bypass
# ===========================================================================


class TestHealthProbeBypass:
    """Health probe paths skip auth even when auth is enabled."""

    @pytest.mark.parametrize("path", ["/liveness", "/readiness", "/health"])
    def test_health_paths_bypass_auth(self, monkeypatch, path):
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        app = _build_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(path)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.parametrize("path", ["/liveness", "/readiness", "/health"])
    def test_health_paths_bypass_without_token(self, monkeypatch, path):
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        app = _build_app()
        client = TestClient(app, raise_server_exceptions=False)

        # No Authorization header at all
        resp = client.get(path)
        assert resp.status_code == 200


# ===========================================================================
# 3. Missing Authorization header
# ===========================================================================


class TestMissingAuthHeader:
    """Requests without Authorization header are rejected."""

    def test_no_auth_header_returns_401(self, monkeypatch):
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        app = _build_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/responses")
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"] == "unauthorized"
        assert "Missing" in body["detail"] or "invalid" in body["detail"].lower()


# ===========================================================================
# 4. Invalid Authorization header (not Bearer)
# ===========================================================================


class TestInvalidAuthScheme:
    """Non-Bearer auth schemes are rejected."""

    @pytest.mark.parametrize(
        "header_value",
        [
            "Basic dXNlcjpwYXNz",
            "Token abc123",
            "bearer-ish something",
            "",
        ],
    )
    def test_non_bearer_returns_401(self, monkeypatch, header_value):
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        app = _build_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/responses",
            headers={"Authorization": header_value},
        )
        assert resp.status_code == 401
        assert resp.json()["error"] == "unauthorized"


# ===========================================================================
# 5. Invalid / malformed token
# ===========================================================================


class TestMalformedToken:
    """Malformed JWT strings are rejected."""

    def test_garbage_token_returns_401(self, monkeypatch):
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        jwks_patcher, mock_client = _mock_jwks()
        # Make JWKS client raise for garbage tokens
        mock_client.get_signing_key_from_jwt.side_effect = pyjwt.PyJWTError(
            "Invalid token"
        )

        with jwks_patcher:
            app = _build_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/responses",
                headers={"Authorization": "Bearer not.a.jwt"},
            )

        assert resp.status_code == 401
        assert resp.json()["error"] == "unauthorized"

    def test_unsigned_token_returns_401(self, monkeypatch):
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        jwks_patcher, mock_client = _mock_jwks()
        mock_client.get_signing_key_from_jwt.side_effect = pyjwt.PyJWTError(
            "Unable to find a signing key"
        )

        with jwks_patcher:
            app = _build_app()
            client = TestClient(app, raise_server_exceptions=False)

            # Token with alg=none
            token = pyjwt.encode(
                _valid_claims(), "secret", algorithm="HS256"
            )
            resp = client.get(
                "/responses",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 401


# ===========================================================================
# 6. Expired token
# ===========================================================================


class TestExpiredToken:
    """Expired tokens are rejected with a specific message."""

    def test_expired_token_returns_401(self, monkeypatch):
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        jwks_patcher, _ = _mock_jwks()

        now = int(time.time())
        token = _encode_token(
            _valid_claims(iat=now - 7200, exp=now - 3600),
        )

        with jwks_patcher:
            app = _build_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/responses",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 401
        body = resp.json()
        assert body["error"] == "unauthorized"
        assert "expired" in body["detail"].lower()


# ===========================================================================
# 7. Invalid audience
# ===========================================================================


class TestInvalidAudience:
    """Tokens with wrong audience are rejected."""

    def test_wrong_audience_returns_401(self, monkeypatch):
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.delenv("AGENT_APP_URI", raising=False)
        jwks_patcher, _ = _mock_jwks()

        token = _encode_token(
            _valid_claims(aud="https://wrong-audience.example.com"),
        )

        with jwks_patcher:
            app = _build_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/responses",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 401
        body = resp.json()
        assert body["error"] == "unauthorized"
        assert "audience" in body["detail"].lower()


# ===========================================================================
# 8. Invalid issuer
# ===========================================================================


class TestInvalidIssuer:
    """Tokens with untrusted issuers are rejected."""

    @pytest.mark.parametrize(
        "bad_issuer",
        [
            "https://evil.example.com/",
            "https://sts.windows.net.evil.com/tenant/",
            "http://sts.windows.net/tenant/",  # http not https
            "",
        ],
    )
    def test_bad_issuer_returns_401(self, monkeypatch, bad_issuer):
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.delenv("AGENT_APP_URI", raising=False)
        jwks_patcher, _ = _mock_jwks()

        token = _encode_token(_valid_claims(iss=bad_issuer))

        with jwks_patcher:
            app = _build_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/responses",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 401
        body = resp.json()
        assert body["error"] == "unauthorized"
        assert "issuer" in body["detail"].lower()


# ===========================================================================
# 9. Valid token — request passes through
# ===========================================================================


class TestValidToken:
    """A properly signed token with correct claims passes through."""

    def test_valid_token_returns_200(self, monkeypatch):
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.delenv("AGENT_APP_URI", raising=False)
        jwks_patcher, _ = _mock_jwks()

        token = _encode_token(_valid_claims())

        with jwks_patcher:
            app = _build_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/responses",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_valid_token_with_login_issuer(self, monkeypatch):
        """Accept issuer from login.microsoftonline.com as well."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.delenv("AGENT_APP_URI", raising=False)
        jwks_patcher, _ = _mock_jwks()

        token = _encode_token(
            _valid_claims(
                iss="https://login.microsoftonline.com/test-tenant/v2.0",
            ),
        )

        with jwks_patcher:
            app = _build_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/responses",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200

    def test_bearer_case_insensitive(self, monkeypatch):
        """'Bearer' prefix matching is case-insensitive."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.delenv("AGENT_APP_URI", raising=False)
        jwks_patcher, _ = _mock_jwks()

        token = _encode_token(_valid_claims())

        with jwks_patcher:
            app = _build_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/responses",
                headers={"Authorization": f"BEARER {token}"},
            )

        assert resp.status_code == 200


# ===========================================================================
# 10. AGENT_APP_URI env var — custom audience accepted
# ===========================================================================


class TestAgentAppUri:
    """Custom audience from AGENT_APP_URI is accepted."""

    def test_custom_audience_accepted(self, monkeypatch):
        custom_uri = "api://my-custom-agent"
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("AGENT_APP_URI", custom_uri)
        jwks_patcher, _ = _mock_jwks()

        token = _encode_token(_valid_claims(aud=custom_uri))

        with jwks_patcher:
            app = _build_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/responses",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_default_audience_still_works_with_app_uri(self, monkeypatch):
        """Default audience should still be accepted when AGENT_APP_URI is set."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("AGENT_APP_URI", "api://custom")
        jwks_patcher, _ = _mock_jwks()

        token = _encode_token(_valid_claims(aud="https://ai.azure.com"))

        with jwks_patcher:
            app = _build_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/responses",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200

    def test_wrong_audience_rejected_even_with_app_uri(self, monkeypatch):
        """A token with neither default nor custom audience is rejected."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("AGENT_APP_URI", "api://custom")
        jwks_patcher, _ = _mock_jwks()

        token = _encode_token(
            _valid_claims(aud="https://completely-wrong.example.com"),
        )

        with jwks_patcher:
            app = _build_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/responses",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 401
        assert "audience" in resp.json()["detail"].lower()


# ===========================================================================
# 11. ContextVar propagation — claims are set on request context
# ===========================================================================


async def _claims_endpoint(request: Request) -> JSONResponse:
    """Return the current user_claims_var value."""
    from middleware.request_context import user_claims_var

    return JSONResponse(user_claims_var.get())


def _build_claims_app() -> Starlette:
    """App with an endpoint that returns the ContextVar claims."""
    from middleware.jwt_auth import JWTAuthMiddleware

    app = Starlette(
        routes=[
            Route("/claims", _claims_endpoint),
        ],
    )
    app.add_middleware(JWTAuthMiddleware)
    return app


class TestContextVarPropagation:
    """JWT middleware populates user_claims_var for downstream use."""

    def test_dev_claims_set_when_auth_disabled(self, monkeypatch):
        monkeypatch.setenv("REQUIRE_AUTH", "false")
        app = _build_claims_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/claims")
        assert resp.status_code == 200
        claims = resp.json()
        assert claims["user_id"] == "dev-user"
        assert claims["tenant_id"] == "dev-tenant"
        assert claims["groups"] == ["dev-group-guid"]
        assert claims["roles"] == ["contributor"]

    def test_jwt_claims_set_on_valid_token(self, monkeypatch):
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.delenv("AGENT_APP_URI", raising=False)
        jwks_patcher, _ = _mock_jwks()

        token = _encode_token(
            _valid_claims(
                oid="user-object-id",
                tid="tenant-123",
                groups=["group-a", "group-b"],
                roles=["reader"],
            ),
        )

        with jwks_patcher:
            app = _build_claims_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/claims",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        claims = resp.json()
        assert claims["user_id"] == "user-object-id"
        assert claims["tenant_id"] == "tenant-123"
        assert claims["groups"] == ["group-a", "group-b"]
        assert claims["roles"] == ["reader"]

    def test_claims_default_empty_when_missing(self, monkeypatch):
        """Claims fields default to empty when absent from JWT."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.delenv("AGENT_APP_URI", raising=False)
        jwks_patcher, _ = _mock_jwks()

        # Token with no oid, tid, groups, or roles
        token = _encode_token(_valid_claims())

        with jwks_patcher:
            app = _build_claims_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/claims",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        claims = resp.json()
        assert claims["user_id"] == ""
        assert claims["tenant_id"] == ""
        assert claims["groups"] == []
        assert claims["roles"] == []


# ===========================================================================
# 12. X-User-Groups header propagation
# ===========================================================================


class TestUserGroupsHeader:
    """X-User-Groups header is used when JWT has no groups claim."""

    def test_header_groups_used_when_jwt_has_no_groups(self, monkeypatch):
        """Service token (no groups) + X-User-Groups header → groups populated."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.delenv("AGENT_APP_URI", raising=False)
        jwks_patcher, _ = _mock_jwks()

        # Token with NO groups claim
        token = _encode_token(_valid_claims(oid="svc-principal"))

        with jwks_patcher:
            app = _build_claims_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/claims",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-User-Groups": "guid-1,guid-2",
                },
            )

        assert resp.status_code == 200
        claims = resp.json()
        assert claims["groups"] == ["guid-1", "guid-2"]

    def test_jwt_groups_take_precedence_over_header(self, monkeypatch):
        """When JWT has groups, the header is ignored."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.delenv("AGENT_APP_URI", raising=False)
        jwks_patcher, _ = _mock_jwks()

        token = _encode_token(
            _valid_claims(groups=["jwt-group"]),
        )

        with jwks_patcher:
            app = _build_claims_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/claims",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-User-Groups": "header-group",
                },
            )

        assert resp.status_code == 200
        claims = resp.json()
        assert claims["groups"] == ["jwt-group"]

    def test_header_groups_whitespace_trimmed(self, monkeypatch):
        """Whitespace around group GUIDs in header is trimmed."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.delenv("AGENT_APP_URI", raising=False)
        jwks_patcher, _ = _mock_jwks()

        token = _encode_token(_valid_claims())

        with jwks_patcher:
            app = _build_claims_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/claims",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-User-Groups": " guid-1 , guid-2 , ",
                },
            )

        assert resp.status_code == 200
        claims = resp.json()
        assert claims["groups"] == ["guid-1", "guid-2"]

    def test_empty_header_no_groups(self, monkeypatch):
        """Empty X-User-Groups header results in empty groups."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.delenv("AGENT_APP_URI", raising=False)
        jwks_patcher, _ = _mock_jwks()

        token = _encode_token(_valid_claims())

        with jwks_patcher:
            app = _build_claims_app()
            client = TestClient(app, raise_server_exceptions=False)

            resp = client.get(
                "/claims",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-User-Groups": "",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["groups"] == []

    def test_dev_mode_honours_header_groups(self, monkeypatch):
        """In dev mode (REQUIRE_AUTH=false), X-User-Groups overrides defaults."""
        monkeypatch.setenv("REQUIRE_AUTH", "false")
        app = _build_claims_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/claims",
            headers={"X-User-Groups": "custom-guid"},
        )

        assert resp.status_code == 200
        claims = resp.json()
        assert claims["groups"] == ["custom-guid"]

    def test_dev_mode_default_groups_without_header(self, monkeypatch):
        """In dev mode without header, default dev groups are used."""
        monkeypatch.setenv("REQUIRE_AUTH", "false")
        app = _build_claims_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/claims")

        assert resp.status_code == 200
        claims = resp.json()
        assert claims["groups"] == ["dev-group-guid"]
