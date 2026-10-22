"""token_version for instant session revocation

Revision ID: b6e3f81d5c40
Revises: 9c4e1a7b3f28
Create Date: 2026-10-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b6e3f81d5c40"
down_revision: Union[str, None] = "9c4e1a7b3f28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table: str, column: str) -> bool:
    try:
        return any(c["name"] == column for c in sa.inspect(conn).get_columns(table))
    except sa.exc.NoSuchTableError:  # pragma: no cover
        return False


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_column(conn, "auth_credential", "token_version"):
        op.add_column(
            "auth_credential",
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _has_column(conn, "auth_credential", "token_version"):
        op.drop_column("auth_credential", "token_version")
