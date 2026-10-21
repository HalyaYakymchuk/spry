"""Cost calculation utility for Amazon Bedrock Anthropic Claude models.

Pricing rates per 1,000,000 tokens (USD):
- Claude Haiku 4.5: $0.80 / 1M input, $4.00 / 1M output
- Claude Sonnet 4.5: $3.00 / 1M input, $15.00 / 1M output
"""

from typing import Any

# Pricing per 1,000,000 tokens in USD
MODEL_PRICING: dict[str, dict[str, float]] = {
    # Claude Haiku 4.5 and aliases
    "haiku": {"input": 0.80, "output": 4.00},
    "claude-haiku": {"input": 0.80, "output": 4.00},
    "eu.anthropic.claude-haiku-4-5-20251001-v1:0": {"input": 0.80, "output": 4.00},
    "anthropic.claude-haiku-4-5-20251001-v1:0": {"input": 0.80, "output": 4.00},
    # Claude Sonnet 4.5 and aliases
    "sonnet": {"input": 3.00, "output": 15.00},
    "claude-sonnet": {"input": 3.00, "output": 15.00},
    "eu.anthropic.claude-sonnet-4-5-20250929-v1:0": {"input": 3.00, "output": 15.00},
    "anthropic.claude-sonnet-4-5-20250929-v1:0": {"input": 3.00, "output": 15.00},
}

DEFAULT_INPUT_RATE_PER_1M = 0.80
DEFAULT_OUTPUT_RATE_PER_1M = 4.00


def cost_usd(model_id: str, usage: dict[str, Any] | None) -> float:
    """Compute dollar cost from input/output tokens based on Bedrock model pricing.

    Args:
        model_id: Bedrock model ID or alias.
        usage: Dict containing 'input_tokens' and 'output_tokens'.

    Returns:
        float: Calculated USD cost rounded to 6 decimal places.
    """
    if not usage:
        return 0.0

    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)

    model_lower = (model_id or "").lower()
    rates = None
    for key, price in MODEL_PRICING.items():
        if key in model_lower:
            rates = price
            break

    if rates:
        in_rate = rates["input"]
        out_rate = rates["output"]
    else:
        in_rate = DEFAULT_INPUT_RATE_PER_1M
        out_rate = DEFAULT_OUTPUT_RATE_PER_1M

    total_cost = (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000.0
    return round(total_cost, 6)
