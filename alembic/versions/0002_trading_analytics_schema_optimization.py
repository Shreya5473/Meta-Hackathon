"""Create trading analytics schema + Timescale optimizations.

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-03-11 00:00:00.000000
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Create core entities and TimescaleDB optimization policies."""
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS assets (
            id          SERIAL PRIMARY KEY,
            symbol      TEXT NOT NULL UNIQUE,
            asset_type  TEXT NOT NULL,
            description TEXT,
            base_ccy    TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS prices (
            asset_id    INT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
            ts          TIMESTAMPTZ NOT NULL,
            open        NUMERIC,
            high        NUMERIC,
            low         NUMERIC,
            close       NUMERIC,
            volume      NUMERIC,
            source      TEXT,
            PRIMARY KEY (asset_id, ts)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS news_events (
            id               BIGSERIAL PRIMARY KEY,
            source           TEXT,
            url              TEXT,
            published_at     TIMESTAMPTZ,
            raw_title        TEXT,
            raw_body         TEXT,
            language         TEXT,
            region           TEXT,
            sentiment_score  NUMERIC,
            severity_score   NUMERIC,
            metadata         JSONB,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS gti_series (
            ts               TIMESTAMPTZ NOT NULL,
            gti_value        NUMERIC NOT NULL,
            metadata         JSONB,
            PRIMARY KEY (ts)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            id               BIGSERIAL PRIMARY KEY,
            asset_id         INT REFERENCES assets(id) ON DELETE CASCADE,
            ts               TIMESTAMPTZ NOT NULL,
            horizon          INTERVAL NOT NULL,
            model_type       TEXT NOT NULL,
            predicted_return NUMERIC,
            predicted_vol    NUMERIC,
            risk_score       NUMERIC,
            confidence       NUMERIC,
            metadata         JSONB,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )

    # Convert time-series tables to hypertables
    op.execute("SELECT create_hypertable('prices', 'ts', if_not_exists => TRUE, migrate_data => TRUE);")
    op.execute("SELECT create_hypertable('gti_series', 'ts', if_not_exists => TRUE, migrate_data => TRUE);")

    # Composite indexes for latest-N per-asset read patterns
    op.execute("CREATE INDEX IF NOT EXISTS idx_prices_asset_ts_desc ON prices (asset_id, ts DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_predictions_asset_ts_desc ON predictions (asset_id, ts DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_news_events_published_at_desc ON news_events (published_at DESC);")

    # Compression + retention policies (idempotent)
    op.execute(
        """
        ALTER TABLE prices SET (
          timescaledb.compress,
          timescaledb.compress_orderby = 'ts DESC',
          timescaledb.compress_segmentby = 'asset_id'
        );
        """
    )
    op.execute("SELECT add_compression_policy('prices', INTERVAL '7 days', if_not_exists => TRUE);")
    op.execute("SELECT add_retention_policy('prices', INTERVAL '180 days', if_not_exists => TRUE);")
    # news_events is a regular table (not a hypertable); skip retention policy

    # Continuous aggregates for downstream feature stores
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS features_prices_1d
        WITH (timescaledb.continuous) AS
        SELECT
            asset_id,
            time_bucket(INTERVAL '1 day', ts) AS bucket,
            AVG(close) AS avg_close,
            MAX(high) AS day_high,
            MIN(low) AS day_low,
            STDDEV_POP(close) AS close_std
        FROM prices
        GROUP BY asset_id, bucket
        WITH NO DATA;
        """
    )

    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS features_gti_1d
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket(INTERVAL '1 day', ts) AS bucket,
            AVG(gti_value) AS avg_gti,
            MAX(gti_value) AS max_gti,
            MIN(gti_value) AS min_gti
        FROM gti_series
        GROUP BY bucket
        WITH NO DATA;
        """
    )


def downgrade() -> None:
    """Partial downgrade for schema elements created here."""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS features_gti_1d;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS features_prices_1d;")
    op.execute("DROP TABLE IF EXISTS predictions;")
    op.execute("DROP TABLE IF EXISTS gti_series;")
    op.execute("DROP TABLE IF EXISTS news_events;")
    op.execute("DROP TABLE IF EXISTS prices;")
    op.execute("DROP TABLE IF EXISTS assets;")
