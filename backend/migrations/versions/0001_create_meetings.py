"""create meetings table

Revision ID: 0001_create_meetings
Revises:
Create Date: 2026-10-01 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_create_meetings"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meetings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attendee_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("attendee_count >= 1", name="ck_meetings_attendee_count"),
        sa.CheckConstraint("length(title) >= 1", name="ck_meetings_title_length"),
        sa.PrimaryKeyConstraint("id", name="pk_meetings"),
    )
    op.create_index(
        op.f("ix_meetings_starts_at"), "meetings", ["starts_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_meetings_starts_at"), table_name="meetings")
    op.drop_table("meetings")
