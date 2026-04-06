"""Create live_price_ticks TimescaleDB hypertable.

This table stores raw bid/ask ticks ingested from OANDA (forex) and
CCXT-compatible exchanges (crypto/equities) during paper trading.  It is
modelled as a TimescaleDB hypertable partitioned by ``ts`` so that
time-range queries and continuous aggregates are highly efficient.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-11
"""
from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Create the raw ticks table ────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS live_price_ticks (
            symbol   TEXT        NOT NULL,
            source   TEXT        NOT NULL,           -- 'oanda' | 'ccxt:binance' etc.
            ts       TIMESTAMPTZ NOT NULL,
            bid      NUMERIC     NOT NULL,
            ask      NUMERIC     NOT NULL,
            mid      NUMERIC     NOT NULL,
            spread   NUMERIC     NOT NULL DEFAULT 0,
            PRIMARY KEY (symbol, ts)
        );
        """
    )

    # ── 2. Convert to TimescaleDB hypertable ─────────────────────────────────
    op.execute(
        """
        SELECT create_hypertable(
            'live_price_ticks', 'ts',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists       => TRUE,
            migrate_data        => TRUE
        );
        """
    )

    # ── 3. Indexes ────────────────────────────────────────────────────────────
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_lpt_symbol_ts_desc "
        "ON live_price_ticks (symbol, ts DESC);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_lpt_source_ts_desc "
        "ON live_price_ticks (source, ts DESC);"
    )

    # ── 4. Compression policy (compress chunks older than 1 day) ─────────────
    op.execute(
        """
        ALTER TABLE live_price_ticks SET (
            timescaledb.compress,
            timescaledb.compress_orderby   = 'ts DESC',
            timescaledb.compress_segmentby = 'symbol'
        );
        """
    )
    op.execute(
        "SELECT add_compression_policy("
        "    'live_price_ticks', INTERVAL '1 day', if_not_exists => TRUE"
        ");"
    )

    # ── 5. Retention policy (keep 90 days of raw ticks) ──────────────────────
    op.execute(
        "SELECT add_retention_policy("
        "    'live_price_ticks', INTERVAL '90 days', if_not_exists => TRUE"
        ");"
    )

    # ── 6. 1-minute OHLCV continuous aggregate ───────────────────────────────
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS live_price_1m
        WITH (timescaledb.continuous) AS
        SELECT
            symbol,
            source,
            time_bucket('1 minute', ts) AS bucket,
            FIRST(bid,  ts)             AS open_bid,
            MAX(bid)                    AS high_bid,
            MIN(bid)                    AS low_bid,
            LAST(bid,   ts)             AS close_bid,
            AVG(mid)                    AS avg_mid,
            COUNT(*)                    AS tick_count
        FROM live_price_ticks
        GROUP BY symbol, source, bucket
        WITH NO DATA;
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy(
            'live_price_1m',
            start_offset  => INTERVAL '10 minutes',
            end_offset    => INTERVAL '1 minute',
            schedule_interval => INTERVAL '1 minute',
            if_not_exists => TRUE
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS live_price_1m CASCADE;")
    op.execute("DROP TABLE IF EXISTS live_price_ticks CASCADE;")
