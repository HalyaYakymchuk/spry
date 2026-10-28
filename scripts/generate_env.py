#!/usr/bin/env python3
"""
Update or populate the project .env file using values from Terraform outputs.
Reads non-sensitive configuration values directly from `terraform -chdir=infra output -raw <output_name>`.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE_PATH = ROOT / ".env.example"
INFRA_DIR = ROOT / "infra"

# Map of .env variable names to Terraform output names
OUTPUT_MAPPINGS = {
    "COGNITO_USER_POOL_ID": "user_pool_id",
    "COGNITO_CLIENT_ID": "user_pool_client_id",
    "COGNITO_DOMAIN": "cognito_domain",
    "COGNITO_DOMAIN_PREFIX": "cognito_domain_prefix",
    "REPORTS_BUCKET_NAME": "reports_bucket_name",
    "REPORTS_BUCKET_ARN": "reports_bucket_arn",
    "REPORT_REQUESTS_QUEUE_URL": "report_requests_queue_url",
    "REPORT_REQUESTS_QUEUE_ARN": "report_requests_queue_arn",
    "PARSER_FUNCTION_URL": "parser_function_url",
    "NEXT_PUBLIC_PARSER_URL": "parser_function_url",
}


def get_tf_output(name: str) -> str:
    try:
        res = subprocess.run(
            ["terraform", f"-chdir={INFRA_DIR}", "output", "-raw", name],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception as e:
        print(f"Warning: could not resolve terraform output '{name}': {e}", file=sys.stderr)
        return ""


def main():
    if not ENV_PATH.exists() and ENV_EXAMPLE_PATH.exists():
        ENV_PATH.write_text(ENV_EXAMPLE_PATH.read_text(encoding="utf-8"))
        print(f"Created {ENV_PATH} from {ENV_EXAMPLE_PATH}")

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []

    updated_keys = set()
    for env_key, output_name in OUTPUT_MAPPINGS.items():
        val = get_tf_output(output_name)
        if not val:
            continue

        pattern = re.compile(rf"^{re.escape(env_key)}=")
        matched = False
        for i, line in enumerate(lines):
            if pattern.match(line):
                lines[i] = f"{env_key}={val}"
                matched = True
                break
        if not matched:
            lines.append(f"{env_key}={val}")
        updated_keys.add(env_key)
        print(f"  [OK] {env_key}={val}")

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Successfully synced {len(updated_keys)} configuration values into {ENV_PATH.name}")


if __name__ == "__main__":
    main()
