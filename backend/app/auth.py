from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKSet, PyJWKSetError
from sqlalchemy import select

from app.config import Settings, get_settings
from app.db import SessionDep
from app.models import User

_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def _get_jwk_client(uri: str) -> PyJWKClient:
    return PyJWKClient(uri)


@lru_cache
def _get_jwk_set(jwks_json: str) -> PyJWKSet:
    return PyJWKSet.from_json(jwks_json)


def _get_signing_key(token: str, settings: Settings):
    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token header",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    kid = header.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token header: missing kid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if settings.cognito_jwks:
        jwk_set = _get_jwk_set(settings.cognito_jwks)
        try:
            return jwk_set[kid].key
        except (KeyError, PyJWKSetError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Signing key not found in JWKS",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
    else:
        jwks_url = f"{settings.cognito_issuer}/.well-known/jwks.json"
        client = _get_jwk_client(jwks_url)
        try:
            signing_key = client.get_signing_key_from_jwt(token)
            return signing_key.key
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to fetch signing key",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc


async def current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Validate Cognito ID token and return or create the matching User."""
    if not settings.auth_configured:
        local_user = session.query(User).filter(User.cognito_sub == "local-mock-user").first()
        if not local_user:
            local_user = User(
                cognito_sub="local-mock-user",
                email="student@example.com",
                name="Local Student",
            )
            session.add(local_user)
            session.commit()
            session.refresh(local_user)
        return local_user

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        key = _get_signing_key(token, settings)
        payload = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=settings.cognito_issuer,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("token_use") != "id":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token use",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("email") or f"{sub}@example.com"
    name = payload.get("name")

    stmt = select(User).where(User.cognito_sub == sub)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            cognito_sub=sub,
            email=email,
            name=name,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
    else:
        updated = False
        if email and user.email != email:
            user.email = email
            updated = True
        if name is not None and user.name != name:
            user.name = name
            updated = True
        if updated:
            await session.flush()
            await session.refresh(user)

    return user


CurrentUser = Annotated[User, Depends(current_user)]

__all__ = ["CurrentUser", "current_user"]
