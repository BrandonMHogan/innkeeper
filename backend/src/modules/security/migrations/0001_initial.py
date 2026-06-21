"""security schema — relocates port_scan_results/security_alerts/
pending_scan_requests from the public schema into their own security
Postgres schema (D-11/D-14), per Plan 05 Task 1.

New Alembic branch (branch_labels=("security",)) per RESEARCH.md Pattern
7/8, chained after traffic's own branch (down_revision points at
"traffic_0001", the traffic Alembic branch's head as of Plan 04) so this
revision applies on top of the full existing migration chain exactly once.

This is a live-data schema move, not a create_table+copy: the three tables
already exist (with data) in the public schema as of migration 0005.
`ALTER TABLE ... SET SCHEMA` moves the existing rows/constraints/indexes in
place — no row is re-inserted, no data is copied or lost.

Revision ID: security_0001
Revises: traffic_0001
Create Date: 2026-06-21
"""

from alembic import op

revision = "security_0001"
down_revision = "traffic_0001"
branch_labels = ("security",)
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS security")

    op.execute("ALTER TABLE port_scan_results SET SCHEMA security")
    op.execute("ALTER TABLE security_alerts SET SCHEMA security")
    op.execute("ALTER TABLE pending_scan_requests SET SCHEMA security")


def downgrade() -> None:
    op.execute("ALTER TABLE security.pending_scan_requests SET SCHEMA public")
    op.execute("ALTER TABLE security.security_alerts SET SCHEMA public")
    op.execute("ALTER TABLE security.port_scan_results SET SCHEMA public")

    op.execute("DROP SCHEMA IF EXISTS security")
