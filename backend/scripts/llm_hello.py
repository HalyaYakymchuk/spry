"""Quick verification script for Amazon Bedrock Anthropic Claude connectivity.

Operates exclusively in eu-north-1 (Stockholm) per project SCP policy.
"""

import os
import sys

# Ensure UTF-8 output on Windows / MSYS2 terminals to support emojis
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from anthropic import AnthropicBedrock, BadRequestError, NotFoundError


def resolve_model_id(model_name: str) -> str:
    """Resolve model shorthand or foundation model ID to Bedrock inference profile ID."""
    aliases = {
        "anthropic.claude-haiku-4-5": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        "anthropic.claude-haiku-4-5-20251001-v1:0": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        "anthropic.claude-sonnet-4-5": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "anthropic.claude-sonnet-4-5-20250929-v1:0": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
    }
    return aliases.get(model_name, model_name)


def main() -> int:
    region = os.getenv("AWS_REGION", "eu-north-1")
    raw_model = os.getenv("PARSER_MODEL", "eu.anthropic.claude-haiku-4-5-20251001-v1:0")

    # Strict SCP constraint check
    if region == "us-east-1":
        print(
            "CRITICAL: us-east-1 is blocked by SCP explicit deny policy. "
            "Please use eu-north-1.",
            file=sys.stderr,
        )
        return 1

    model_id = resolve_model_id(raw_model)

    print("=" * 60)
    print("Amazon Bedrock - Anthropic Claude Verification")
    print("=" * 60)
    print(f"Target Region    : {region}")
    print(f"Requested Model  : {raw_model}")
    if model_id != raw_model:
        print(f"Inference Profile: {model_id}")
    print("=" * 60)

    prompt = "Hello! Confirm that Amazon Bedrock connectivity to Anthropic Claude is operational in eu-north-1. Respond in one sentence."

    try:
        client = AnthropicBedrock(aws_region=region)
        print(f"Sending prompt: {prompt!r} ...\n")
        response = client.messages.create(
            model=model_id,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )

        print("-" * 60)
        print("Bedrock Response:")
        print("-" * 60)
        for block in response.content:
            if block.type == "text":
                print(block.text.strip())

        print("\n" + "-" * 60)
        print(
            f"Usage: input_tokens={response.usage.input_tokens}, "
            f"output_tokens={response.usage.output_tokens}"
        )
        print("-" * 60)
        print("Status: SUCCESS (Bedrock Claude invocation verified)")
        return 0

    except NotFoundError as err:
        print(f"\n[Bedrock NotFoundError]: {err}", file=sys.stderr)
        if "use case details" in str(err).lower():
            print(
                "\nNOTE: The Anthropic use case details have been submitted. "
                "AWS Bedrock typically requires ~15 minutes to propagate access approval.",
                file=sys.stderr,
            )
        return 1
    except BadRequestError as err:
        print(f"\n[Bedrock BadRequestError]: {err}", file=sys.stderr)
        if "on-demand throughput isn't supported" in str(err).lower():
            print(
                "\nNOTE: Anthropic models in eu-north-1 require a regional inference profile "
                "(e.g., 'eu.anthropic.claude-haiku-4-5-20251001-v1:0').",
                file=sys.stderr,
            )
        return 1
    except Exception as err:
        print(f"\n[Error]: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
