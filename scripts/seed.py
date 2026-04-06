#!/usr/bin/env python3
"""Seed script — populates 30 days of sample events and market OHLCV data.

Usage:
    python scripts/seed.py
    # or via docker:
    make seed
"""
from __future__ import annotations

import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.logging import configure_logging, get_logger
from app.models.event import Event, EventCluster
from app.models.gti import GTISnapshot
from app.models.market import MarketData
from app.models.signal import MarketSignal, ModelVersion
from app.models.ingestion import IngestionSource

configure_logging()
logger = get_logger("seed")

rng = random.Random(2024)

REGIONS = ["global", "middle_east", "europe", "asia_pacific", "americas"]

SAMPLE_HEADLINES = [
    ("Tensions escalate in Gaza as airstrikes continue overnight", "middle_east", "escalation", -0.85, 0.9),
    ("NATO expands eastern flank amid rising Russian threats", "europe", "tension", -0.6, 0.7),
    ("Oil prices surge 8% after OPEC production cut announcement", "global", "tension", -0.4, 0.6),
    ("US-China trade war intensifies with new 25% tariff round", "asia_pacific", "tension", -0.55, 0.65),
    ("Iranian nuclear program back under international scrutiny", "middle_east", "tension", -0.5, 0.7),
    ("Stock markets rally as inflation data comes in below forecast", "americas", "normal", 0.7, 0.1),
    ("Cyber attack targets European energy infrastructure", "europe", "escalation", -0.7, 0.8),
    ("Humanitarian corridor opens in Sudan conflict zone", "africa", "normal", 0.3, 0.2),
    ("G7 sanctions Russia with new financial restrictions", "europe", "tension", -0.6, 0.65),
    ("Taiwan Strait military exercises raise regional tensions", "asia_pacific", "escalation", -0.75, 0.85),
    ("Saudi Arabia and Iran restore diplomatic ties", "middle_east", "normal", 0.8, 0.1),
    ("Fed holds rates steady amid geopolitical uncertainty", "americas", "normal", 0.2, 0.2),
    ("Houthi attacks on Red Sea shipping disrupt global trade", "middle_east", "escalation", -0.8, 0.88),
    ("Pakistan election results disputed, street protests erupt", "asia_pacific", "tension", -0.5, 0.6),
    ("Venezuela opposition leader arrested before election", "americas", "tension", -0.55, 0.55),
]

ASSETS = [
    ("SPY", "equity", "americas"),
    ("QQQ", "equity", "americas"),
    ("XLE", "equity", "americas"),
    ("GLD", "commodities", "global"),
    ("USO", "commodities", "middle_east"),
    ("TLT", "financials", "americas"),
    ("EEM", "equity", "asia_pacific"),
    ("EWG", "equity", "europe"),
    ("BNO", "commodities", "global"),
    ("CYB", "equity", "global"),
]


async def seed_ingestion_sources(session: object) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    sess: AsyncSession = session  # type: ignore
    existing = await sess.execute(select(IngestionSource).limit(1))
    if existing.scalar_one_or_none():
        logger.info("ingestion_sources_already_seeded")
        return

    sources = [
        IngestionSource(name="reuters_world", adapter_type="rss", url="https://feeds.reuters.com/reuters/worldNews", region="global"),
        IngestionSource(name="bbc_world", adapter_type="rss", url="https://feeds.bbci.co.uk/news/world/rss.xml", region="global"),
        IngestionSource(name="al_jazeera", adapter_type="rss", url="https://www.aljazeera.com/xml/rss/all.xml", region="middle_east"),
    ]
    sess.add_all(sources)
    await sess.flush()
    logger.info("ingestion_sources_seeded", count=len(sources))


async def seed_events(session: object, days: int = 30) -> list[Event]:
    from sqlalchemy.ext.asyncio import AsyncSession
    sess: AsyncSession = session  # type: ignore
    now = datetime.now(UTC)
    events: list[Event] = []

    for day_offset in range(days):
        base_ts = now - timedelta(days=days - day_offset)
        n_events = rng.randint(3, 8)
        for _ in range(n_events):
            template = rng.choice(SAMPLE_HEADLINES)
            title, region, clss, sentiment, severity = template
            jitter_hours = rng.uniform(0, 23)
            occurred = base_ts + timedelta(hours=jitter_hours)
            ev = Event(
                content_hash=uuid.uuid4().hex,
                title=f"{title} [{day_offset}]",
                body=f"Detailed coverage of: {title}",
                url=f"https://example.com/news/{uuid.uuid4().hex[:8]}",
                source=rng.choice(["reuters", "bbc", "al_jazeera"]),
                region=region,
                occurred_at=occurred,
                ingested_at=occurred + timedelta(minutes=rng.randint(1, 15)),
                classification=clss,
                sentiment_score=sentiment + rng.uniform(-0.05, 0.05),
                severity_score=min(1.0, severity + rng.uniform(-0.05, 0.05)),
                entities=[region.replace("_", " ").title(), "UN", "NATO"],
                geo_risk_vector={region: round(severity, 2), "global": round(severity * 0.3, 2)},
            )
            events.append(ev)

    sess.add_all(events)
    await sess.flush()
    logger.info("events_seeded", count=len(events))
    return events


async def seed_gti_snapshots(session: object, days: int = 30) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.pipelines.gti_engine import GTIEngine
    sess: AsyncSession = session  # type: ignore
    now = datetime.now(UTC)
    engine = GTIEngine()

    for region in REGIONS:
        prev_gti = rng.uniform(10, 40)
        prev_ts = now - timedelta(days=days)
        snapshots = []
        for h in range(days * 24):
            ts = now - timedelta(hours=(days * 24 - h))
            result = engine.compute(
                events=[],
                prev_gti=prev_gti,
                prev_ts=prev_ts,
                region=region,
                now=ts,
            )
            # Add some random geopolitical "shocks"
            shock = rng.uniform(0, 3) if rng.random() < 0.1 else 0.0
            gti_val = result.gti_value + shock
            snap = GTISnapshot(
                ts=ts,
                region=region,
                gti_value=round(min(100.0, max(0.0, gti_val)), 4),
                gti_delta_1h=round(gti_val - prev_gti, 4),
                confidence=round(rng.uniform(0.4, 0.85), 3),
                top_drivers=[],
                calculation_version="1.0.0",
            )
            snapshots.append(snap)
            prev_gti = gti_val
            prev_ts = ts
        sess.add_all(snapshots)
        await sess.flush()
        logger.info("gti_snapshots_seeded", region=region, count=len(snapshots))


async def seed_market_data(session: object, days: int = 30) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession
    import math
    sess: AsyncSession = session  # type: ignore
    now = datetime.now(UTC)
    records = []

    for symbol, asset_class, region in ASSETS:
        base_price = rng.uniform(50, 500)
        prev_close = base_price
        for day in range(days):
            ts = now - timedelta(days=days - day)
            daily_return = rng.gauss(0.0002, 0.015)
            close = prev_close * (1 + daily_return)
            high = close * (1 + abs(rng.gauss(0, 0.006)))
            low = close * (1 - abs(rng.gauss(0, 0.006)))
            open_p = prev_close * (1 + rng.gauss(0, 0.003))
            # Parkinson's realized volatility estimator
            realized_vol = math.sqrt(1 / (4 * math.log(2))) * math.log(high / low) if low > 0 else 0.01
            md = MarketData(
                symbol=symbol,
                asset_class=asset_class,
                region=region,
                ts=ts,
                open=round(open_p, 4),
                high=round(high, 4),
                low=round(low, 4),
                close=round(close, 4),
                volume=round(rng.uniform(1e6, 1e8), 0),
                realized_vol=round(realized_vol, 6),
                return_1d=round(daily_return, 6),
                return_5d=round(daily_return * 5, 6),
            )
            records.append(md)
            prev_close = close

    sess.add_all(records)
    await sess.flush()
    logger.info("market_data_seeded", count=len(records))


async def seed_model_version(session: object) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.pipelines.market_model import feature_schema_hash
    sess: AsyncSession = session  # type: ignore
    mv = ModelVersion(
        model_name="vol_spike_lgbm",
        version="1.0.0",
        feature_schema_hash=feature_schema_hash(),
        artifact_path="./model_artifacts/vol_spike_lgbm.pkl",
        is_active=True,
        brier_score=0.18,
        metadata_={"training_samples": 2000, "notes": "surrogate model for MVP"},
    )
    session.add(mv)  # type: ignore
    await sess.flush()
    logger.info("model_version_seeded")


async def main() -> None:
    logger.info("starting_seed")
    async with get_db_session() as session:
        await seed_ingestion_sources(session)
        await seed_events(session, days=30)
        await seed_gti_snapshots(session, days=30)
        await seed_market_data(session, days=30)
        await seed_model_version(session)
    logger.info("seed_complete")


if __name__ == "__main__":
    asyncio.run(main())
