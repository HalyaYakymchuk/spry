"""create agendas table

Revision ID: 0002_create_agendas
Revises: 0001_create_meetings
Create Date: 2026-10-21 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_create_agendas"
down_revision: str | Sequence[str] | None = "0001_create_meetings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agendas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("items", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("action_items", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("ai_suggestion", sa.JSON(), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["meeting_id"],
            ["meetings.id"],
            name="fk_agendas_meeting_id_meetings",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agendas"),
        sa.UniqueConstraint("meeting_id", name="uq_agendas_meeting_id"),
    )
    op.create_index(
        op.f("ix_agendas_meeting_id"), "agendas", ["meeting_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agendas_meeting_id"), table_name="agendas")
    op.drop_table("agendas")
