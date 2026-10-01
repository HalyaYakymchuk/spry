from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Meeting(Base):
    """SQLAlchemy model representing a scheduled meeting."""

    __tablename__ = "meetings"
    __table_args__ = (
        CheckConstraint("attendee_count >= 1", name="ck_meetings_attendee_count"),
        CheckConstraint("length(title) >= 1", name="ck_meetings_title_length"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attendee_count: Mapped[int] = mapped_column(Integer, nullable=False)
