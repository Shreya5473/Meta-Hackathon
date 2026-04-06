"""Pytest configuration and shared fixtures."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base, get_db
from app.main import app

# ── In-memory SQLite test database ───────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _patch_models_for_sqlite() -> None:
    """Replace PostgreSQL-specific types with SQLite-compatible equivalents."""
    from sqlalchemy.dialects.postgresql import JSONB, ARRAY
    import sqlalchemy as sa

    # Patch JSONB columns → JSON
    for table in Base.metadata.tables.values():
        # Strip timescaledb hypertable kwarg
        table.kwargs.pop("timescaledb_hypertable", None)
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, ARRAY):
                # SQLite doesn't support ARRAY — swap to JSON (we store list as JSON)
                col.type = JSON()


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="function")
async def test_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create tables in SQLite and yield a session for the test."""
    _patch_models_for_sqlite()
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        try:
            yield session
            await session.rollback()
        finally:
            pass

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def mock_redis():
    """Mock Redis client globally for tests."""
    mock_client = AsyncMock()
    mock_client.get.return_value = None
    mock_client.setex.return_value = True
    mock_client.ping.return_value = True
    mock_client.delete.return_value = 0
    mock_client.keys.return_value = []

    with patch("app.core.cache.get_redis", return_value=mock_client):
        yield mock_client


@pytest_asyncio.fixture(scope="function")
async def async_client(test_db_session: AsyncSession, mock_redis) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI async test client with overridden DB session."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_event_dict() -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "title": "Tensions escalate in Middle East after airstrikes",
        "occurred_at": datetime.now(UTC),
        "severity_score": 0.8,
        "sentiment_score": -0.7,
        "region": "middle_east",
        "geo_risk_vector": {"middle_east": 0.9, "global": 0.3},
        "classification": "escalation",
    }
