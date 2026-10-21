from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_serializer


class AgendaItemSchema(BaseModel):
    topic: str
    owner: str | None = None
    minutes: int | None = None


class ActionItemSchema(BaseModel):
    task: str
    owner: str | None = None
    due: str | None = None


class AgendaCreate(BaseModel):
    title: str | None = None
    items: list[AgendaItemSchema] = Field(default_factory=list)
    action_items: list[ActionItemSchema] = Field(default_factory=list)
    ai_suggestion: dict[str, Any] | None = None
    model: str | None = None
    prompt_version: str | None = None


class AgendaUpdate(BaseModel):
    title: str | None = None
    items: list[AgendaItemSchema] | None = None
    action_items: list[ActionItemSchema] | None = None
    ai_suggestion: dict[str, Any] | None = None
    model: str | None = None
    prompt_version: str | None = None


class AgendaResponse(BaseModel):
    id: int
    meeting_id: int
    title: str | None = None
    items: list[AgendaItemSchema] = Field(default_factory=list)
    action_items: list[ActionItemSchema] = Field(default_factory=list)
    ai_suggestion: dict[str, Any] | None = None
    model: str | None = None
    prompt_version: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_serializer("created_at", "updated_at")
    def serialize_dt(self, dt: datetime | None, _info):
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    model_config = {"from_attributes": True}
