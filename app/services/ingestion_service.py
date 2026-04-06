"""Ingestion service — dedup + NLP processing of raw articles."""
from __future__ import annotations

from datetime import UTC, datetime

from rapidfuzz import fuzz

from app.core.logging import get_logger
from app.models.event import Event
from app.pipelines.ingestion_adapters import RawArticle
from app.pipelines.nlp_pipeline import get_nlp_pipeline
from app.repositories.event_repo import EventRepository

logger = get_logger(__name__)

FUZZY_SIMILARITY_THRESHOLD = 85  # 0-100 rapidfuzz ratio


class IngestionService:
    """Processes RawArticle → Event with deduplication and NLP annotation."""

    def __init__(self, event_repo: EventRepository) -> None:
        self.event_repo = event_repo

    async def process_articles(
        self, articles: list[RawArticle], run_nlp: bool = True
    ) -> tuple[int, int]:
        """Return (new_count, duplicate_count)."""
        new_count = 0
        dup_count = 0

        for article in articles:
            # 1. Exact dedup by content hash
            existing = await self.event_repo.get_by_content_hash(article.content_hash)
            if existing is not None:
                dup_count += 1
                continue

            # 2. Fuzzy title dedup against very recent events (last 6h)
            if await self._is_fuzzy_duplicate(article.title):
                logger.debug("fuzzy_duplicate_skipped", title=article.title[:80])
                dup_count += 1
                continue

            # 3. Build Event
            event = Event(
                content_hash=article.content_hash,
                title=article.title,
                body=article.body,
                url=article.url,
                source=article.source,
                region=article.region,
                occurred_at=article.published_at,
                ingested_at=datetime.now(UTC),
            )

            # 4. NLP annotation (inline for now; async task in production)
            if run_nlp:
                try:
                    nlp = get_nlp_pipeline()
                    result = nlp.process(article.title, article.body)
                    # Persist detailed event class so downstream signal mapping
                    # can use categories like "energy_supply_disruption".
                    event.classification = result.classification_detail or result.classification
                    event.sentiment_score = result.sentiment_score
                    event.severity_score = result.severity_score
                    event.entities = result.entities
                    event.geo_risk_vector = result.geo_risk_vector
                    event.embedding = result.embedding
                except Exception as exc:
                    logger.warning("nlp_failed", error=str(exc), title=article.title[:80])

            await self.event_repo.create(event)
            new_count += 1

        return new_count, dup_count

    async def _is_fuzzy_duplicate(self, title: str) -> bool:
        """Check recent events for near-duplicate titles."""
        from datetime import timedelta
        since = datetime.now(UTC) - timedelta(hours=6)
        recent = await self.event_repo.get_active_events(since)
        for ev in recent:
            similarity = fuzz.token_set_ratio(title.lower(), ev.title.lower())
            if similarity >= FUZZY_SIMILARITY_THRESHOLD:
                return True
        return False
