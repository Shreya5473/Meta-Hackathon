-- GeoTrade PostgreSQL / TimescaleDB baseline schema
-- Created: 2026-03-11
--
-- This schema captures a clean interview-friendly baseline for trading +
-- analytics workloads while preserving production concerns:
-- - time-series hypertables for prices and gti_series
-- - query-path indexes for latest-N lookups
-- - retention/compression policies on raw streams
-- - pre-aggregated continuous materialized views

BEGIN;

-- Required extension for hypertables and policies
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 4.1 Core entities

CREATE TABLE IF NOT EXISTS assets (
    id          SERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL UNIQUE,
    asset_type  TEXT NOT NULL,          -- fx, equity, crypto, index, etc.
    description TEXT,
    base_ccy    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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

CREATE TABLE IF NOT EXISTS gti_series (
    ts               TIMESTAMPTZ NOT NULL,
    gti_value        NUMERIC NOT NULL,
    metadata         JSONB,
    PRIMARY KEY (ts)
);

CREATE TABLE IF NOT EXISTS predictions (
    id               BIGSERIAL PRIMARY KEY,
    asset_id         INT REFERENCES assets(id) ON DELETE CASCADE,
    ts               TIMESTAMPTZ NOT NULL,
    horizon          INTERVAL NOT NULL,
    model_type       TEXT NOT NULL,      -- lightgbm, xgboost, lstm, ensemble
    predicted_return NUMERIC,
    predicted_vol    NUMERIC,
    risk_score       NUMERIC,
    confidence       NUMERIC,
    metadata         JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4.2 Time-series conversion
SELECT create_hypertable('prices', 'ts', if_not_exists => TRUE, migrate_data => TRUE);
SELECT create_hypertable('gti_series', 'ts', if_not_exists => TRUE, migrate_data => TRUE);

-- 4.2 Query-path indexes
CREATE INDEX IF NOT EXISTS idx_prices_asset_ts_desc ON prices (asset_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_asset_ts_desc ON predictions (asset_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_news_events_published_at_desc ON news_events (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_events_source ON news_events (source);

-- 4.2 Compression + retention on raw streams
ALTER TABLE prices SET (
  timescaledb.compress,
  timescaledb.compress_orderby = 'ts DESC',
  timescaledb.compress_segmentby = 'asset_id'
);
SELECT add_compression_policy('prices', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('prices', INTERVAL '180 days', if_not_exists => TRUE);

-- Keep raw events shorter than curated analytics layers
SELECT add_retention_policy('news_events', INTERVAL '365 days', if_not_exists => TRUE);

-- 4.2 Materialized / continuous aggregates
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

SELECT add_continuous_aggregate_policy(
  'features_prices_1d',
  start_offset => INTERVAL '30 days',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '15 minutes'
);

SELECT add_continuous_aggregate_policy(
  'features_gti_1d',
  start_offset => INTERVAL '90 days',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '30 minutes'
);

COMMIT;
