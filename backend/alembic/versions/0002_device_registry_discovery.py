"""Device registry + discovery: dhcp_events, mdns_events, discovered_identities, devices.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_DEVICE_TYPE_VALUES = [
    "phone",
    "laptop",
    "desktop",
    "tablet",
    "iot_smart_home",
    "tv_streaming",
    "game_console",
    "router_network",
    "other",
]


def upgrade() -> None:
    op.create_table(
        "dhcp_events",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("src_mac", sa.String(17), nullable=False),
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("requested_ip", sa.String(45), nullable=True),
        sa.Column("vendor_class_id", sa.String(255), nullable=True),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "mdns_events",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("service_type", sa.String(255), nullable=False),
        sa.Column("addresses", sa.String(512), nullable=False),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "discovered_identities",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("identity_key", sa.String(255), nullable=False),
        sa.Column("mac", sa.String(17), nullable=False),
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("first_seen", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_key"),
    )

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("identity_key", sa.String(255), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("owner", sa.String(100), nullable=False, server_default=""),
        sa.Column("type", sa.Enum(*_DEVICE_TYPE_VALUES, name="devicetype"), nullable=False),
        sa.Column("trusted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_known_mac", sa.String(17), nullable=True),
        sa.Column("first_seen", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_key"),
    )


def downgrade() -> None:
    op.drop_table("devices")
    op.drop_table("discovered_identities")
    op.drop_table("mdns_events")
    op.drop_table("dhcp_events")
