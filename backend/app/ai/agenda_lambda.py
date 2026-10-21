"""AWS Lambda handler for agenda parsing behind Lambda Function URL.

Operates in eu-north-1 outside VPC, with manual Cognito JWT verification.
"""

import base64
from datetime import date
import json
import logging
import os
import time
from typing import Any

from app.ai.agenda import (
    PROMPT_VERSION,
    AgendaParseError,
    parse_agenda,
    resolve_model_id,
)
from app.ai.auth import AuthError, authenticate_request
from app.ai.cost import cost_usd
from app.config import get_settings

logger = logging.getLogger(__name__)
if not logger.handlers and not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _response(
    status_code: int,
    body: dict[str, Any] | str,
) -> dict[str, Any]:
    """Build API Gateway / Lambda Function URL response dict.

    CORS headers are handled exclusively by the Lambda Function URL configuration.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "isBase64Encoded": False,
        "body": json.dumps(body) if isinstance(body, dict) else body,
    }


def handler(
    event: dict[str, Any] | None = None,
    context: Any = None,
    *,
    client: Any = None,
) -> dict[str, Any]:
    """Lambda entry point for agenda parsing."""
    event = event or {}
    headers = event.get("headers") or {}

    # 1. Handle CORS preflight (OPTIONS -> 200)
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "POST"
    ).upper()

    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "isBase64Encoded": False,
            "body": "",
        }

    # 2. Extract and verify Cognito JWT from Authorization header -> 401 on failure
    try:
        user_claims = authenticate_request(headers)
        user_sub = user_claims.get("sub", "unknown")
    except AuthError as auth_err:
        logger.warning("Cognito authentication failed: %s", auth_err)
        return _response(401, {"error": str(auth_err)})

    # 3. Parse JSON body
    raw_body = event.get("body")
    if raw_body is None:
        if "text" in event or "today" in event:
            body = event
        else:
            return _response(400, {"error": "Missing request body"})
    elif isinstance(raw_body, dict):
        body = raw_body
    elif isinstance(raw_body, str):
        if event.get("isBase64Encoded"):
            try:
                raw_body = base64.b64decode(raw_body).decode("utf-8")
            except Exception as dec_err:
                return _response(
                    400,
                    {"error": f"Base64 decoding failed: {dec_err}"},
                )
        try:
            body = json.loads(raw_body)
        except Exception:
            return _response(400, {"error": "Invalid JSON body"})
    else:
        body = {}

    if not isinstance(body, dict):
        return _response(400, {"error": "Request body must be a JSON object"})

    # 4. Check text length > 10000 -> HTTP 413
    raw_text = body.get("text")
    if raw_text is not None and len(str(raw_text)) > 10000:
        return _response(
            413,
            {"error": "Text exceeds maximum length of 10,000 characters"},
        )

    # 5. Validate presence of text, today, and tz
    if raw_text is None or not str(raw_text).strip():
        return _response(400, {"error": "Missing required field: text"})

    if "today" not in body or not body.get("today"):
        return _response(400, {"error": "Missing required field: today"})

    if "tz" not in body or not body.get("tz"):
        return _response(400, {"error": "Missing required field: tz"})

    try:
        today_date = date.fromisoformat(str(body["today"]))
    except ValueError as val_err:
        return _response(
            400,
            {"error": f"Invalid ISO date format for 'today': {val_err}"},
        )

    tz_str = str(body["tz"])

    # 6. Model resolution
    settings = get_settings()
    raw_model = os.getenv(
        "PARSER_MODEL",
        getattr(settings, "parser_model", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"),
    )
    model_id = resolve_model_id(raw_model)

    # 7. Invoke parse_agenda and measure latency
    start_time = time.perf_counter()
    try:
        agenda, usage = parse_agenda(
            text=str(raw_text),
            today=today_date,
            tz=tz_str,
            client=client,
            model=model_id,
        )
    except AgendaParseError as parse_err:
        logger.warning("AgendaParseError during invocation: %s", parse_err)
        return _response(422, {"error": str(parse_err)})
    except Exception as exc:
        logger.exception("Unexpected error in agenda parser: %s", exc)
        return _response(500, {"error": f"Internal server error: {exc}"})

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # 8. Calculate token costs and print structured CloudWatch log line
    in_tokens = int(usage.get("input_tokens") or 0)
    out_tokens = int(usage.get("output_tokens") or 0)
    cost = cost_usd(model_id, usage)

    cloudwatch_log = {
        "event": "agenda_parsed",
        "user": user_sub,
        "model": model_id,
        "prompt_version": PROMPT_VERSION,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "latency_ms": latency_ms,
        "cost_usd": cost,
    }
    # Print single-line JSON log for CloudWatch Logs Insights
    print(json.dumps(cloudwatch_log), flush=True)

    # 9. Return HTTP 200 with JSON payload (Function URL applies CORS)
    return _response(
        200,
        {
            "agenda": agenda.model_dump(mode="json"),
            "model": model_id,
            "prompt_version": PROMPT_VERSION,
        },
    )
