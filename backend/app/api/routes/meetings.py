from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.agenda import Agenda
from app.models.meeting import Meeting
from app.schemas.agenda import AgendaCreate, AgendaResponse
from app.schemas.meeting import MeetingCreate, MeetingResponse

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("", response_model=list[MeetingResponse], status_code=status.HTTP_200_OK)
def list_meetings(db: Session = Depends(get_db)) -> list[Meeting]:
    """Retrieve all meetings ordered chronologically by starts_at with optional agenda."""
    stmt = (
        select(Meeting)
        .options(selectinload(Meeting.agenda))
        .order_by(Meeting.starts_at.asc())
    )
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


@router.get(
    "/{meeting_id}", response_model=MeetingResponse, status_code=status.HTTP_200_OK
)
def get_meeting(meeting_id: int, db: Session = Depends(get_db)) -> Meeting:
    """Retrieve a single meeting by its ID."""
    stmt = (
        select(Meeting)
        .options(selectinload(Meeting.agenda))
        .where(Meeting.id == meeting_id)
    )
    meeting = db.scalar(stmt)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting {meeting_id} not found",
        )
    return meeting


@router.get(
    "/{meeting_id}/agenda",
    response_model=Optional[AgendaResponse],
    status_code=status.HTTP_200_OK,
)
def get_meeting_agenda(
    meeting_id: int, db: Session = Depends(get_db)
) -> Optional[Agenda]:
    """Retrieve the agenda associated with a meeting."""
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting {meeting_id} not found",
        )

    stmt = select(Agenda).where(Agenda.meeting_id == meeting_id)
    agenda = db.scalar(stmt)
    return agenda


@router.post(
    "/{meeting_id}/agenda",
    response_model=AgendaResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.put(
    "/{meeting_id}/agenda",
    response_model=AgendaResponse,
    status_code=status.HTTP_200_OK,
)
def save_meeting_agenda(
    meeting_id: int,
    agenda_in: AgendaCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> Agenda:
    """Create or update (upsert) the agenda for a meeting."""
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting {meeting_id} not found",
        )

    stmt = select(Agenda).where(Agenda.meeting_id == meeting_id)
    agenda = db.scalar(stmt)

    items_data: list[dict[str, Any]] = [
        item.model_dump() for item in agenda_in.items
    ]
    action_items_data: list[dict[str, Any]] = [
        action.model_dump() for action in agenda_in.action_items
    ]

    if agenda:
        # Update existing agenda
        response.status_code = status.HTTP_200_OK
        agenda.title = agenda_in.title
        agenda.items = items_data
        agenda.action_items = action_items_data
        agenda.ai_suggestion = agenda_in.ai_suggestion
        agenda.model = agenda_in.model
        agenda.prompt_version = agenda_in.prompt_version
        agenda.updated_at = datetime.now(timezone.utc)
    else:
        # Create new agenda
        response.status_code = status.HTTP_201_CREATED
        agenda = Agenda(
            meeting_id=meeting_id,
            title=agenda_in.title,
            items=items_data,
            action_items=action_items_data,
            ai_suggestion=agenda_in.ai_suggestion,
            model=agenda_in.model,
            prompt_version=agenda_in.prompt_version,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(agenda)

    db.commit()
    db.refresh(agenda)
    return agenda


@router.put(
    "/{meeting_id}/agenda",
    response_model=AgendaResponse,
    status_code=status.HTTP_200_OK,
)
def put_meeting_agenda(
    meeting_id: int,
    agenda_in: AgendaCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> Agenda:
    """Idempotent update or creation of meeting agenda."""
    return save_meeting_agenda(
        meeting_id=meeting_id, agenda_in=agenda_in, response=response, db=db
    )
