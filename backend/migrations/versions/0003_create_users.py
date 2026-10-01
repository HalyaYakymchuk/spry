"""create users table and owner_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("cognito_sub", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_cognito_sub"), "users", ["cognito_sub"], unique=True)
    op.execute("DELETE FROM items")
    op.add_column("items", sa.Column("owner_id", sa.UUID(), nullable=False))
    op.create_index(op.f("ix_items_owner_id"), "items", ["owner_id"], unique=False)
    op.create_foreign_key(None, "items", "users", ["owner_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint(None, "items", type_="foreignkey")
    op.drop_index(op.f("ix_items_owner_id"), table_name="items")
    op.drop_column("items", "owner_id")
    op.drop_index(op.f("ix_users_cognito_sub"), table_name="users")
    op.drop_table("users")
