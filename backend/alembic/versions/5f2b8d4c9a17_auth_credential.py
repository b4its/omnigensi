"""auth_credential table for a rotatable operator password

Revision ID: 5f2b8d4c9a17
Revises: 3d9a7c5e1b42
Create Date: 2026-10-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "5f2b8d4c9a17"
down_revision: Union[str, None] = "3d9a7c5e1b42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(conn, name: str) -> bool:
    return sa.inspect(conn).has_table(name)


def upgrade() -> None:
    conn = op.get_bind()
    if _has_table(conn, "auth_credential"):
        return

    op.create_table(
        "auth_credential",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    if _has_table(conn, "auth_credential"):
        op.drop_table("auth_credential")
