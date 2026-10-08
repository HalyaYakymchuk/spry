import json
import logging
import os
import urllib.request
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

try:
    from jose import JWTError, jwt
    _USE_JOSE = True
except ImportError:
    import jwt
    from jwt import PyJWTError as JWTError
    _USE_JOSE = False

from app.api.router import api_router
from app.config import get_settings

logger = logging.getLogger(__name__)

# Cognito configuration
REGION = os.getenv("COGNITO_REGION") or os.getenv("AWS_REGION") or "eu-north-1"
USER_POOL_ID = (
    os.getenv("COGNITO_USER_POOL_ID")
    or os.getenv("USER_POOL_ID")
    or "eu-north-1_tJwOveqnV"
)
CLIENT_ID = (
    os.getenv("COGNITO_CLIENT_ID")
    or os.getenv("USER_POOL_CLIENT_ID")
    or "7qrffcg5chk6nio4ml189gio8"
)

JWKS_URL = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"

# In-memory public keys cache
CACHED_KEYS: Optional[list] = None


def get_jwks() -> list:
    global CACHED_KEYS
    if CACHED_KEYS:
        return CACHED_KEYS

    # Check COGNITO_JWKS environment variable if available
    jwks_env = os.getenv("COGNITO_JWKS")
    if jwks_env:
        try:
            parsed = json.loads(jwks_env)
            CACHED_KEYS = parsed.get("keys", [])
            if CACHED_KEYS:
                return CACHED_KEYS
        except Exception as e:
            logger.warning(f"Failed to parse COGNITO_JWKS env: {e}")

    # Fetch from JWKS_URL and cache in memory
    req = urllib.request.Request(
        JWKS_URL,
        headers={"User-Agent": "FastAPI-Cognito-Auth"},
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        data = json.loads(res.read().decode("utf-8"))
        CACHED_KEYS = data.get("keys", [])
        return CACHED_KEYS


def verify_jwt_token(token: str) -> dict:
    keys = get_jwks()
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    if not kid:
        raise ValueError("Missing 'kid' in token header")

    key_dict = next((k for k in keys if k["kid"] == kid), None)
    if not key_dict:
        raise ValueError("Public key not found in JWKS")

    if _USE_JOSE:
        signing_key = key_dict
    else:
        from jwt import PyJWK
        signing_key = PyJWK.from_dict(key_dict).key

    # Validate signature, exp, iss
    claims = jwt.decode(
        token,
        signing_key,
        algorithms=["RS256"],
        issuer=ISSUER,
        options={
            "verify_signature": True,
            "verify_exp": True,
            "verify_iss": True,
            "verify_aud": False,  # Cognito access tokens use client_id instead of aud
        },
    )

    # Validate client_id for Cognito access token or aud for Cognito ID token
    token_client_id = claims.get("client_id") or claims.get("aud")
    if CLIENT_ID and token_client_id != CLIENT_ID:
        raise ValueError("Invalid client_id claim")

    return claims


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["authorization", "content-type"],
    )

    # 2. Middleware for Cognito JWT verification
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        # Allow preflight OPTIONS and public endpoints
        if request.method == "OPTIONS":
            response = await call_next(request)
            if response.status_code == 405:
                return JSONResponse(status_code=200, content={"status": "ok"})
            return response

        if request.url.path in [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]:
            return await call_next(request)

        # Protect /api routes
        if request.url.path.startswith("/api/"):
            auth_header = request.headers.get("Authorization") or request.headers.get(
                "authorization"
            )
            if not auth_header or not auth_header.startswith("Bearer "):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing or invalid Authorization header"},
                    headers={"WWW-Authenticate": "Bearer"},
                )

            parts = auth_header.split(" ", 1)
            if len(parts) != 2 or not parts[1].strip():
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing or invalid Authorization header"},
                    headers={"WWW-Authenticate": "Bearer"},
                )

            token = parts[1].strip()
            try:
                claims = verify_jwt_token(token)
                request.state.user = claims
            except (JWTError, ValueError, Exception) as e:
                return JSONResponse(
                    status_code=401,
                    content={"detail": f"Unauthorized: {str(e)}"},
                    headers={"WWW-Authenticate": "Bearer"},
                )

        return await call_next(request)

    @app.get("/health", tags=["health"], summary="Liveness probe")
    def root_health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)
    return app


app = create_app()