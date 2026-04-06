"""Geopolitical news ingestion layer.

Fetches news articles related to geopolitical events from structured JSON sources
like NewsAPI or specialized geopolitical data feeds.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class GeopoliticalArticle(BaseModel):
    title: str
    description: str | None
    url: str | None
    source: str
    published_at: datetime
    region: str = "global"
    category: str = "general"
    relevance_score: float = 0.5  # 0 to 1

class GeopoliticalNewsService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.newsapi_key.get_secret_value() if self.settings.newsapi_key else ""
        self.base_url = "https://newsapi.org/v2/everything"

    async def fetch_geopolitical_news(self, query: str = "geopolitics OR conflict OR sanctions OR trade war") -> list[GeopoliticalArticle]:
        """Fetch news articles matching geopolitical keywords."""
        if not self.api_key:
            logger.warning("NewsAPI key not configured. Skipping news fetch.")
            return self._get_fallback_news()

        cache_key = f"geopolitical_news_{query.replace(' ', '_')}"
        cached = await cache_get(cache_key)
        if cached:
            return [GeopoliticalArticle(**a) for a in cached]

        params = {
            "q": query,
            "apiKey": self.api_key,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.base_url, params=params)
                resp.raise_for_status()
                data = resp.json()
                
                articles: list[GeopoliticalArticle] = []
                for item in data.get("articles", []):
                    # Simple heuristic for relevance score (e.g. title length or keywords)
                    relevance = 0.5
                    if any(kw in item["title"].lower() for kw in ["war", "conflict", "sanction", "tension", "crisis"]):
                        relevance += 0.3
                        
                    articles.append(
                        GeopoliticalArticle(
                            title=item["title"],
                            description=item.get("description"),
                            url=item.get("url"),
                            source=item["source"]["name"],
                            published_at=datetime.fromisoformat(item["publishedAt"].replace("Z", "+00:00")),
                            region="global",  # In real implementation, extract from content
                            category="geopolitical",
                            relevance_score=min(1.0, relevance)
                        )
                    )
                
                await cache_set(cache_key, [a.model_dump(mode="json") for a in articles], ttl=1800)  # 30m cache
                return articles

        except Exception as e:
            logger.error(f"Error fetching NewsAPI articles: {e}")
            return self._get_fallback_news()

    def _get_fallback_news(self) -> list[GeopoliticalArticle]:
        """Provide fallback news articles."""
        now = datetime.now(UTC)
        return [
            GeopoliticalArticle(
                title="Global Trade Tensions Rise Amid New Sanctions",
                description="Economic sanctions introduced between major powers are expected to impact supply chains.",
                url=None,
                source="Fallback News",
                published_at=now - timedelta(hours=2),
                region="global",
                category="trade_restrictions",
                relevance_score=0.85
            ),
            GeopoliticalArticle(
                title="Middle East Energy Supply Disruption Warning",
                description="Tensions near major shipping lanes raise concerns about crude oil price volatility.",
                url=None,
                source="Fallback News",
                published_at=now - timedelta(hours=5),
                region="middle_east",
                category="energy_supply_disruption",
                relevance_score=0.92
            )
        ]

_news_service: GeopoliticalNewsService | None = None

def get_geopolitical_news_service() -> GeopoliticalNewsService:
    global _news_service
    if _news_service is None:
        _news_service = GeopoliticalNewsService()
    return _news_service
