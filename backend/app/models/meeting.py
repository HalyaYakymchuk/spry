from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.agenda import Agenda


class Meeting(Base):
    """SQLAlchemy model representing a scheduled meeting."""

    __tablename__ = "meetings"
    __table_args__ = (
        CheckConstraint("attendee_count >= 1", name="ck_meetings_attendee_count"),
        CheckConstraint("length(title) >= 1", name="ck_meetings_title_length"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attendee_count: Mapped[int] = mapped_column(Integer, nullable=False)

    agenda: Mapped[Optional["Agenda"]] = relationship(
        "Agenda",
        back_populates="meeting",
        uselist=False,
        cascade="all, delete-orphan",
    )
