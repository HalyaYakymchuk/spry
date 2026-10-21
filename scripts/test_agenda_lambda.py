#!/usr/bin/env python3
"""Testing helper for the Agenda Parser Lambda function and Function URL.

Tests:
1. HTTP 401 on missing/invalid Authorization header.
2. HTTP 413 on oversized text (> 10,000 characters).
3. HTTP 200 with structured agenda output on valid request with Cognito ID token.
"""

import argparse
from datetime import date
import json
import os
import sys
import urllib.error
import urllib.request

# Ensure root and backend directory are in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
backend_dir = os.path.join(root_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import boto3
from dotenv import load_dotenv

# Load .env if present
load_dotenv(os.path.join(root_dir, ".env"))


def get_cognito_id_token(
    user_pool_id: str,
    client_id: str,
    region: str = "eu-north-1",
    email: str = "test-runner@spry.org.ua",
    password: str = "TestPassword123!",
) -> str:
    """Fetch or generate a valid Cognito ID token for testing."""
    client = boto3.client("cognito-idp", region_name=region)

    # 1. Ensure test user exists with confirmed permanent password
    try:
        client.admin_get_user(UserPoolId=user_pool_id, Username=email)
    except client.exceptions.UserNotFoundException:
        print(f"Creating test user '{email}' in user pool {user_pool_id}...")
        client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            MessageAction="SUPPRESS",
        )

    # Ensure password is permanently confirmed
    client.admin_set_user_password(
        UserPoolId=user_pool_id,
        Username=email,
        Password=password,
        Permanent=True,
    )

    # 2. Authenticate to obtain ID token
    try:
        res = client.admin_initiate_auth(
            UserPoolId=user_pool_id,
            ClientId=client_id,
            AuthFlow="ADMIN_NO_SRP_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
        return res["AuthenticationResult"]["IdToken"]
    except Exception as exc:
        # Fallback to USER_PASSWORD_AUTH
        res = client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
        return res["AuthenticationResult"]["IdToken"]


def resolve_function_url(region: str = "eu-north-1", project_name: str = "peach") -> str:
    """Resolve the Lambda Function URL from environment or CloudFormation stack."""
    url = os.getenv("PARSER_FUNCTION_URL") or os.getenv("NEXT_PUBLIC_PARSER_URL")
    if url:
        return url.strip()

    cf = boto3.client("cloudformation", region_name=region)
    stack_name = f"{project_name}-parser"
    try:
        res = cf.describe_stacks(StackName=stack_name)
        outputs = res["Stacks"][0].get("Outputs", [])
        for out in outputs:
            if out.get("OutputKey") == "ParserFunctionUrl":
                return out["OutputValue"].strip()
    except Exception:
        pass

    return ""


def run_http_request(
    url: str,
    method: str = "POST",
    headers: dict[str, str] | None = None,
    payload: dict | None = None,
) -> tuple[int, dict, dict[str, str]]:
    """Execute HTTP request against Function URL and return (status_code, body_dict, headers)."""
    headers = headers or {}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=35) as res:
            status = res.status
            resp_headers = dict(res.headers)
            body_str = res.read().decode("utf-8")
            body_dict = json.loads(body_str) if body_str else {}
            return status, body_dict, resp_headers
    except urllib.error.HTTPError as err:
        status = err.code
        resp_headers = dict(err.headers)
        body_str = err.read().decode("utf-8")
        try:
            body_dict = json.loads(body_str) if body_str else {}
        except Exception:
            body_dict = {"raw": body_str}
        return status, body_dict, resp_headers


def run_remote_tests(url: str, id_token: str) -> bool:
    """Run verification tests against deployed Lambda Function URL."""
    print("=" * 70)
    print("Agenda Parser Function URL - Verification Test Suite")
    print("=" * 70)
    print(f"Target URL: {url}")
    print(f"Token (preview): {id_token[:25]}... (length: {len(id_token)})")
    print("=" * 70)

    all_passed = True

    # --- Test 1: Missing Token -> 401 ---
    print("\n[Test 1] Invoking without Authorization header (expecting HTTP 401)...")
    status, body, _ = run_http_request(
        url,
        method="POST",
        headers={"Content-Type": "application/json"},
        payload={
            "text": "Meeting tomorrow at 10am to discuss project budget.",
            "today": date.today().isoformat(),
            "tz": "Europe/Kyiv",
        },
    )
    if status == 401 and "error" in body:
        print(f"  PASS: Received HTTP 401 Unauthorized. Error: {body['error']}")
    else:
        print(f"  FAIL: Expected HTTP 401, got {status}. Response: {body}")
        all_passed = False

    # --- Test 2: Oversized Text (> 10,000 chars) -> 413 ---
    print("\n[Test 2] Invoking with text > 10,000 characters (expecting HTTP 413)...")
    oversized_text = "A" * 10005
    status, body, _ = run_http_request(
        url,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {id_token}",
        },
        payload={
            "text": oversized_text,
            "today": date.today().isoformat(),
            "tz": "Europe/Kyiv",
        },
    )
    if (
        status == 413
        and body.get("error") == "Text exceeds maximum length of 10,000 characters"
    ):
        print(f"  PASS: Received HTTP 413 Payload Too Large. Error: {body['error']}")
    else:
        print(f"  FAIL: Expected HTTP 413 with exact message, got {status}. Response: {body}")
        all_passed = False

    # --- Test 3: Valid Request with Token -> 200 ---
    print("\n[Test 3] Invoking with valid agenda text and Bearer token (expecting HTTP 200)...")
    valid_text = (
        "Sprint planning tomorrow at 11:00 for 45 minutes. "
        "Discuss Q4 deliverables. Action: Sarah to send sheet by Friday."
    )
    status, body, _ = run_http_request(
        url,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {id_token}",
        },
        payload={
            "text": valid_text,
            "today": date.today().isoformat(),
            "tz": "Europe/Kyiv",
        },
    )
    if status == 200 and "agenda" in body and "model" in body and "prompt_version" in body:
        agenda = body["agenda"]
        print(f"  PASS: Received HTTP 200 OK.")
        print(f"  Extracted Title: {agenda.get('title')}")
        print(f"  Duration (min) : {agenda.get('duration_minutes')}")
        print(f"  Action Items   : {len(agenda.get('action_items', []))}")
        print(f"  Model Used     : {body.get('model')}")
        print(f"  Prompt Version : {body.get('prompt_version')}")
    else:
        print(f"  FAIL: Expected HTTP 200, got {status}. Response: {body}")
        all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("ALL TESTS PASSED! Lambda function URL is fully operational.")
    else:
        print("SOME TESTS FAILED! Check logs above for details.")
    print("=" * 70)

    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test Agenda Parser Lambda function and Function URL."
    )
    parser.add_argument("--url", help="Deployed Function URL to test.")
    parser.add_argument("--token", help="Cognito ID token (optional, auto-generated if omitted).")
    parser.add_argument("--region", default="eu-north-1", help="AWS region (default: eu-north-1).")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run tests locally directly against the Python handler.",
    )

    args = parser.parse_args()

    region = os.getenv("AWS_REGION", args.region)
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID", "eu-north-1_tJwOveqnV")
    client_id = os.getenv("COGNITO_CLIENT_ID", "7qrffcg5chk6nio4ml189gio8")
    project_name = os.getenv("PROJECT_NAME", "peach")

    token = args.token or os.getenv("COGNITO_ID_TOKEN")
    if not token:
        print("Fetching fresh Cognito ID token...")
        try:
            token = get_cognito_id_token(
                user_pool_id=user_pool_id,
                client_id=client_id,
                region=region,
            )
            print("Successfully acquired Cognito ID token.")
        except Exception as exc:
            print(f"Failed to acquire Cognito ID token automatically: {exc}", file=sys.stderr)
            print("Pass an ID token via --token or set COGNITO_ID_TOKEN.", file=sys.stderr)
            return 1

    if args.local:
        # Run local test using the actual handler and Bedrock in eu-north-1
        from app.ai.agenda_lambda import handler

        print("Running local handler test...")
        # Test 401
        resp_401 = handler({"headers": {}, "body": json.dumps({"text": "hi", "today": "2026-10-21", "tz": "UTC"})})
        assert resp_401["statusCode"] == 401, f"Expected 401, got {resp_401['statusCode']}"
        print("Local Test 1 (401 Missing Token): PASS")

        # Test 413
        resp_413 = handler(
            {
                "headers": {"authorization": f"Bearer {token}"},
                "body": json.dumps({"text": "A" * 10005, "today": "2026-10-21", "tz": "UTC"}),
            }
        )
        assert resp_413["statusCode"] == 413, f"Expected 413, got {resp_413['statusCode']}"
        print("Local Test 2 (413 Oversized Text): PASS")

        # Test 200
        resp_200 = handler(
            {
                "headers": {"authorization": f"Bearer {token}"},
                "body": json.dumps(
                    {
                        "text": "Team sync tomorrow at 10am for 30m.",
                        "today": "2026-10-21",
                        "tz": "Europe/Kyiv",
                    }
                ),
            }
        )
        assert resp_200["statusCode"] == 200, f"Expected 200, got {resp_200['statusCode']}"
        print("Local Test 3 (200 Valid Agenda): PASS")
        print("All local handler tests passed!")
        return 0

    url = args.url or resolve_function_url(region=region, project_name=project_name)
    if not url:
        print(
            "Error: Function URL not found. Specify --url or set PARSER_FUNCTION_URL in .env, "
            "or use --local to test handler directly.",
            file=sys.stderr,
        )
        return 1

    success = run_remote_tests(url=url, id_token=token)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
