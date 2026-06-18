"""Initial schema: app_settings, bandwidth_metrics (hypertable), arp_events.

Revision ID: 0001
Revises:
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=True),
        sa.Column("setup_complete", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "bandwidth_metrics",
        sa.Column("time", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("device_mac", sa.String(17), nullable=False),
        sa.Column("bytes_rx", sa.Float(), nullable=False, server_default="0"),
        sa.Column("bytes_tx", sa.Float(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("time", "device_mac"),
    )

    op.create_table(
        "arp_events",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("src_mac", sa.String(17), nullable=False),
        sa.Column("src_ip", sa.String(45), nullable=False),
        sa.Column("dst_ip", sa.String(45), nullable=False),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # Convert bandwidth_metrics to a TimescaleDB hypertable (D-16 — schema locked
    # in Phase 1 even though Phase 3 is what populates it).
    op.execute(
        "SELECT create_hypertable('bandwidth_metrics', by_range('time', INTERVAL '1 week'))"
    )

    # Declare the index TimescaleDB auto-creates on the time column so Alembic
    # autogenerate doesn't try to drop it on a later migration (Pitfall 2).
    # IF NOT EXISTS because create_hypertable() above already created this
    # exact index — op.create_index() would error with DuplicateTableError.
    op.execute(
        "CREATE INDEX IF NOT EXISTS bandwidth_metrics_time_idx ON bandwidth_metrics (time)"
    )


def downgrade() -> None:
    op.drop_table("arp_events")
    op.drop_table("bandwidth_metrics")
    op.drop_table("app_settings")
