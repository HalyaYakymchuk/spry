"""Cognito JWT verification for Agenda Lambda.

Runs in Lambda outside VPC, directly fetching and caching Cognito JWKS.
"""

from functools import lru_cache
import json
import logging
import os
from typing import Any
import urllib.request

import jwt
from jwt import PyJWK

from app.config import get_settings

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Base exception for authentication failures."""

    pass


class TokenMissingError(AuthError):
    """Raised when Authorization header or token is absent or malformed."""

    pass


class TokenValidationError(AuthError):
    """Raised when token signature, expiration, or claims fail validation."""

    pass


# In-memory JWKS cache across invocations
_JWKS_CACHE: dict[str, list[dict[str, Any]]] = {}


def clear_jwks_cache() -> None:
    """Clear in-memory JWKS cache (useful in tests)."""
    _JWKS_CACHE.clear()


def fetch_jwks(jwks_url: str, *, force_refresh: bool = False) -> list[dict[str, Any]]:
    """Fetch and cache JWKS keys from Cognito or environment."""
    if not force_refresh and jwks_url in _JWKS_CACHE:
        return _JWKS_CACHE[jwks_url]

    # 1. Check COGNITO_JWKS environment variable / settings fallback
    settings = get_settings()
    jwks_env = os.getenv("COGNITO_JWKS") or getattr(settings, "cognito_jwks", None)
    if jwks_env:
        try:
            parsed = json.loads(jwks_env)
            keys = parsed.get("keys", [])
            if keys:
                _JWKS_CACHE[jwks_url] = keys
                return keys
        except Exception as exc:
            logger.warning("Failed to parse COGNITO_JWKS env: %s", exc)

    # 2. Fetch directly from Cognito JWKS endpoint
    req = urllib.request.Request(
        jwks_url,
        headers={"User-Agent": "Spry-Agenda-Lambda-Auth"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode("utf-8"))
            keys = data.get("keys", [])
            _JWKS_CACHE[jwks_url] = keys
            return keys
    except Exception as exc:
        raise TokenValidationError(f"Failed to fetch JWKS from {jwks_url}: {exc}") from exc


def get_bearer_token(headers: dict[str, Any] | None) -> str:
    """Extract Bearer token from request headers (case-insensitive)."""
    if not headers:
        raise TokenMissingError("Missing Authorization header")

    auth_val = None
    for k, v in headers.items():
        if k.lower() == "authorization":
            auth_val = v
            break

    if not auth_val or not str(auth_val).strip():
        raise TokenMissingError("Missing Authorization header")

    parts = str(auth_val).strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise TokenMissingError(
            "Invalid Authorization header format. Expected 'Bearer <token>'"
        )

    return parts[1].strip()


def verify_cognito_token(
    token: str,
    *,
    user_pool_id: str | None = None,
    client_id: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Verify Cognito JWT token against user pool JWKS and return claims.

    Args:
        token: JWT string.
        user_pool_id: Optional user pool ID (defaults to COGNITO_USER_POOL_ID).
        client_id: Optional client ID (defaults to COGNITO_CLIENT_ID).
        region: Optional AWS region (defaults to COGNITO_REGION or AWS_REGION).

    Returns:
        dict: Validated token claims (contains 'sub').

    Raises:
        TokenValidationError: If validation fails.
    """
    settings = get_settings()
    region = (
        region
        or os.getenv("COGNITO_REGION")
        or os.getenv("AWS_REGION")
        or getattr(settings, "cognito_region", "eu-north-1")
    )
    user_pool_id = (
        user_pool_id
        or os.getenv("COGNITO_USER_POOL_ID")
        or getattr(settings, "cognito_user_pool_id", "")
    )
    client_id = (
        client_id
        or os.getenv("COGNITO_CLIENT_ID")
        or getattr(settings, "cognito_client_id", "")
    )

    if not user_pool_id:
        raise TokenValidationError("COGNITO_USER_POOL_ID is not configured")

    issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
    jwks_url = f"{issuer}/.well-known/jwks.json"

    # Extract kid from unverified header
    try:
        unverified_headers = jwt.get_unverified_header(token)
    except Exception as exc:
        raise TokenValidationError(f"Invalid token header: {exc}") from exc

    kid = unverified_headers.get("kid")
    if not kid:
        raise TokenValidationError("Missing 'kid' in token header")

    keys = fetch_jwks(jwks_url)
    key_dict = next((k for k in keys if k.get("kid") == kid), None)
    if not key_dict:
        # Refresh cache once in case keys were rotated
        keys = fetch_jwks(jwks_url, force_refresh=True)
        key_dict = next((k for k in keys if k.get("kid") == kid), None)

    if not key_dict:
        raise TokenValidationError(f"Public key for kid '{kid}' not found in JWKS")

    try:
        signing_key = PyJWK.from_dict(key_dict).key
    except Exception as exc:
        raise TokenValidationError(f"Failed to construct key from JWKS: {exc}") from exc

    # Decode and validate signature, exp, iss
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=issuer,
            leeway=60,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": False,  # We validate client_id/aud explicitly below
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenValidationError("Token has expired") from exc
    except jwt.InvalidIssuerError as exc:
        raise TokenValidationError("Invalid token issuer") from exc
    except jwt.PyJWTError as exc:
        raise TokenValidationError(f"Token validation failed: {exc}") from exc

    # Validate audience / client_id
    if client_id:
        token_client_id = claims.get("client_id") or claims.get("aud")
        if token_client_id != client_id:
            raise TokenValidationError(
                f"Token audience/client_id '{token_client_id}' does not match '{client_id}'"
            )

    sub = claims.get("sub")
    if not sub:
        raise TokenValidationError("Token missing 'sub' claim")

    return claims


def authenticate_request(
    headers: dict[str, Any] | None,
    *,
    user_pool_id: str | None = None,
    client_id: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Helper to extract and verify Bearer token from HTTP headers."""
    token = get_bearer_token(headers)
    return verify_cognito_token(
        token,
        user_pool_id=user_pool_id,
        client_id=client_id,
        region=region,
    )
