"""add provider model registry and default_model

Revision ID: 7c1f4b9d2e10
Revises: 352a58f07526
Create Date: 2026-10-21

Adds:
  * llm_providers.default_model - model preselected for new agents
  * provider_models table       - discovered chat models per provider
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c1f4b9d2e10"
down_revision: Union[str, None] = "352a58f07526"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(conn, name: str) -> bool:
    return sa.inspect(conn).has_table(name)


def _has_column(conn, table: str, column: str) -> bool:
    return any(c["name"] == column for c in sa.inspect(conn).get_columns(table))


def upgrade() -> None:
    """Apply the schema additively.

    ``create_all`` runs on startup, so a fresh database may already contain
    these objects. Every step is guarded to keep the migration idempotent.
    """
    conn = op.get_bind()

    if not _has_column(conn, "llm_providers", "default_model"):
        op.add_column(
            "llm_providers",
            sa.Column("default_model", sa.String(length=255), nullable=True),
        )

    if _has_table(conn, "provider_models"):
        return

    op.create_table(
        "provider_models",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("context_length", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "pricing",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        sa.ForeignKeyConstraint(["provider_id"], ["llm_providers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_id", "model_id", name="uq_provider_models_provider_model"
        ),
    )
    op.create_index(
        "ix_provider_models_provider_id",
        "provider_models",
        ["provider_id"],
        unique=False,
    )


def downgrade() -> None:
    conn = op.get_bind()
    if _has_table(conn, "provider_models"):
        op.drop_index("ix_provider_models_provider_id", table_name="provider_models")
        op.drop_table("provider_models")
    if _has_column(conn, "llm_providers", "default_model"):
        op.drop_column("llm_providers", "default_model")
