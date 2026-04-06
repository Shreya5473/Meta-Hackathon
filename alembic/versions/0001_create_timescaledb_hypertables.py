"""Create TimescaleDB hypertables for all time-series tables.

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-03-11 00:00:00.000000

Why this migration exists
--------------------------
The SQLAlchemy ORM models carry timescaledb_hypertable metadata in their
__table_args__, but SQLAlchemy does NOT translate that annotation into a
create_hypertable() call automatically.  Without this migration the tables are
created as plain PostgreSQL tables and all TimescaleDB time-series optimisations
(chunk-based compression, time_bucket queries, etc.) are disabled.

This migration calls create_hypertable() for every table that was declared with
the hypertable annotation.  Each call uses if_not_exists => TRUE so the migration
is safe to re-run and idempotent.

Tables converted
----------------
events          occurred_at
market_data     ts
gti_snapshots   ts
market_signals  ts
"""
from __future__ import annotations

from alembic import op

# Alembic revision identifiers
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Convert time-series tables into TimescaleDB hypertables.

    Each statement is wrapped in a DO block that first checks whether the
    TimescaleDB extension is present, so the migration degrades gracefully on
    vanilla PostgreSQL (e.g. in CI test databases that use SQLite/plain Postgres).
    """
    _hypertables = [
        ("events", "occurred_at"),
        ("market_data", "ts"),
        ("gti_snapshots", "ts"),
        ("market_signals", "ts"),
    ]

    for table, time_col in _hypertables:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
                ) THEN
                    PERFORM create_hypertable(
                        '{table}',
                        '{time_col}',
                        if_not_exists => TRUE,
                        migrate_data  => TRUE
                    );
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    """Hypertable conversion cannot be trivially reversed.

    Rolling back would require dropping and recreating each table as a plain
    relation — a destructive operation that causes data loss.  This is an
    intentional no-op; revert by restoring from a pre-migration backup.
    """
    pass
