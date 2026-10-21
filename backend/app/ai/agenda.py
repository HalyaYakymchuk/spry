"""Meeting agenda parser using Amazon Bedrock and Anthropic Claude.

Operates exclusively in eu-north-1 (Stockholm) per project SCP policy.
"""

from datetime import date
import os
from typing import Any

from anthropic import AnthropicBedrock
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import get_settings


class AgendaParseError(Exception):
    """Raised when agenda extraction or validation fails."""

    pass


class AgendaItem(BaseModel):
    topic: str
    owner: str | None = None
    minutes: int | None = None


class ActionItem(BaseModel):
    task: str
    owner: str | None = None
    due: date | None = None

    @field_validator("due", mode="before")
    @classmethod
    def _coerce_empty_due(cls, v: Any) -> Any:
        if v == "":
            return None
        return v


class ParsedAgenda(BaseModel):
    title: str | None = None
    starts_at: str | None = None
    duration_minutes: int | None = None
    items: list[AgendaItem] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    language: str = "en"

    @field_validator("items", mode="before")
    @classmethod
    def _coerce_items(cls, v: Any) -> Any:
        return v if v is not None else []

    @field_validator("action_items", mode="before")
    @classmethod
    def _coerce_action_items(cls, v: Any) -> Any:
        return v if v is not None else []

    @field_validator("language", mode="before")
    @classmethod
    def _coerce_language(cls, v: Any) -> Any:
        return v if v is not None else "en"


RECORD_AGENDA: dict[str, Any] = {
    "name": "record_agenda",
    "description": (
        "Record structured meeting agenda, topics, action items, dates, and metadata."
    ),
    "input_schema": ParsedAgenda.model_json_schema(),
}

PROMPT_VERSION: str = "agenda-v1"

SYSTEM: str = """You are an expert meeting assistant. Analyze pasted text (email, notes, invite, agenda draft, or chat log) and extract structured meeting details.

You must ALWAYS invoke the `record_agenda` tool to return your findings.

Extraction guidelines:
1. title: A concise, descriptive title for the meeting. If explicitly named, use it. If not, infer a concise title (e.g. "Q4 Budget Review"). If no meeting is present, set to null.
2. starts_at: The scheduled start time in ISO 8601 format (e.g., "YYYY-MM-DDTHH:MM:SS" or with timezone offset).
   - Resolve relative dates (e.g., "today", "tomorrow", "this Friday", "next Monday") against the reference date and weekday provided in the user prompt.
   - Use the reference time zone for any time calculations.
   - If no start time or date is mentioned or inferable, set to null.
3. duration_minutes: Total planned meeting duration in minutes as an integer.
   - If start and end times are given (e.g. 10:00 to 11:30), calculate the duration (90).
   - If explicit duration is stated (e.g. "30m", "1 hour"), parse to minutes.
   - If unspecified, set to null.
4. items: List of agenda items or discussion topics:
   - topic: Concise topic description.
   - owner: Person leading or presenting this topic, or null if unassigned.
   - minutes: Planned minutes for this topic, or null if unspecified.
5. action_items: List of actionable follow-ups, tasks, or commitments:
   - task: Clear description of the action.
   - owner: Assignee name, or null if unassigned.
   - due: Due date in ISO 8601 format "YYYY-MM-DD", resolved relative to the reference date, or null.
6. language: Two-letter ISO 639-1 language code (e.g. "en", "uk", "fr"). Default to "en".

Rules:
- Never make up information. If an attribute is unknown or missing, use null (or empty list for items/action_items).
- Always output your result by invoking the `record_agenda` tool.
"""


def resolve_model_id(model_name: str) -> str:
    """Resolve model shorthand or foundation model ID to Bedrock inference profile ID."""
    aliases = {
        "anthropic.claude-haiku-4-5": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        "anthropic.claude-haiku-4-5-20251001-v1:0": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        "anthropic.claude-sonnet-4-5": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "anthropic.claude-sonnet-4-5-20250929-v1:0": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
    }
    return aliases.get(model_name, model_name)


def parse_agenda(
    text: str,
    today: date,
    tz: str,
    *,
    client: AnthropicBedrock | None = None,
    model: str | None = None,
) -> tuple[ParsedAgenda, dict[str, int]]:
    """Parse raw agenda/meeting text into a structured ParsedAgenda object.

    Args:
        text: Raw text to parse (wrapped in <pasted_text>...</pasted_text>).
        today: Reference date for resolving relative dates.
        tz: Reference timezone (e.g. "Europe/Kyiv").
        client: Optional AnthropicBedrock client instance.
        model: Optional Bedrock model ID / inference profile ID.

    Returns:
        tuple[ParsedAgenda, dict]: (Parsed agenda model, token usage dict)

    Raises:
        AgendaParseError: If no tool call occurs or validation fails twice.
    """
    if client is None:
        settings = get_settings()
        region = os.getenv("AWS_REGION", getattr(settings, "aws_region", "eu-north-1"))
        if region == "us-east-1":
            raise AgendaParseError(
                "us-east-1 is blocked by SCP explicit deny policy. Use eu-north-1."
            )
        client = AnthropicBedrock(aws_region=region)

    if model is None:
        settings = get_settings()
        model = os.getenv(
            "PARSER_MODEL",
            getattr(settings, "parser_model", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"),
        )
    model = resolve_model_id(model)

    weekday = today.strftime("%A")
    iso_date = today.isoformat()
    user_prompt = (
        f"Today is {weekday}, {iso_date}. Time zone is {tz}.\n\n"
        f"<pasted_text>\n{text}\n</pasted_text>"
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
    total_input_tokens = 0
    total_output_tokens = 0

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM,
            tools=[RECORD_AGENDA],
            tool_choice={"type": "tool", "name": "record_agenda"},
            messages=messages,
        )
    except Exception as exc:
        raise AgendaParseError(f"Bedrock invocation failed: {exc}") from exc

    if response.usage:
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

    tool_use_block = next(
        (
            b
            for b in response.content
            if getattr(b, "type", None) == "tool_use"
            and getattr(b, "name", None) == "record_agenda"
        ),
        None,
    )
    if tool_use_block is None:
        tool_use_block = next(
            (b for b in response.content if getattr(b, "type", None) == "tool_use"),
            None,
        )

    if tool_use_block is None:
        raise AgendaParseError("Model did not call the required tool 'record_agenda'.")

    try:
        parsed = ParsedAgenda.model_validate(tool_use_block.input)
        return parsed, {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
        }
    except ValidationError as first_validation_err:
        # Append assistant turn and retry user turn with tool_result
        messages.append({"role": "assistant", "content": response.content})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_block.id,
                        "content": (
                            f"Schema validation failed: {first_validation_err}\n"
                            "Please fix the validation error(s) and call the "
                            "'record_agenda' tool again."
                        ),
                        "is_error": True,
                    }
                ],
            }
        )

        try:
            retry_response = client.messages.create(
                model=model,
                max_tokens=2048,
                system=SYSTEM,
                tools=[RECORD_AGENDA],
                tool_choice={"type": "tool", "name": "record_agenda"},
                messages=messages,
            )
        except Exception as retry_exc:
            raise AgendaParseError(
                f"Bedrock retry invocation failed: {retry_exc}"
            ) from retry_exc

        if retry_response.usage:
            total_input_tokens += retry_response.usage.input_tokens
            total_output_tokens += retry_response.usage.output_tokens

        retry_tool_use_block = next(
            (
                b
                for b in retry_response.content
                if getattr(b, "type", None) == "tool_use"
                and getattr(b, "name", None) == "record_agenda"
            ),
            None,
        )
        if retry_tool_use_block is None:
            retry_tool_use_block = next(
                (
                    b
                    for b in retry_response.content
                    if getattr(b, "type", None) == "tool_use"
                ),
                None,
            )

        if retry_tool_use_block is None:
            raise AgendaParseError(
                "Model did not call the required tool 'record_agenda' on retry."
            )

        try:
            parsed = ParsedAgenda.model_validate(retry_tool_use_block.input)
            return parsed, {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            }
        except ValidationError as second_validation_err:
            raise AgendaParseError(
                f"Agenda validation failed twice: {second_validation_err}"
            ) from second_validation_err
