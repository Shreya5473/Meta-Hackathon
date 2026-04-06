"""GTI computation engine.

Algorithm:
  gti(t) = gti(t-1) * exp(-λ * Δt_hours) + Σ weighted_event_contributions(t)

Where:
  - λ = decay constant (default 0.05/hour → half-life ≈ 14h)
  - event contributions = severity * sentiment_factor * region_weight * recency_factor
  - confidence = f(event_count, recency, coverage)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Maximum possible GTI value (clamp output to this)
GTI_MAX = 100.0
GTI_MIN = 0.0


@dataclass
class EventContribution:
    event_id: UUID
    severity: float
    sentiment_factor: float
    region_weight: float
    region: str
    age_hours: float
    contribution: float


@dataclass
class GTIResult:
    region: str
    gti_value: float
    gti_delta_1h: float
    confidence: float
    top_drivers: list[dict[str, Any]]
    calculation_version: str
    ts: datetime


def _decay_factor(age_hours: float, lambda_: float) -> float:
    """Exponential decay weight for an event of given age."""
    return math.exp(-lambda_ * age_hours)


def _sentiment_to_factor(sentiment_score: float) -> float:
    """Convert -1..1 sentiment to 0..1 tension factor.
    Negative sentiment → higher tension.
    """
    return max(0.0, (1.0 - sentiment_score) / 2.0)


def _confidences(event_contributions: list[EventContribution], window_hours: float) -> float:
    """Confidence metric based on event count and recency coverage."""
    n = len(event_contributions)
    if n == 0:
        return 0.0
    # Count events within first quarter of window (very recent)
    very_recent = sum(1 for e in event_contributions if e.age_hours < window_hours / 4)
    # Sigmoid-like confidence from event count + recency ratio
    count_conf = min(1.0, n / 20.0)  # 20 events → full confidence
    recency_conf = very_recent / max(1, n)
    return float(0.6 * count_conf + 0.4 * recency_conf)


class GTIEngine:
    """Stateless GTI calculation engine.

    Usage:
        engine = GTIEngine()
        result = engine.compute(events, prev_gti=prev_snapshot)
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.lambda_ = settings.gti_decay_lambda
        self.version = settings.gti_version

    def compute(
        self,
        events: list[dict[str, Any]],  # list of event dicts with required fields
        prev_gti: float | None = None,
        prev_ts: datetime | None = None,
        region: str = "global",
        window_hours: float = 72.0,
        now: datetime | None = None,
    ) -> GTIResult:
        now = now or datetime.now(UTC)

        # 1. Decay previous GTI
        if prev_gti is not None and prev_ts is not None:
            delta_hours = (now - prev_ts).total_seconds() / 3600.0
            decayed_base = prev_gti * _decay_factor(delta_hours, self.lambda_)
        else:
            decayed_base = 0.0

        # 2. Compute contributions from recent events
        contributions: list[EventContribution] = []
        cutoff = now - timedelta(hours=window_hours)

        for ev in events:
            occurred_at = ev.get("occurred_at")
            if occurred_at is None:
                continue
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=UTC)
            if occurred_at < cutoff:
                continue

            age_hours = (now - occurred_at).total_seconds() / 3600.0
            severity = float(ev.get("severity_score") or 0.3)
            sentiment = float(ev.get("sentiment_score") or 0.0)
            geo_vec: dict[str, float] = ev.get("geo_risk_vector") or {"global": 1.0}

            # Region weight: direct region match OR global contribution
            region_weight = geo_vec.get(region, geo_vec.get("global", 0.1))

            sent_factor = _sentiment_to_factor(sentiment)
            decay = _decay_factor(age_hours, self.lambda_)

            # Raw contribution: 0-10 scale per event
            raw_contribution = 10.0 * severity * sent_factor * region_weight * decay

            contributions.append(
                EventContribution(
                    event_id=ev["id"],
                    severity=severity,
                    sentiment_factor=sent_factor,
                    region_weight=region_weight,
                    region=str(ev.get("region", "global")),
                    age_hours=age_hours,
                    contribution=raw_contribution,
                )
            )

        # 3. Sum all contributions (additive on top of decayed base)
        total_new = sum(c.contribution for c in contributions)
        gti_raw = decayed_base + total_new
        gti_value = float(max(GTI_MIN, min(GTI_MAX, gti_raw)))

        # 4. GTI delta vs 1h ago (approximate from decay)
        gti_delta_1h = gti_value - (prev_gti or 0.0) * _decay_factor(1.0, self.lambda_)

        # 5. Confidence
        confidence = _confidences(contributions, window_hours)

        # 6. Top drivers (top-5 by contribution, descending)
        top_drivers = sorted(contributions, key=lambda c: c.contribution, reverse=True)[:5]
        top_drivers_out = [
            {
                "event_id": str(td.event_id),
                "contribution_weight": round(td.contribution / max(1.0, total_new), 4),
                "region": td.region,
            }
            for td in top_drivers
        ]

        logger.debug(
            "gti_computed",
            region=region,
            gti_value=gti_value,
            event_count=len(contributions),
            confidence=confidence,
        )

        return GTIResult(
            region=region,
            gti_value=round(gti_value, 4),
            gti_delta_1h=round(gti_delta_1h, 4),
            confidence=round(confidence, 4),
            top_drivers=top_drivers_out,
            calculation_version=self.version,
            ts=now,
        )


# Module-level singleton
_gti_engine: GTIEngine | None = None


def get_gti_engine() -> GTIEngine:
    global _gti_engine  # noqa: PLW0603
    if _gti_engine is None:
        _gti_engine = GTIEngine()
    return _gti_engine
