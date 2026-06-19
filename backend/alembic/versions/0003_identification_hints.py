"""Identification hints: mdns_service_type/dhcp_vendor_class on discovered_identities.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("discovered_identities", sa.Column("mdns_service_type", sa.String(255), nullable=True))
    op.add_column("discovered_identities", sa.Column("dhcp_vendor_class", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("discovered_identities", "dhcp_vendor_class")
    op.drop_column("discovered_identities", "mdns_service_type")
