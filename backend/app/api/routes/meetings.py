from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.meeting import Meeting
from app.schemas.meeting import MeetingCreate, MeetingResponse

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("", response_model=list[MeetingResponse], status_code=status.HTTP_200_OK)
def list_meetings(db: Session = Depends(get_db)) -> list[Meeting]:
    """Retrieve all meetings ordered chronologically by starts_at."""
    stmt = select(Meeting).order_by(Meeting.starts_at.asc())
    return list(db.scalars(stmt).all())


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def create_meeting(meeting_in: MeetingCreate, db: Session = Depends(get_db)) -> Meeting:
    """Create a new meeting."""
    meeting = Meeting(
        title=meeting_in.title,
        starts_at=meeting_in.starts_at,
        ends_at=meeting_in.ends_at,
        attendee_count=meeting_in.attendee_count,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting
