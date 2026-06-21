"""Module Platform Foundation (Phase 5 Plan 01): module_configs table backing
MOD-02's enable/disable toggle. Modules default enabled (column default
True) — a missing row for a module_id is treated as enabled by
src/host/dependencies.py's is_module_enabled, not disabled.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "module_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("module_id", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_module_configs_module_id",
        "module_configs",
        ["module_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_module_configs_module_id", table_name="module_configs")
    op.drop_table("module_configs")
