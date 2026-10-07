from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer, field_validator


class MeetingBase(BaseModel):
    title: str = Field(
        ..., min_length=1, max_length=255, description="Title of the meeting"
    )
    starts_at: datetime = Field(..., description="Start timestamp in ISO 8601 format")
    ends_at: datetime = Field(..., description="End timestamp in ISO 8601 format")
    attendee_count: int = Field(..., ge=1, description="Attendee count, must be >= 1")


class MeetingCreate(MeetingBase):
    @field_validator("ends_at")
    @classmethod
    def validate_ends_at(cls, v: datetime, info):
        if "starts_at" in info.data and v < info.data["starts_at"]:
            raise ValueError("ends_at must be equal to or after starts_at")
        return v


class MeetingResponse(MeetingBase):
    id: int

    @field_serializer("starts_at", "ends_at")
    def serialize_dt(self, dt: datetime, _info):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    model_config = {"from_attributes": True}
