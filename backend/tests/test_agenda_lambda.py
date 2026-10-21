"""Unit tests for Agenda Lambda handler, Cognito JWT auth, and Bedrock cost utility."""

import base64
from datetime import date, datetime, timedelta, timezone
import json
import time
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pytest

from app.ai.agenda import AgendaParseError, ParsedAgenda
from app.ai.agenda_lambda import handler
from app.ai.auth import (
    TokenMissingError,
    TokenValidationError,
    clear_jwks_cache,
    get_bearer_token,
    verify_cognito_token,
)
from app.ai.cost import cost_usd


# --- Fixtures for RSA Keys and Cognito Mock Tokens ---

@pytest.fixture(scope="module")
def rsa_keypair():
    """Generate a 2048-bit RSA keypair for JWT signing tests."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()

    def _int_to_b64(val: int) -> str:
        val_bytes = val.to_bytes((val.bit_length() + 7) // 8, byteorder="big")
        return base64.urlsafe_b64encode(val_bytes).decode("ascii").rstrip("=")

    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": "test-key-id-1",
        "n": _int_to_b64(public_numbers.n),
        "e": _int_to_b64(public_numbers.e),
    }
    return private_key, jwk


@pytest.fixture(autouse=True)
def setup_env(monkeypatch, rsa_keypair):
    """Set up environment variables for testing."""
    _, jwk = rsa_keypair
    monkeypatch.setenv("AWS_REGION", "eu-north-1")
    monkeypatch.setenv("COGNITO_REGION", "eu-north-1")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "eu-north-1_testPool")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "testclient123")
    monkeypatch.setenv(
        "PARSER_MODEL", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    )
    monkeypatch.setenv("COGNITO_JWKS", json.dumps({"keys": [jwk]}))
    clear_jwks_cache()


def create_test_token(
    private_key,
    kid: str = "test-key-id-1",
    sub: str = "user-sub-abc-123",
    issuer: str = "https://cognito-idp.eu-north-1.amazonaws.com/eu-north-1_testPool",
    aud: str = "testclient123",
    expires_in_seconds: int = 3600,
    token_use: str = "id",
) -> str:
    """Helper to generate signed test Cognito JWTs."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "iss": issuer,
        "aud": aud,
        "token_use": token_use,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


# --- 1. Cost Utility Tests ---

def test_cost_usd_haiku_pricing():
    # Haiku: $0.80 / 1M input, $4.00 / 1M output
    usage = {"input_tokens": 1000, "output_tokens": 500}
    # (1000 * 0.80 + 500 * 4.00) / 1_000_000 = (800 + 2000) / 1_000_000 = 0.0028
    cost = cost_usd("eu.anthropic.claude-haiku-4-5-20251001-v1:0", usage)
    assert cost == 0.0028

    # Small token usage (e.g. typical agenda parse: 250 in, 110 out)
    # (250 * 0.8 + 110 * 4.0) / 1M = (200 + 440) / 1M = 640 / 1M = 0.00064
    usage_small = {"input_tokens": 250, "output_tokens": 110}
    assert cost_usd("claude-haiku-4-5", usage_small) == 0.00064


def test_cost_usd_sonnet_pricing():
    # Sonnet: $3.00 / 1M input, $15.00 / 1M output
    usage = {"input_tokens": 1000, "output_tokens": 1000}
    # (1000 * 3.00 + 1000 * 15.00) / 1_000_000 = 18000 / 1_000_000 = 0.018
    cost = cost_usd("eu.anthropic.claude-sonnet-4-5-20250929-v1:0", usage)
    assert cost == 0.018


def test_cost_usd_zero_and_empty():
    assert cost_usd("any-model", None) == 0.0
    assert cost_usd("any-model", {}) == 0.0
    assert cost_usd("any-model", {"input_tokens": 0, "output_tokens": 0}) == 0.0


# --- 2. Auth Tests ---

def test_get_bearer_token_success():
    headers = {"Authorization": "Bearer my_secret_token"}
    assert get_bearer_token(headers) == "my_secret_token"

    # Case-insensitivity check
    headers_lower = {"authorization": "Bearer my_lower_token"}
    assert get_bearer_token(headers_lower) == "my_lower_token"


def test_get_bearer_token_missing_and_invalid():
    with pytest.raises(TokenMissingError, match="Missing Authorization header"):
        get_bearer_token({})

    with pytest.raises(TokenMissingError, match="Missing Authorization header"):
        get_bearer_token({"other": "header"})

    with pytest.raises(TokenMissingError, match="Invalid Authorization header"):
        get_bearer_token({"Authorization": "Basic 12345"})

    with pytest.raises(TokenMissingError, match="Invalid Authorization header"):
        get_bearer_token({"Authorization": "Bearer"})


def test_verify_cognito_token_success(rsa_keypair):
    private_key, _ = rsa_keypair
    token = create_test_token(private_key, sub="test-sub-1234")
    claims = verify_cognito_token(token)
    assert claims["sub"] == "test-sub-1234"
    assert claims["aud"] == "testclient123"


def test_verify_cognito_token_expired(rsa_keypair):
    private_key, _ = rsa_keypair
    token = create_test_token(private_key, expires_in_seconds=-120)
    with pytest.raises(TokenValidationError, match="Token has expired"):
        verify_cognito_token(token)


def test_verify_cognito_token_invalid_issuer(rsa_keypair):
    private_key, _ = rsa_keypair
    token = create_test_token(private_key, issuer="https://evil-issuer.com")
    with pytest.raises(TokenValidationError, match="Invalid token issuer"):
        verify_cognito_token(token)


def test_verify_cognito_token_invalid_audience(rsa_keypair):
    private_key, _ = rsa_keypair
    token = create_test_token(private_key, aud="wrong-client-id")
    with pytest.raises(TokenValidationError, match="does not match"):
        verify_cognito_token(token)


def test_verify_cognito_token_unknown_kid(rsa_keypair):
    private_key, _ = rsa_keypair
    token = create_test_token(private_key, kid="unknown-kid")
    with pytest.raises(TokenValidationError, match="not found in JWKS"):
        verify_cognito_token(token)


# --- 3. Agenda Lambda Handler Tests ---

def test_lambda_options_cors_preflight():
    event = {
        "requestContext": {"http": {"method": "OPTIONS"}},
        "headers": {"origin": "http://localhost:3000"},
    }
    resp = handler(event)
    assert resp["statusCode"] == 200
    assert resp["headers"]["Content-Type"] == "application/json"
    assert resp["body"] == ""


def test_lambda_unauthorized_missing_token():
    event = {
        "headers": {},
        "body": json.dumps({"text": "Test", "today": "2026-10-21", "tz": "UTC"}),
    }
    resp = handler(event)
    assert resp["statusCode"] == 401
    body = json.loads(resp["body"])
    assert "Missing Authorization header" in body["error"]


def test_lambda_unauthorized_expired_token(rsa_keypair):
    private_key, _ = rsa_keypair
    token = create_test_token(private_key, expires_in_seconds=-60)
    event = {
        "headers": {"authorization": f"Bearer {token}"},
        "body": json.dumps({"text": "Test", "today": "2026-10-21", "tz": "UTC"}),
    }
    resp = handler(event)
    assert resp["statusCode"] == 401
    body = json.loads(resp["body"])
    assert "expired" in body["error"].lower()


def test_lambda_oversized_text_413(rsa_keypair):
    private_key, _ = rsa_keypair
    token = create_test_token(private_key)
    huge_text = "A" * 10001
    event = {
        "headers": {"authorization": f"Bearer {token}"},
        "body": json.dumps(
            {"text": huge_text, "today": "2026-10-21", "tz": "UTC"}
        ),
    }
    resp = handler(event)
    assert resp["statusCode"] == 413
    body = json.loads(resp["body"])
    assert body["error"] == "Text exceeds maximum length of 10,000 characters"


def test_lambda_missing_fields_400(rsa_keypair):
    private_key, _ = rsa_keypair
    token = create_test_token(private_key)

    # Missing today
    event1 = {
        "headers": {"authorization": f"Bearer {token}"},
        "body": json.dumps({"text": "Meeting", "tz": "Europe/Kyiv"}),
    }
    resp1 = handler(event1)
    assert resp1["statusCode"] == 400
    assert "Missing required field: today" in json.loads(resp1["body"])["error"]

    # Missing tz
    event2 = {
        "headers": {"authorization": f"Bearer {token}"},
        "body": json.dumps({"text": "Meeting", "today": "2026-10-21"}),
    }
    resp2 = handler(event2)
    assert resp2["statusCode"] == 400
    assert "Missing required field: tz" in json.loads(resp2["body"])["error"]

    # Invalid date
    event3 = {
        "headers": {"authorization": f"Bearer {token}"},
        "body": json.dumps(
            {"text": "Meeting", "today": "not-a-date", "tz": "Europe/Kyiv"}
        ),
    }
    resp3 = handler(event3)
    assert resp3["statusCode"] == 400
    assert "Invalid ISO date format" in json.loads(resp3["body"])["error"]


def test_lambda_agenda_parse_error_422(rsa_keypair):
    private_key, _ = rsa_keypair
    token = create_test_token(private_key)

    event = {
        "headers": {"authorization": f"Bearer {token}"},
        "body": json.dumps(
            {
                "text": "Hello world with no meeting details",
                "today": "2026-10-21",
                "tz": "Europe/Kyiv",
            }
        ),
    }

    with patch(
        "app.ai.agenda_lambda.parse_agenda",
        side_effect=AgendaParseError("Model failed to extract agenda"),
    ):
        resp = handler(event)

    assert resp["statusCode"] == 422
    body = json.loads(resp["body"])
    assert body["error"] == "Model failed to extract agenda"


def test_lambda_success_and_cloudwatch_log(rsa_keypair, capsys):
    private_key, _ = rsa_keypair
    token = create_test_token(private_key, sub="cognito-user-456")

    mock_agenda = ParsedAgenda(
        title="Sprint Planning",
        starts_at="2026-10-22T09:00:00",
        duration_minutes=45,
        items=[],
        action_items=[],
        language="en",
    )
    mock_usage = {"input_tokens": 120, "output_tokens": 80}

    event = {
        "requestContext": {"http": {"method": "POST"}},
        "headers": {
            "origin": "https://d2l89vyn3q02js.cloudfront.net",
            "authorization": f"Bearer {token}",
        },
        "body": json.dumps(
            {
                "text": "Sprint planning tomorrow at 9am for 45m.",
                "today": "2026-10-21",
                "tz": "Europe/Kyiv",
            }
        ),
    }

    with patch(
        "app.ai.agenda_lambda.parse_agenda",
        return_value=(mock_agenda, mock_usage),
    ):
        resp = handler(event)

    assert resp["statusCode"] == 200
    assert resp["headers"]["Content-Type"] == "application/json"
    assert "Access-Control-Allow-Origin" not in resp["headers"]

    payload = json.loads(resp["body"])
    assert payload["agenda"]["title"] == "Sprint Planning"
    assert payload["agenda"]["duration_minutes"] == 45
    assert payload["model"] == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert payload["prompt_version"] == "agenda-v1"

    # Verify structured CloudWatch log line on stdout
    captured = capsys.readouterr()
    log_line = next(
        (
            line
            for line in captured.out.strip().split("\n")
            if '"event": "agenda_parsed"' in line
        ),
        None,
    )
    assert log_line is not None, f"Expected agenda_parsed in stdout, got: {captured.out}"
    parsed_log = json.loads(log_line)
    assert parsed_log["event"] == "agenda_parsed"
    assert parsed_log["user"] == "cognito-user-456"
    assert parsed_log["model"] == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert parsed_log["prompt_version"] == "agenda-v1"
    assert parsed_log["input_tokens"] == 120
    assert parsed_log["output_tokens"] == 80
    assert "latency_ms" in parsed_log
    assert "cost_usd" in parsed_log
    # (120 * 0.8 + 80 * 4.0) / 1M = 0.000416
    assert parsed_log["cost_usd"] == 0.000416
