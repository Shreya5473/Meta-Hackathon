"""Create trade_log table for ML-driven order tracking and P&L.

Each row represents one trade decision (buy / sell / hold) made by the
OrderManager.  The table is intentionally kept simple — no foreign keys to
user_portfolios because the email-keyed anonymous cart is the join point.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-11
"""
from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS trade_log (
            id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            email           TEXT        NOT NULL,
            symbol          TEXT        NOT NULL,
            action          TEXT        NOT NULL,           -- buy | sell | hold
            quantity        DOUBLE PRECISION,
            price           DOUBLE PRECISION,
            signal_vol_spike DOUBLE PRECISION,
            signal_bias     DOUBLE PRECISION,
            recommendation  TEXT,
            order_id        TEXT,
            status          TEXT,                          -- accepted | rejected | hold | dry_run
            broker          TEXT,                          -- oanda | paper | none
            pnl             DOUBLE PRECISION,
            note            TEXT
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_trade_log_email ON trade_log (email);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_trade_log_ts    ON trade_log (ts DESC);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS trade_log;")
