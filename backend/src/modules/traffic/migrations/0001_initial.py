"""traffic schema — relocates traffic_flows/bandwidth_metrics from the
public schema into their own traffic Postgres schema (D-11/D-14), per Plan
04 Task 1.

New Alembic branch (branch_labels=("traffic",)) per RESEARCH.md Pattern
7/8, chained after device_identity's own branch (down_revision points at
"device_identity_0001", the device_identity Alembic branch's head as of
Plan 03) so this revision applies on top of the full existing migration
chain exactly once.

This is a live-data schema move, not a create_table+copy: the
traffic_flows/bandwidth_metrics tables already exist (with data, and as
TimescaleDB hypertables) in the public schema as of migration 0004.
`ALTER TABLE ... SET SCHEMA` moves the existing rows/constraints/indexes in
place — no row is re-inserted, no data is copied or lost.

TimescaleDB hypertable metadata after ALTER TABLE ... SET SCHEMA: per
TimescaleDB's documented behavior, `ALTER TABLE ... SET SCHEMA` on a table
that is itself a hypertable updates the hypertable's catalog entry
in-place — it is a metadata-only rename, not a drop/recreate, so the
hypertable's chunks/dimensions/compression/retention settings are retained
automatically (this is the same operation Postgres performs for any
ALTER...SET SCHEMA, and TimescaleDB's hypertable catalog tracks tables by
OID, not by schema-qualified name). Continuous aggregates, however, are
themselves objects that materialize a query string referencing the
underlying hypertable by schema-qualified name; bandwidth_hourly/daily/
weekly/monthly's view definitions (from alembic/versions/0004_traffic_flows.py)
were created referencing the unqualified "bandwidth_metrics"/"bandwidth_daily"
names. Per TimescaleDB docs, a continuous aggregate's underlying query is
NOT automatically rewritten by a base-table schema move — the materialized
view would continue resolving the old unqualified name via the connection's
search_path, which works only as long as "traffic" is on search_path. To
avoid relying on search_path ordering (DEFENSIVE per T-05-13), this
migration drops and recreates the four continuous aggregates schema-qualified
against the moved tables, re-issuing the exact create_hypertable/
add_compression_policy/add_continuous_aggregate_policy calls from
0004_traffic_flows.py against "traffic.bandwidth_metrics"/"traffic.traffic_flows".

Revision ID: traffic_0001
Revises: device_identity_0001
Create Date: 2026-06-21
"""

from alembic import op

revision = "traffic_0001"
down_revision = "device_identity_0001"
branch_labels = ("traffic",)
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS traffic")

    # Drop the four continuous aggregates before the schema move — their
    # materialized query strings reference the pre-move unqualified table
    # names and must be recreated schema-qualified afterward (see module
    # docstring's T-05-13 rationale).
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bandwidth_monthly")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bandwidth_weekly")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bandwidth_daily")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bandwidth_hourly")

    # Live schema move — hypertable catalog metadata follows automatically
    # (tracked by OID, not schema-qualified name). device_mac_history
    # already moved to device_identity's schema in Plan 03's migration —
    # not touched here.
    op.execute("ALTER TABLE traffic_flows SET SCHEMA traffic")
    op.execute("ALTER TABLE bandwidth_metrics SET SCHEMA traffic")

    # Recreate the continuous aggregates schema-qualified against the moved
    # tables — same time_bucket widths/policies as 0004_traffic_flows.py.
    op.execute(
        """
        CREATE MATERIALIZED VIEW traffic.bandwidth_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            device_mac,
            sum(bytes_rx) AS bytes_rx,
            sum(bytes_tx) AS bytes_tx
        FROM traffic.bandwidth_metrics
        GROUP BY bucket, device_mac
        WITH NO DATA
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('traffic.bandwidth_hourly',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '30 minutes')
        """
    )

    op.execute(
        """
        CREATE MATERIALIZED VIEW traffic.bandwidth_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', bucket) AS bucket,
            device_mac,
            sum(bytes_rx) AS bytes_rx,
            sum(bytes_tx) AS bytes_tx
        FROM traffic.bandwidth_hourly
        GROUP BY time_bucket('1 day', bucket), device_mac
        WITH NO DATA
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('traffic.bandwidth_daily',
            start_offset => INTERVAL '3 days',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour')
        """
    )

    op.execute(
        """
        CREATE MATERIALIZED VIEW traffic.bandwidth_weekly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 week', bucket) AS bucket,
            device_mac,
            sum(bytes_rx) AS bytes_rx,
            sum(bytes_tx) AS bytes_tx
        FROM traffic.bandwidth_daily
        GROUP BY time_bucket('1 week', bucket), device_mac
        WITH NO DATA
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('traffic.bandwidth_weekly',
            start_offset => INTERVAL '3 weeks',
            end_offset => INTERVAL '6 hours',
            schedule_interval => INTERVAL '6 hours')
        """
    )

    op.execute(
        """
        CREATE MATERIALIZED VIEW traffic.bandwidth_monthly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 month', bucket) AS bucket,
            device_mac,
            sum(bytes_rx) AS bytes_rx,
            sum(bytes_tx) AS bytes_tx
        FROM traffic.bandwidth_daily
        GROUP BY time_bucket('1 month', bucket), device_mac
        WITH NO DATA
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('traffic.bandwidth_monthly',
            start_offset => INTERVAL '3 months',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day')
        """
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS traffic.bandwidth_monthly")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS traffic.bandwidth_weekly")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS traffic.bandwidth_daily")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS traffic.bandwidth_hourly")

    op.execute("ALTER TABLE traffic.bandwidth_metrics SET SCHEMA public")
    op.execute("ALTER TABLE traffic.traffic_flows SET SCHEMA public")

    op.execute(
        """
        CREATE MATERIALIZED VIEW bandwidth_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            device_mac,
            sum(bytes_rx) AS bytes_rx,
            sum(bytes_tx) AS bytes_tx
        FROM bandwidth_metrics
        GROUP BY bucket, device_mac
        WITH NO DATA
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('bandwidth_hourly',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '30 minutes')
        """
    )
    op.execute(
        """
        CREATE MATERIALIZED VIEW bandwidth_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', bucket) AS bucket,
            device_mac,
            sum(bytes_rx) AS bytes_rx,
            sum(bytes_tx) AS bytes_tx
        FROM bandwidth_hourly
        GROUP BY time_bucket('1 day', bucket), device_mac
        WITH NO DATA
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('bandwidth_daily',
            start_offset => INTERVAL '3 days',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour')
        """
    )
    op.execute(
        """
        CREATE MATERIALIZED VIEW bandwidth_weekly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 week', bucket) AS bucket,
            device_mac,
            sum(bytes_rx) AS bytes_rx,
            sum(bytes_tx) AS bytes_tx
        FROM bandwidth_daily
        GROUP BY time_bucket('1 week', bucket), device_mac
        WITH NO DATA
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('bandwidth_weekly',
            start_offset => INTERVAL '3 weeks',
            end_offset => INTERVAL '6 hours',
            schedule_interval => INTERVAL '6 hours')
        """
    )
    op.execute(
        """
        CREATE MATERIALIZED VIEW bandwidth_monthly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 month', bucket) AS bucket,
            device_mac,
            sum(bytes_rx) AS bytes_rx,
            sum(bytes_tx) AS bytes_tx
        FROM bandwidth_daily
        GROUP BY time_bucket('1 month', bucket), device_mac
        WITH NO DATA
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('bandwidth_monthly',
            start_offset => INTERVAL '3 months',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day')
        """
    )
    op.execute("DROP SCHEMA IF EXISTS traffic")
