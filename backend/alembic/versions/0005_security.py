"""Phase 4 security foundation: Device gains security_status/last_scanned_at/
last_known_ip columns; new port_scan_results, security_alerts,
pending_scan_requests tables (D-05/D-06/D-08/D-11).

All three new tables are plain relational tables, not hypertables — per
STATE.md's note that TimescaleDB schema changes should not be applied to
non-time-series data.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("security_status", sa.String(), nullable=False, server_default="good"))
    op.add_column("devices", sa.Column("last_scanned_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("devices", sa.Column("last_known_ip", sa.String(45), nullable=True))

    op.create_table(
        "port_scan_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("scanned_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("open_ports", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
    )

    op.create_table(
        "security_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
    )

    op.create_table(
        "pending_scan_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("claimed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
    )


def downgrade() -> None:
    op.drop_table("pending_scan_requests")
    op.drop_table("security_alerts")
    op.drop_table("port_scan_results")
    op.drop_column("devices", "last_known_ip")
    op.drop_column("devices", "last_scanned_at")
    op.drop_column("devices", "security_status")
