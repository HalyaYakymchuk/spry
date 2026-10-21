from datetime import date
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.ai.agenda import (
    PROMPT_VERSION,
    RECORD_AGENDA,
    SYSTEM,
    ActionItem,
    AgendaItem,
    AgendaParseError,
    ParsedAgenda,
    parse_agenda,
    resolve_model_id,
)


def test_agenda_item_schema():
    item = AgendaItem(topic="Q4 Budget", owner="John", minutes=30)
    assert item.topic == "Q4 Budget"
    assert item.owner == "John"
    assert item.minutes == 30

    item_minimal = AgendaItem(topic="Standup")
    assert item_minimal.topic == "Standup"
    assert item_minimal.owner is None
    assert item_minimal.minutes is None


def test_action_item_schema():
    action = ActionItem(task="Send slides", owner="Sarah", due=date(2026, 10, 23))
    assert action.task == "Send slides"
    assert action.owner == "Sarah"
    assert action.due == date(2026, 10, 23)

    # Empty string should coerce to None
    action_empty_due = ActionItem.model_validate({"task": "Follow up", "due": ""})
    assert action_empty_due.due is None

    # Invalid string should raise ValidationError
    with pytest.raises(ValidationError):
        ActionItem.model_validate({"task": "Follow up", "due": "not-a-date"})


def test_parsed_agenda_schema():
    agenda = ParsedAgenda(
        title="Weekly Sync",
        starts_at="2026-10-22T10:00:00",
        duration_minutes=60,
        items=[AgendaItem(topic="Roadmap", owner="Alice", minutes=30)],
        action_items=[ActionItem(task="Update Jira", owner="Bob", due=date(2026, 10, 25))],
        language="en",
    )
    assert agenda.title == "Weekly Sync"
    assert len(agenda.items) == 1
    assert len(agenda.action_items) == 1
    assert agenda.language == "en"

    # None for items/action_items should coerce to empty list
    agenda_nulls = ParsedAgenda.model_validate(
        {"title": "Test", "items": None, "action_items": None, "language": None}
    )
    assert agenda_nulls.items == []
    assert agenda_nulls.action_items == []
    assert agenda_nulls.language == "en"


def test_record_agenda_tool_schema():
    assert RECORD_AGENDA["name"] == "record_agenda"
    assert "input_schema" in RECORD_AGENDA
    schema = RECORD_AGENDA["input_schema"]
    assert "properties" in schema
    assert "items" in schema["properties"]
    assert "action_items" in schema["properties"]


def test_prompt_version():
    assert PROMPT_VERSION == "agenda-v1"
    assert "record_agenda" in SYSTEM


def test_resolve_model_id():
    assert (
        resolve_model_id("anthropic.claude-haiku-4-5")
        == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    )
    assert (
        resolve_model_id("custom-model-id")
        == "custom-model-id"
    )


def test_parse_agenda_success_first_attempt():
    mock_client = MagicMock()
    mock_usage = MagicMock(input_tokens=120, output_tokens=80)
    mock_tool_block = MagicMock(
        type="tool_use",
        id="tool_123",
        name="record_agenda",
        input={
            "title": "Budget Meeting",
            "starts_at": "2026-10-22T10:00:00",
            "duration_minutes": 30,
            "items": [{"topic": "Budget Review", "owner": "John", "minutes": 30}],
            "action_items": [{"task": "Send deck", "owner": "Sarah", "due": "2026-10-23"}],
            "language": "en",
        },
    )
    mock_response = MagicMock(content=[mock_tool_block], usage=mock_usage)
    mock_client.messages.create.return_value = mock_response

    parsed, usage = parse_agenda(
        text="Meeting tomorrow at 10am to discuss budget.",
        today=date(2026, 10, 21),
        tz="Europe/Kyiv",
        client=mock_client,
    )

    assert isinstance(parsed, ParsedAgenda)
    assert parsed.title == "Budget Meeting"
    assert parsed.duration_minutes == 30
    assert len(parsed.items) == 1
    assert len(parsed.action_items) == 1
    assert parsed.action_items[0].due == date(2026, 10, 23)
    assert usage == {"input_tokens": 120, "output_tokens": 80}
    assert mock_client.messages.create.call_count == 1


def test_parse_agenda_retry_success():
    mock_client = MagicMock()

    # Turn 1: invalid payload (minutes as string instead of int or invalid due date)
    mock_usage_1 = MagicMock(input_tokens=100, output_tokens=50)
    mock_tool_block_1 = MagicMock(
        type="tool_use",
        id="tool_1",
        name="record_agenda",
        input={
            "title": "Meeting",
            "action_items": [{"task": "Do thing", "due": "invalid-date"}],
        },
    )
    mock_response_1 = MagicMock(content=[mock_tool_block_1], usage=mock_usage_1)

    # Turn 2: corrected payload
    mock_usage_2 = MagicMock(input_tokens=150, output_tokens=60)
    mock_tool_block_2 = MagicMock(
        type="tool_use",
        id="tool_2",
        name="record_agenda",
        input={
            "title": "Meeting",
            "action_items": [{"task": "Do thing", "due": "2026-10-25"}],
        },
    )
    mock_response_2 = MagicMock(content=[mock_tool_block_2], usage=mock_usage_2)

    mock_client.messages.create.side_effect = [mock_response_1, mock_response_2]

    parsed, usage = parse_agenda(
        text="Meeting with task.",
        today=date(2026, 10, 21),
        tz="Europe/Kyiv",
        client=mock_client,
    )

    assert isinstance(parsed, ParsedAgenda)
    assert len(parsed.action_items) == 1
    assert parsed.action_items[0].due == date(2026, 10, 25)
    # Token usage accumulated across both turns
    assert usage == {"input_tokens": 250, "output_tokens": 110}
    assert mock_client.messages.create.call_count == 2

    # Check retry message payload
    retry_call_args = mock_client.messages.create.call_args_list[1]
    sent_messages = retry_call_args.kwargs["messages"]
    assert len(sent_messages) == 3
    assert sent_messages[1]["role"] == "assistant"
    assert sent_messages[2]["role"] == "user"
    assert sent_messages[2]["content"][0]["type"] == "tool_result"
    assert sent_messages[2]["content"][0]["is_error"] is True


def test_parse_agenda_validation_fails_twice():
    mock_client = MagicMock()
    mock_usage = MagicMock(input_tokens=100, output_tokens=50)
    invalid_block = MagicMock(
        type="tool_use",
        id="tool_err",
        name="record_agenda",
        input={"action_items": [{"task": "Do thing", "due": "invalid-date"}]},
    )
    mock_response = MagicMock(content=[invalid_block], usage=mock_usage)
    mock_client.messages.create.return_value = mock_response

    with pytest.raises(AgendaParseError, match="validation failed twice"):
        parse_agenda(
            text="Invalid meeting",
            today=date(2026, 10, 21),
            tz="Europe/Kyiv",
            client=mock_client,
        )


def test_parse_agenda_no_tool_call():
    mock_client = MagicMock()
    text_block = MagicMock(type="text", text="Sorry, I cannot parse this.")
    mock_response = MagicMock(
        content=[text_block],
        usage=MagicMock(input_tokens=50, output_tokens=10),
    )
    mock_client.messages.create.return_value = mock_response

    with pytest.raises(AgendaParseError, match="did not call the required tool"):
        parse_agenda(
            text="Non-meeting text",
            today=date(2026, 10, 21),
            tz="Europe/Kyiv",
            client=mock_client,
        )


def test_parse_agenda_scp_us_east_1_deny(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    with pytest.raises(AgendaParseError, match="us-east-1 is blocked by SCP"):
        parse_agenda(
            text="Test",
            today=date(2026, 10, 21),
            tz="Europe/Kyiv",
        )
