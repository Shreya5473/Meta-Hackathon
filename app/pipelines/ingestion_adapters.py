"""Ingestion adapters: base interface + RSS/Scraping/File implementations.

Expanded adapter set with comprehensive global news coverage and
a web scraping adapter for sources without RSS.
"""
from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RawArticle:
    title: str
    body: str | None
    url: str | None
    source: str
    published_at: datetime
    content_hash: str
    region: str = "global"
    raw_meta: dict[str, Any] | None = None

    @staticmethod
    def make_hash(title: str, body: str | None, url: str | None) -> str:
        payload = f"{title}|{body or ''}|{url or ''}"
        return hashlib.sha256(payload.encode()).hexdigest()[:64]


class BaseAdapter(ABC):
    """Pluggable adapter interface for data sources."""

    name: str
    adapter_type: str

    @abstractmethod
    async def fetch(self) -> list[RawArticle]:
        """Fetch articles from source. Must be idempotent."""

    async def health_check(self) -> bool:
        """Return True if source is reachable."""
        return True


class RSSAdapter(BaseAdapter):
    """RSS/Atom feed adapter with retry/backoff."""

    adapter_type = "rss"

    def __init__(self, name: str, url: str, region: str = "global") -> None:
        self.name = name
        self.url = url
        self.region = region

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, Exception)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    async def fetch(self) -> list[RawArticle]:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)

        articles: list[RawArticle] = []
        for entry in feed.entries[:50]:  # cap per run
            title = entry.get("title", "").strip()
            if not title:
                continue
            body = entry.get("summary") or entry.get("description")
            url = entry.get("link")
            published = self._parse_date(entry)
            content_hash = RawArticle.make_hash(title, body, url)
            articles.append(
                RawArticle(
                    title=title,
                    body=body[:2000] if body else None,
                    url=url,
                    source=self.name,
                    published_at=published,
                    content_hash=content_hash,
                    region=self.region,
                )
            )
        logger.info("rss_fetched", source=self.name, count=len(articles))
        return articles

    @staticmethod
    def _parse_date(entry: Any) -> datetime:
        import time
        from email.utils import parsedate_to_datetime
        for field in ("published_parsed", "updated_parsed"):
            ts = entry.get(field)
            if ts:
                return datetime.fromtimestamp(time.mktime(ts), tz=UTC)
        try:
            return parsedate_to_datetime(entry.get("published", ""))
        except Exception:
            return datetime.now(UTC)

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.head(self.url)
                return resp.status_code < 500
        except Exception:
            return False


class WebScrapingAdapter(BaseAdapter):
    """Simple HTML scraping adapter for sources without RSS feeds.

    Extracts headlines and summaries from HTML pages using regex patterns.
    Minimizes external dependencies — no Selenium/Playwright required.
    """

    adapter_type = "scraper"

    def __init__(
        self,
        name: str,
        url: str,
        region: str = "global",
        title_pattern: str = r"<h[23][^>]*>(.*?)</h[23]>",
        link_pattern: str = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>',
    ) -> None:
        self.name = name
        self.url = url
        self.region = region
        self.title_pattern = title_pattern
        self.link_pattern = link_pattern

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, Exception)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
    )
    async def fetch(self) -> list[RawArticle]:
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; GeoTradeBot/1.0; research project)",
                "Accept": "text/html,application/xhtml+xml",
            },
        ) as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
            html = resp.text

        # Extract titles
        titles = re.findall(self.title_pattern, html, re.DOTALL | re.IGNORECASE)
        # Clean HTML tags from titles
        titles = [re.sub(r"<[^>]+>", "", t).strip() for t in titles]
        titles = [t for t in titles if len(t) > 10][:30]

        articles: list[RawArticle] = []
        now = datetime.now(UTC)

        for title in titles:
            if not self._is_geopolitical(title):
                continue
            content_hash = RawArticle.make_hash(title, None, self.url)
            articles.append(
                RawArticle(
                    title=title,
                    body=None,
                    url=self.url,
                    source=self.name,
                    published_at=now,
                    content_hash=content_hash,
                    region=self.region,
                )
            )

        logger.info("scraper_fetched", source=self.name, count=len(articles))
        return articles

    @staticmethod
    def _is_geopolitical(title: str) -> bool:
        """Quick filter to keep only potentially geopolitical headlines."""
        keywords = {
            "war", "military", "sanction", "trade", "tariff", "oil", "gas",
            "nuclear", "missile", "attack", "invasion", "conflict", "tension",
            "embargo", "crisis", "election", "coup", "protest", "diplomacy",
            "treaty", "nato", "defense", "weapon", "drone", "cyber",
            "energy", "supply", "pipeline", "inflation", "recession",
            "central bank", "interest rate", "currency", "gold", "commodity",
        }
        lower = title.lower()
        return any(kw in lower for kw in keywords)


class FileAdapter(BaseAdapter):
    """Load articles from a JSONL file for testing/seeding."""

    adapter_type = "file"

    def __init__(self, name: str, path: str, region: str = "global") -> None:
        self.name = name
        self.path = path
        self.region = region

    async def fetch(self) -> list[RawArticle]:
        import json
        from pathlib import Path

        articles: list[RawArticle] = []
        p = Path(self.path)
        if not p.exists():
            logger.warning("file_adapter_not_found", path=self.path)
            return []
        with p.open() as f:
            for line in f:
                data = json.loads(line)
                title = data.get("title", "")
                body = data.get("body")
                url = data.get("url")
                published_raw = data.get("published_at", "")
                try:
                    published = datetime.fromisoformat(published_raw)
                    if published.tzinfo is None:
                        published = published.replace(tzinfo=UTC)
                except Exception:
                    published = datetime.now(UTC)
                articles.append(
                    RawArticle(
                        title=title,
                        body=body,
                        url=url,
                        source=self.name,
                        published_at=published,
                        content_hash=RawArticle.make_hash(title, body, url),
                        region=data.get("region", self.region),
                    )
                )
        logger.info("file_adapter_loaded", source=self.name, count=len(articles))
        return articles


# ── Registered adapters (pluggable config-driven) ─────────────────────────────

DEFAULT_ADAPTERS: list[BaseAdapter] = [
    # ── Major international news ──────────────────────────────────────────
    RSSAdapter("reuters_world", "https://feeds.reuters.com/reuters/worldNews", region="global"),
    RSSAdapter("bbc_world", "https://feeds.bbci.co.uk/news/world/rss.xml", region="global"),
    RSSAdapter("al_jazeera", "https://www.aljazeera.com/xml/rss/all.xml", region="middle_east"),
    RSSAdapter("ft_markets", "https://www.ft.com/rss/home/uk", region="europe"),

    # ── Regional coverage ─────────────────────────────────────────────────
    RSSAdapter("nyt_world", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", region="global"),
    RSSAdapter("guardian_world", "https://www.theguardian.com/world/rss", region="europe"),
    RSSAdapter("scmp_asia", "https://www.scmp.com/rss/91/feed", region="asia_pacific"),
    RSSAdapter("dw_world", "https://rss.dw.com/rdf/rss-en-world", region="europe"),

    # ── Defense / security ────────────────────────────────────────────────
    RSSAdapter("defense_one", "https://www.defenseone.com/rss/", region="global"),
    RSSAdapter("janes_news", "https://www.janes.com/feeds/news", region="global"),

    # ── Economic / market policy ──────────────────────────────────────────
    RSSAdapter("economist", "https://www.economist.com/rss", region="global"),
    RSSAdapter("cnbc_world", "https://www.cnbc.com/id/100727362/device/rss/rss.html", region="global"),
    RSSAdapter("bloomberg_markets", "https://feeds.bloomberg.com/markets/news.rss", region="global"),

    # ── Energy / commodities ──────────────────────────────────────────────
    RSSAdapter("oilprice", "https://oilprice.com/rss/main", region="global"),
    RSSAdapter("eia_updates", "https://www.eia.gov/rss/press_calendar.xml", region="americas"),

    # ── Africa ────────────────────────────────────────────────────────────
    RSSAdapter("bbc_africa", "https://feeds.bbci.co.uk/news/world/africa/rss.xml", region="africa"),

    # ── Americas ──────────────────────────────────────────────────────────
    RSSAdapter("bbc_latin", "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml", region="americas"),
]


def get_adapters() -> list[BaseAdapter]:
    return DEFAULT_ADAPTERS
