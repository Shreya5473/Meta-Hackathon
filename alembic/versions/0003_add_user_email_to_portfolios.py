"""Add user_email column to user_portfolios for email-keyed anonymous carts.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS so this migration is idempotent when the
    # ORM bootstrap (create_all) has already added the column.
    op.execute(
        """
        ALTER TABLE user_portfolios
        ADD COLUMN IF NOT EXISTS user_email VARCHAR(255);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_user_portfolios_user_email
        ON user_portfolios (user_email);
        """
    )


def downgrade() -> None:
    op.drop_index("ix_user_portfolios_user_email", table_name="user_portfolios")
    op.drop_column("user_portfolios", "user_email")
