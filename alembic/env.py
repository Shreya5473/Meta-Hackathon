"""Alembic env.py — auto-generates migrations from SQLAlchemy models."""
from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

# Load .env so DATABASE_SYNC_URL is available without a shell export
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    pass

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import all models to ensure they are registered in metadata
from app.core.database import Base
import app.models  # noqa: F401 — side-effect: registers all ORM models

config = context.config

# Override sqlalchemy.url from environment (asyncpg → psycopg2 for sync use)
_db_url = os.getenv("DATABASE_SYNC_URL") or os.getenv("DATABASE_URL", "")
_db_url = _db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
config.set_main_option("sqlalchemy.url", _db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Bootstrap: create any ORM-declared tables that don't exist yet so
        # migrations that ALTER or ADD COLUMN to them can always proceed cleanly.
        target_metadata.create_all(bind=connectable, checkfirst=True)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
