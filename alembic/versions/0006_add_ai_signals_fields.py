"""Add enhanced AI signals fields to market_signals table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to market_signals
    op.add_column("market_signals", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("market_signals", sa.Column("bullish_strength", sa.Float(), nullable=True))
    op.add_column("market_signals", sa.Column("bearish_strength", sa.Float(), nullable=True))
    op.add_column("market_signals", sa.Column("volatility", sa.String(length=16), nullable=True))
    op.add_column("market_signals", sa.Column("triggering_event", sa.Text(), nullable=True))
    op.add_column("market_signals", sa.Column("entry", sa.Float(), nullable=True))
    op.add_column("market_signals", sa.Column("stop_loss", sa.Float(), nullable=True))
    op.add_column("market_signals", sa.Column("target", sa.Float(), nullable=True))
    op.add_column("market_signals", sa.Column("risk_reward", sa.Float(), nullable=True))
    op.add_column("market_signals", sa.Column("atr", sa.Float(), nullable=True))
    op.add_column("market_signals", sa.Column("max_position", sa.Float(), nullable=True))
    op.add_column("market_signals", sa.Column("reasoning", sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove columns from market_signals
    op.drop_column("market_signals", "reasoning")
    op.drop_column("market_signals", "max_position")
    op.drop_column("market_signals", "atr")
    op.drop_column("market_signals", "risk_reward")
    op.drop_column("market_signals", "target")
    op.drop_column("market_signals", "stop_loss")
    op.drop_column("market_signals", "entry")
    op.drop_column("market_signals", "triggering_event")
    op.drop_column("market_signals", "volatility")
    op.drop_column("market_signals", "bearish_strength")
    op.drop_column("market_signals", "bullish_strength")
    op.drop_column("market_signals", "confidence")
