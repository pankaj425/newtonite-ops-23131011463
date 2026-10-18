"""Add a composite index for team-scoped listing ordered by created_at.

The list endpoint always filters by team membership and orders by
``created_at DESC, id DESC``. A composite ``(team_id, created_at)`` index lets
PostgreSQL satisfy the filter and most of the sort without a full scan.

Revision ID: 0002_team_created_index
Revises: 0001_initial
Create Date: 2026-10-18

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_team_created_index"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_work_items_team_created",
        "work_items",
        ["team_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_work_items_team_created", table_name="work_items")
