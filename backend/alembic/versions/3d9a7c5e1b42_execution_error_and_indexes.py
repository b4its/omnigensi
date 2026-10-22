"""execution error_message, simulated flag and filter indexes

Revision ID: 3d9a7c5e1b42
Revises: 7c1f4b9d2e10
Create Date: 2026-10-21

Adds:
  * workflow_executions.error_message - structured failure reason
  * workflow_executions.simulated     - provider failure fell back to simulation
  * indexes on workflow_id/status/started_at used by the history filters
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "3d9a7c5e1b42"
down_revision: Union[str, None] = "7c1f4b9d2e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES = (
    "ix_workflow_executions_workflow_id",
    "ix_workflow_executions_status",
    "ix_workflow_executions_started_at",
)


def _has_column(conn, table: str, column: str) -> bool:
    return any(c["name"] == column for c in sa.inspect(conn).get_columns(table))


def _indexes(conn, table: str) -> set:
    try:
        return {i["name"] for i in sa.inspect(conn).get_indexes(table)}
    except sa.exc.NoSuchTableError:  # pragma: no cover - table always exists
        return set()


def upgrade() -> None:
    """Idempotent: create_all runs on startup so objects may already exist."""
    conn = op.get_bind()

    if not _has_column(conn, "workflow_executions", "error_message"):
        op.add_column(
            "workflow_executions",
            sa.Column("error_message", sa.Text(), nullable=True),
        )

    if not _has_column(conn, "workflow_executions", "simulated"):
        op.add_column(
            "workflow_executions",
            sa.Column(
                "simulated",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    existing = _indexes(conn, "workflow_executions")
    specs = {
        "ix_workflow_executions_workflow_id": ["workflow_id"],
        "ix_workflow_executions_status": ["status"],
        "ix_workflow_executions_started_at": ["started_at"],
    }
    for name, columns in specs.items():
        if name not in existing:
            op.create_index(name, "workflow_executions", columns, unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    existing = _indexes(conn, "workflow_executions")
    for name in INDEXES:
        if name in existing:
            op.drop_index(name, table_name="workflow_executions")

    if _has_column(conn, "workflow_executions", "simulated"):
        op.drop_column("workflow_executions", "simulated")
    if _has_column(conn, "workflow_executions", "error_message"):
        op.drop_column("workflow_executions", "error_message")
