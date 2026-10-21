from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.meeting import Meeting


class Agenda(Base):
    """SQLAlchemy model representing a meeting's agenda and quality signals."""

    __tablename__ = "agendas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    items: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    action_items: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    ai_suggestion: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="agenda")
