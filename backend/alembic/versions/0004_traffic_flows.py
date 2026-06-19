"""traffic_flows hypertable, device_mac_history table, continuous aggregates,
compression policies (no retention policy — D-06).

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "traffic_flows",
        sa.Column("time", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("device_mac", sa.String(17), nullable=False),
        sa.Column("dst_ip", sa.String(45), nullable=False),
        sa.Column("dst_port", sa.Integer(), nullable=True),
        sa.Column("protocol", sa.Integer(), nullable=False),
        sa.Column("bytes", sa.Float(), nullable=False, server_default="0"),
        sa.Column("dst_hostname", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("time", "device_mac", "dst_ip", "dst_port", "protocol"),
    )

    # Convert traffic_flows to a TimescaleDB hypertable (D-05).
    op.execute("SELECT create_hypertable('traffic_flows', by_range('time', INTERVAL '1 week'))")

    # Declare the index TimescaleDB auto-creates on the time column so Alembic
    # autogenerate doesn't try to drop it on a later migration (mirrors 0001's
    # bandwidth_metrics_time_idx pattern).
    op.execute("CREATE INDEX IF NOT EXISTS traffic_flows_time_idx ON traffic_flows (time)")

    op.create_table(
        "device_mac_history",
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("mac", sa.String(17), nullable=False),
        sa.Column("first_seen", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("device_id", "mac"),
    )

    # Continuous aggregates for bandwidth_metrics — hierarchical hourly ->
    # daily -> weekly/monthly (TRAF-04). Real-time aggregation default-off
    # since TimescaleDB v2.13 (Pitfall 2) is acceptable here: charts read
    # through these caggs with scheduled refreshes, not live "today" totals.
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

    # Compression policies — keep all rows forever, just shrink storage after
    # they age out. Deliberately NOT calling add_retention_policy() anywhere
    # in this migration (D-06 — never auto-delete by default; Pitfall 3).
    op.execute(
        """
        ALTER TABLE bandwidth_metrics SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'device_mac',
            timescaledb.compress_orderby = 'time DESC'
        )
        """
    )
    op.execute("SELECT add_compression_policy('bandwidth_metrics', compress_after => INTERVAL '7 days')")

    op.execute(
        """
        ALTER TABLE traffic_flows SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'device_mac',
            timescaledb.compress_orderby = 'time DESC'
        )
        """
    )
    op.execute("SELECT add_compression_policy('traffic_flows', compress_after => INTERVAL '7 days')")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bandwidth_monthly")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bandwidth_weekly")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bandwidth_daily")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS bandwidth_hourly")
    op.drop_table("device_mac_history")
    op.drop_table("traffic_flows")
