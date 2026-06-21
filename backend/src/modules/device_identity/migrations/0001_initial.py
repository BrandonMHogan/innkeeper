"""device_identity schema — relocates devices/discovered_identities/
device_mac_history from the public schema into their own device_identity
Postgres schema (D-11/D-12), per Plan 03 Task 1.

New Alembic branch (branch_labels=("device_identity",)) per RESEARCH.md
Pattern 7 — this module owns its own migration history going forward,
separate from the main alembic/versions/ chain. down_revision points at
0006 (the current head as of Plan 01's module_configs migration), so this
revision applies on top of the existing 0001-0006 chain exactly once.

This is a live-data schema move, not a create_table+copy: the devices/
discovered_identities/device_mac_history tables already exist (with data)
in the public schema as of migration 0002/0003. `ALTER TABLE ... SET SCHEMA`
moves the existing rows/constraints/indexes/sequences in place — no row is
re-inserted, no data is copied or lost.

Revision ID: device_identity_0001
Revises: 0006
Create Date: 2026-06-21
"""

from alembic import op

revision = "device_identity_0001"
down_revision = "0006"
branch_labels = ("device_identity",)
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS device_identity")
    op.execute("ALTER TABLE devices SET SCHEMA device_identity")
    op.execute("ALTER TABLE discovered_identities SET SCHEMA device_identity")
    op.execute("ALTER TABLE device_mac_history SET SCHEMA device_identity")


def downgrade() -> None:
    op.execute("ALTER TABLE device_identity.device_mac_history SET SCHEMA public")
    op.execute("ALTER TABLE device_identity.discovered_identities SET SCHEMA public")
    op.execute("ALTER TABLE device_identity.devices SET SCHEMA public")
    op.execute("DROP SCHEMA IF EXISTS device_identity")
