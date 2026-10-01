import json
import os
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.config import get_settings

_KEY_ID = "test-key-id"
_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

_jwk_dict = json.loads(RSAAlgorithm.to_jwk(_PUBLIC_KEY))
_jwk_dict["kid"] = _KEY_ID
_jwk_dict["use"] = "sig"
_jwk_dict["alg"] = "RS256"

# Configure test environment for Cognito verification
os.environ["COGNITO_REGION"] = "us-east-1"
os.environ["COGNITO_USER_POOL_ID"] = "test-pool"
os.environ["COGNITO_CLIENT_ID"] = "test-client"
os.environ["COGNITO_JWKS"] = json.dumps({"keys": [_jwk_dict]})

get_settings.cache_clear()


def make_token(sub: str, email: str, name: str | None = None) -> str:
    """Generate a valid Cognito ID token signed with the test RSA key."""
    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "iss": settings.cognito_issuer,
        "aud": settings.cognito_client_id,
        "token_use": "id",
        "iat": now,
        "exp": now + 3600,
    }
    if name is not None:
        payload["name"] = name
    return jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256", headers={"kid": _KEY_ID})


def auth(
    sub: str = "alice-sub", email: str = "alice@example.com", name: str = "Alice"
) -> dict[str, str]:
    """Return an Authorization header for tests."""
    return {"Authorization": f"Bearer {make_token(sub, email, name)}"}
