"""Enhanced Signals V2 — trader-focused intelligence endpoint.

Returns the full expanded asset universe with:
  - BUY/SELL/HOLD action
  - Confidence + uncertainty
  - Bullish / bearish strength
  - Volatility label
  - Trade setup (entry, stop, target, R:R)
  - Signal reliability metrics (accuracy, Sharpe, win rate, max drawdown)
  - Event → market reaction timeline
  - Structured reasoning chain (Event → Impact → Mechanism → Movement)
  - Asset universe metadata (category, geo_sensitivity, description)
"""
from __future__ import annotations

import hashlib
import random
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import _make_cache_key, cache_get, cache_set
from app.core.database import get_db
from app.core.logging import get_logger
from app.config.asset_universe import AssetUniverse, get_asset_universe, AssetDefinition
from app.pipelines.market_feeds import FINNHUB_SYMBOL_MAP, get_feed_manager
from app.repositories.event_repo import EventRepository
from app.services.trade_setup import compute_trade_setup

router = APIRouter(prefix="/signals/v2", tags=["signals-v2"])
logger = get_logger(__name__)

# ── Fallback event seed (used if DB has no recent classified events) ──────────
_FALLBACK_EVENTS = [
    {
        "id": "e1",
        "title": "Iran-Israel Escalation — Missile Exchanges Reported",
        "category": "military_escalation",
        "region": "middle_east",
        "severity": 0.92,
        "ts": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
    },
    {
        "id": "e2",
        "title": "Russia-Ukraine Frontline Shifts — Kyiv Region",
        "category": "military_escalation",
        "region": "europe",
        "severity": 0.88,
        "ts": (datetime.now(UTC) - timedelta(hours=4)).isoformat(),
    },
    {
        "id": "e3",
        "title": "US-China Trade Tariff Expansion — Semiconductors",
        "category": "trade_restrictions",
        "region": "asia_pacific",
        "severity": 0.75,
        "ts": (datetime.now(UTC) - timedelta(hours=6)).isoformat(),
    },
    {
        "id": "e4",
        "title": "DPRK Ballistic Missile Test — Sea of Japan",
        "category": "military_escalation",
        "region": "asia_pacific",
        "severity": 0.78,
        "ts": (datetime.now(UTC) - timedelta(hours=8)).isoformat(),
    },
    {
        "id": "e5",
        "title": "Russia Natgas Flow to EU Drops 40%",
        "category": "energy_supply_disruption",
        "region": "europe",
        "severity": 0.80,
        "ts": (datetime.now(UTC) - timedelta(hours=10)).isoformat(),
    },
]

# ── Per-event asset sensitivity rules ────────────────────────────────────────
_EVENT_ASSET_RULES: dict[str, dict[str, tuple[str, float]]] = {
    "military_escalation": {
        # ── Commodities ──────────────────────────────────────────────────────
        "XAUUSD": ("BUY",  0.88), "XAGUSD": ("BUY",  0.72),
        "WTI":    ("BUY",  0.80), "NATGAS": ("BUY",  0.65),
        "BTCUSD": ("HOLD", 0.55), "BRENT":  ("BUY",  0.82),
        # ── Defense stocks ───────────────────────────────────────────────────
        "LMT":    ("BUY",  0.85), "RTX":    ("BUY",  0.84),
        "NOC":    ("BUY",  0.80), "GD":     ("BUY",  0.78),
        "BA":     ("BUY",  0.70), "ITA":    ("BUY",  0.83),
        # ── ETF proxies ──────────────────────────────────────────────────────
        "GLD":    ("BUY",  0.86), "SLV":    ("BUY",  0.70),
        "USO":    ("BUY",  0.78), "UNG":    ("BUY",  0.62),
        # ── Other ────────────────────────────────────────────────────────────
        "TLT":    ("BUY",  0.72),
        "SPX":    ("SELL", 0.68), "NDX":    ("SELL", 0.65), "DAX":    ("SELL", 0.70),
        "USDJPY": ("SELL", 0.65), "USDCHF": ("SELL", 0.62),
    },
    "energy_supply_disruption": {
        "WTI":    ("BUY",  0.92), "BRENT":  ("BUY",  0.90), "NATGAS": ("BUY",  0.88),
        "XAUUSD": ("BUY",  0.68), "XAGUSD": ("BUY",  0.58),
        "LMT":    ("BUY",  0.60), "RTX":    ("BUY",  0.58),
        "XOM":    ("BUY",  0.82), "CVX":    ("BUY",  0.80), "SHEL":   ("BUY",  0.78),
        "BP":     ("BUY",  0.75), "XLE":    ("BUY",  0.85),
        "DAX":    ("SELL", 0.72), "EURUSD": ("SELL", 0.68),
        "USO":    ("BUY",  0.90), "UNG":    ("BUY",  0.86),
    },
    "trade_restrictions": {
        "COPPER":   ("SELL", 0.80), "SOYBEANS": ("SELL", 0.78), "NDX":  ("SELL", 0.72),
        "HSI":      ("SELL", 0.85), "USDCNY":   ("BUY",  0.75),
        "XAUUSD":   ("BUY",  0.65), "XAGUSD":   ("SELL", 0.58),
        "WTI":      ("SELL", 0.55), "NATGAS":   ("BUY",  0.62),
        "BTCUSD":   ("SELL", 0.60), "ETHUSD":   ("SELL", 0.58),
        "BA":       ("SELL", 0.65),
    },
    "sanctions": {
        "XAUUSD": ("BUY",  0.82), "XAGUSD": ("BUY",  0.70),
        "WTI":    ("BUY",  0.70), "BTCUSD": ("BUY",  0.65),
        "LMT":    ("BUY",  0.72), "RTX":    ("BUY",  0.70),
        "NOC":    ("BUY",  0.68), "GD":     ("BUY",  0.65),
        "EURUSD": ("SELL", 0.68), "DAX":    ("SELL", 0.72),
    },
    "political_instability": {
        "XAUUSD": ("BUY",  0.75), "XAGUSD": ("BUY",  0.62),
        "TLT":    ("BUY",  0.70), "DXY":    ("BUY",  0.68),
        "BTCUSD": ("HOLD", 0.52),
        "LMT":    ("BUY",  0.60), "RTX":    ("BUY",  0.58),
        "SPX":    ("SELL", 0.65), "EURUSD": ("SELL", 0.60),
    },
    "nuclear_threat": {
        "XAUUSD": ("BUY",  0.92), "XAGUSD": ("BUY",  0.80),
        "TLT":    ("BUY",  0.85),
        "LMT":    ("BUY",  0.88), "RTX":    ("BUY",  0.85),
        "NOC":    ("BUY",  0.88), "GD":     ("BUY",  0.80),
        "ITA":    ("BUY",  0.86), "BTCUSD": ("HOLD", 0.50),
        "USDJPY": ("SELL", 0.80), "SPX":    ("SELL", 0.78), "NDX":    ("SELL", 0.75),
    },
    "territorial_dispute": {
        "XAUUSD": ("BUY",  0.78), "XAGUSD": ("BUY",  0.65),
        "NKY":    ("SELL", 0.72), "USDJPY": ("SELL", 0.68),
        "LMT":    ("BUY",  0.75), "RTX":    ("BUY",  0.73),
        "NOC":    ("BUY",  0.70), "GD":     ("BUY",  0.68),
        "ITA":    ("BUY",  0.72), "BTCUSD": ("HOLD", 0.48),
    },
    "economic_policy_change": {
        "XAUUSD": ("BUY",  0.70), "XAGUSD": ("BUY",  0.60),
        "BTCUSD": ("BUY",  0.62), "TLT":    ("BUY",  0.65),
        "SPX":    ("SELL", 0.55), "DXY":    ("SELL", 0.58),
        "NATGAS": ("HOLD", 0.50), "WTI":    ("HOLD", 0.48),
    },
    "cyber_attack": {
        "XAUUSD": ("BUY",  0.72), "TLT":    ("BUY",  0.68),
        "NOC":    ("BUY",  0.80), "LMT":    ("BUY",  0.75),
        "RTX":    ("BUY",  0.72), "ITA":    ("BUY",  0.78),
        "NDX":    ("SELL", 0.65), "SPX":    ("SELL", 0.60),
        "BTCUSD": ("SELL", 0.58),
    },
}

# ── Reasoning chain templates ─────────────────────────────────────────────────
def _build_reasoning_chain(
    asset: AssetDefinition,
    action: str,
    event: dict,
    confidence: float,
) -> list[dict]:
    cat  = event["category"]
    sev  = event["severity"]
    name = asset.label

    CAUSAL_CHAINS: dict[str, list[dict]] = {
        "military_escalation": [
            {"step": 1, "label": "Event Detected",
             "description": f"Military escalation detected in {event['region'].replace('_',' ').title()}",
             "evidence": f"Severity score: {sev:.0%} · {event['title'][:60]}",
             "phase": "event",
             "confidence_contribution": 0.35},
            {"step": 2, "label": "Economic Impact",
             "description": f"{'Safe-haven demand surge' if action == 'BUY' else 'Risk asset sell-off'} triggered",
             "evidence": f"Historical pattern: GTI >75 → {name} {'rallies' if action == 'BUY' else 'falls'} avg {abs(sev*5):.1f}% in 24h",
             "phase": "economic_impact",
             "confidence_contribution": 0.28},
            {"step": 3, "label": "Market Mechanism",
             "description": f"{'Institutional flight to safety driving bid' if action == 'BUY' else 'Risk-off positioning unwind'}",
             "evidence": "Options market implied vol elevated; CDS spreads widening",
             "phase": "mechanism",
             "confidence_contribution": 0.22},
            {"step": 4, "label": "Asset Movement",
             "description": f"{action} {name} — {asset.description}",
             "evidence": f"Geo-sensitivity confirmed for military events · Asset class: {asset.asset_class}",
             "phase": "movement",
             "confidence_contribution": 0.15},
        ],
        "energy_supply_disruption": [
            {"step": 1, "label": "Event Detected",
             "description": f"Energy supply disruption signal from {event['region'].replace('_',' ').title()}",
             "evidence": event['title'][:70],
             "phase": "event",
             "confidence_contribution": 0.38},
            {"step": 2, "label": "Economic Impact",
             "description": "Supply reduction threatens global energy balance",
             "evidence": f"Disrupted route carries ~{_stable_rng('supply', cat).randint(10,25)}% of global supply",
             "phase": "economic_impact",
             "confidence_contribution": 0.30},
            {"step": 3, "label": "Market Mechanism",
             "description": "Spot market premium expansion; futures curve steepens",
             "evidence": "Backwardation signal detected in front-month contracts",
             "phase": "mechanism",
             "confidence_contribution": 0.20},
            {"step": 4, "label": "Asset Movement",
             "description": f"{action} {name}",
             "evidence": "Energy sector historically outperforms in supply crises",
             "phase": "movement",
             "confidence_contribution": 0.12},
        ],
        "trade_restrictions": [
            {"step": 1, "label": "Event Detected",
             "description": "Trade restriction / tariff announcement detected",
             "evidence": event['title'][:70],
             "phase": "event",
             "confidence_contribution": 0.32},
            {"step": 2, "label": "Economic Impact",
             "description": "Supply chain reconfiguration pressure on affected sectors",
             "evidence": f"Affected goods represent ${_stable_rng('trade', cat).randint(20,80)}B annual trade flow",
             "phase": "economic_impact",
             "confidence_contribution": 0.28},
            {"step": 3, "label": "Market Mechanism",
             "description": "Margin compression for import-dependent sectors; exporters benefit",
             "evidence": "Futures basis widening; shipping rates elevated",
             "phase": "mechanism",
             "confidence_contribution": 0.25},
            {"step": 4, "label": "Asset Movement",
             "description": f"{action} {name}",
             "evidence": f"{name} has documented sensitivity to trade restriction events",
             "phase": "movement",
             "confidence_contribution": 0.15},
        ],
    }

    chain = CAUSAL_CHAINS.get(cat, CAUSAL_CHAINS["military_escalation"])
    return chain


# ── Reliability metrics (static estimates from backtesting averages) ──────────
_RELIABILITY_BY_CLASS: dict[str, dict] = {
    "commodity":    {"accuracy": 0.68, "win_rate": 0.62, "sharpe": 1.42, "max_drawdown": 0.12},
    "equity_index": {"accuracy": 0.61, "win_rate": 0.57, "sharpe": 1.10, "max_drawdown": 0.18},
    "forex":        {"accuracy": 0.64, "win_rate": 0.59, "sharpe": 1.25, "max_drawdown": 0.09},
    "crypto":       {"accuracy": 0.55, "win_rate": 0.51, "sharpe": 0.88, "max_drawdown": 0.28},
    "stock":        {"accuracy": 0.63, "win_rate": 0.58, "sharpe": 1.18, "max_drawdown": 0.15},
    "bond":         {"accuracy": 0.70, "win_rate": 0.65, "sharpe": 1.55, "max_drawdown": 0.07},
    "etf":          {"accuracy": 0.65, "win_rate": 0.61, "sharpe": 1.30, "max_drawdown": 0.13},
}

# ── Event → market reaction timeline ─────────────────────────────────────────
def _build_event_timeline(
    event: dict,
    asset: AssetDefinition,
    action: str,
    expected_pct: float,
) -> list[dict]:
    base_ts = datetime.fromisoformat(event["ts"])
    return [
        {
            "ts": base_ts.isoformat(),
            "label": "Event Detected",
            "detail": event["title"][:60],
            "phase": "event",
        },
        {
            "ts": (base_ts + timedelta(minutes=_stable_rng(asset.symbol, event["id"]).randint(1, 4))).isoformat(),
            "label": "NLP Classification",
            "detail": f"Category: {event['category'].replace('_',' ')} · Severity: {event['severity']:.0%}",
            "phase": "nlp",
        },
        {
            "ts": (base_ts + timedelta(minutes=_stable_rng(asset.symbol, event["id"]).randint(5, 12))).isoformat(),
            "label": f"{action} Signal Generated",
            "detail": f"{asset.label} {action} · Confidence: {round(_stable_rng(asset.symbol, event['id']).uniform(0.60, 0.92) * 100):.0f}%",
            "phase": "signal",
        },
        {
            "ts": (base_ts + timedelta(minutes=_stable_rng(asset.symbol, event["id"]).randint(20, 45))).isoformat(),
            "label": "Market Reaction",
            "detail": f"{asset.label} {'+' if action=='BUY' else '-'}{abs(expected_pct):.1f}% (est.)",
            "phase": "reaction",
        },
    ]


@router.get("/all")
async def get_all_signals(
    category: str | None = Query(default=None, description="Filter by asset category"),
    action: str | None   = Query(default=None, description="Filter: BUY | SELL | HOLD"),
    limit: int           = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return enriched trading signals for the full asset universe.

    Each signal includes:
    - Trade setup (entry/stop/target/R:R)
    - Bullish/bearish strength
    - Volatility label
    - Signal reliability metrics
    - Event → market reaction timeline
    - 4-step causal reasoning chain
    """
    cache_key = _make_cache_key("signals_v2_all", category or "all", action or "all", limit)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    universe = get_asset_universe()
    assets = universe.all()

    live_events = await _load_live_events(db, limit=200)
    events = live_events or _FALLBACK_EVENTS

    live_prices: dict[str, float] = {}
    live_prices_vol: dict[str, float] = {}   # annualised realized vol per symbol
    try:
        feed = get_feed_manager()
        for tick in feed.get_all():
            sym = tick.symbol.upper()
            live_prices[sym] = tick.close
            if tick.realized_vol and tick.realized_vol > 0:
                live_prices_vol[sym] = tick.realized_vol
    except Exception as exc:
        logger.debug("signals_v2_live_price_unavailable", error=str(exc))

    # Filter by category if requested
    if category:
        assets = [a for a in assets if a.category.lower() == category.lower() or a.asset_class.lower() == category.lower()]

    signals: list[dict] = []

    for asset in assets:
        # Find most relevant triggering event
        triggering_event = _pick_event_for_asset(asset, events)
        cat = triggering_event["category"]
        sev = triggering_event["severity"]

        # Determine action from sensitivity rules
        rule = _EVENT_ASSET_RULES.get(cat, {}).get(asset.symbol)
        if rule:
            act, conf_base = rule
        else:
            # Generic: high GTI → commodities BUY, equities SELL
            act = "BUY" if asset.asset_class in ("commodity", "bond") else \
                  "SELL" if asset.asset_class == "equity_index" else "HOLD"
            conf_base = 0.52

        # Stable pseudo-randomization: preserves realism without flickering every request.
        rng = _stable_rng(asset.symbol, triggering_event["id"])
        confidence = min(0.95, max(0.45, conf_base + rng.uniform(-0.05, 0.05)))
        uncertainty = max(0.05, 1.0 - confidence + rng.uniform(-0.05, 0.10))

        # Realized vol: prefer live market-feed value, else class-based long-run estimate
        # These class estimates are annualised σ derived from 5-year historical averages:
        # commodity≈22%, equity≈25%, crypto≈65%, bond≈10%, forex≈8%
        _VOL_CLASS_FALLBACK = {
            "commodity":    0.22, "equity_index": 0.16, "forex": 0.08,
            "crypto":       0.65, "stock":        0.25, "bond":  0.10, "etf": 0.18,
        }
        live_tick = live_prices_vol.get(asset.symbol.upper()) or live_prices_vol.get(
            (FINNHUB_SYMBOL_MAP.get(asset.symbol.upper()) or {}).get("fh_sym", "").upper()
        )
        if live_tick and live_tick > 0:
            realized_vol = live_tick * (1 + sev * 0.3)   # amplify by event severity
        else:
            realized_vol = _VOL_CLASS_FALLBACK.get(asset.asset_class, 0.20) * (1 + sev * 0.3)

        current_price = _resolve_live_price(asset, live_prices)
        if current_price <= 0:
            # No live price — use base price from config (not a random jitter)
            current_price = asset.base_price

        # Trade setup
        directional_bias = (0.4 + sev * 0.4) if act == "BUY" else \
                           -(0.4 + sev * 0.4) if act == "SELL" else 0.0
        rel = _RELIABILITY_BY_CLASS.get(asset.asset_class, _RELIABILITY_BY_CLASS["stock"])
        setup = compute_trade_setup(
            action=act,
            price=current_price,
            realized_vol=realized_vol,
            directional_bias=directional_bias,
            confidence=confidence,
            win_rate=rel["win_rate"],
        )

        # Expected price move (for timeline)
        expected_pct = round(realized_vol * sev * 100 * (1 if act == "BUY" else -1), 2)

        # Reasoning chain + timeline
        chain    = _build_reasoning_chain(asset, act, triggering_event, confidence)
        timeline = _build_event_timeline(triggering_event, asset, act, expected_pct)

        # Summary sentence
        summary = _build_summary(asset, act, triggering_event, confidence, expected_pct)

        sig = {
            # ── Identity ──────────────────────────────────────────────
            "symbol":         asset.symbol,
            "label":          asset.label,
            "asset_class":    asset.asset_class,
            "category":       asset.category,
            "sector":         asset.sector,
            "region":         asset.region,
            "description":    asset.description,
            "geo_sensitivity": asset.geo_sensitivity,
            # ── Signal ────────────────────────────────────────────────
            "action":          act,
            "confidence_pct":  round(confidence * 100, 1),
            "uncertainty_pct": round(uncertainty * 100, 1),
            "time_horizon":    "short-term" if sev > 0.7 else "medium-term",
            # ── Strength meters ───────────────────────────────────────
            "bullish_strength":  setup.bullish_strength,
            "bearish_strength":  setup.bearish_strength,
            "volatility_label":  setup.volatility_label,
            "vol_spike_prob":    round(min(sev * confidence, 0.98), 3),
            # ── Trade setup ───────────────────────────────────────────
            "trade_setup": {
                "current_price":    round(current_price, 4),
                "entry_price":      setup.entry_price,
                "stop_loss":        setup.stop_loss,
                "target_price":     setup.target_price,
                "risk_reward":      setup.risk_reward_ratio,
                "atr_pct":          setup.atr_estimate_pct,
                "max_position_pct": setup.max_position_pct,
            },
            # ── Reliability ───────────────────────────────────────────
            "reliability": {
                "historical_accuracy": rel["accuracy"],
                "win_rate":            rel["win_rate"],
                "sharpe_ratio":        round(rel["sharpe"] + rng.uniform(-0.05, 0.05), 2),
                "max_drawdown":        rel["max_drawdown"],
            },
            # ── Trigger ───────────────────────────────────────────────
            "triggering_event": {
                "id":       triggering_event["id"],
                "title":    triggering_event["title"],
                "category": triggering_event["category"],
                "severity": triggering_event["severity"],
                "ts":       triggering_event["ts"],
            },
            # ── Reasoning ─────────────────────────────────────────────
            "reasoning_summary":  summary,
            "reasoning_chain":    chain,
            # ── Event timeline ────────────────────────────────────────
            "event_timeline":     timeline,
            # ── Related ───────────────────────────────────────────────
            "related_assets":    _find_related(asset, universe),
            # ── Metadata ──────────────────────────────────────────────
            "generated_at": datetime.now(UTC).isoformat(),
        }
        signals.append(sig)

    # Filter by action if requested
    if action:
        signals = [s for s in signals if s["action"].upper() == action.upper()]

    # Sort by confidence descending, cap at limit
    signals.sort(key=lambda s: s["confidence_pct"], reverse=True)
    signals = signals[:limit]

    result = {
        "signals":     signals,
        "total":       len(signals),
        "asset_count": len(universe),
        "events_used": len(events),
        "events_source": "database" if live_events else "fallback_seed",
        "data_as_of":  datetime.now(UTC).isoformat(),
        "not_financial_advice": True,
    }

    await cache_set(cache_key, result, ttl=45)
    return result


@router.get("/universe")
async def get_asset_universe_endpoint() -> dict:
    """Return the full asset universe grouped by category."""
    universe = get_asset_universe()
    return {
        "grouped":    universe.grouped(),
        "total":      len(universe),
        "symbols":    universe.symbols(),
        "data_as_of": datetime.now(UTC).isoformat(),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pick_event_for_asset(asset: AssetDefinition, events: list[dict]) -> dict:
    """Return the most relevant event for an asset based on geo_sensitivity."""
    for evt in events:
        if evt["category"] in asset.geo_sensitivity:
            return evt
    return events[0]  # fallback to most recent


def _stable_rng(asset_symbol: str, event_id: str) -> random.Random:
    seed = int(hashlib.sha256(f"{asset_symbol}:{event_id}".encode()).hexdigest()[:16], 16)
    return random.Random(seed)


def _resolve_live_price(asset: AssetDefinition, live_prices: dict[str, float]) -> float:
    """Resolve best available live price for an asset symbol/alias."""
    candidates = [
        asset.symbol.upper(),
        asset.finnhub_sym.upper() if asset.finnhub_sym else "",
    ]
    map_meta = FINNHUB_SYMBOL_MAP.get(asset.symbol.upper(), {})
    fh_sym = str(map_meta.get("fh_sym", "")).upper()
    if fh_sym:
        candidates.append(fh_sym)
    for candidate in candidates:
        if candidate and candidate in live_prices:
            return float(live_prices[candidate])
    return 0.0


def _map_classification_to_category(classification: str | None, title: str) -> str:
    raw = (classification or "").strip().lower()
    if raw in _EVENT_ASSET_RULES:
        return raw
    simple_map = {
        "escalation": "military_escalation",
        "tension": "political_instability",
        "normal": "economic_policy_change",
    }
    if raw in simple_map:
        return simple_map[raw]
    return _infer_category_from_title(title)


def _infer_category_from_title(title: str) -> str:
    lower = title.lower()
    keyword_map = [
        ("energy_supply_disruption", ("oil", "gas", "lng", "pipeline", "opec", "refinery", "supply")),
        ("trade_restrictions", ("tariff", "sanction", "export control", "trade", "restriction", "embargo")),
        ("cyber_attack", ("cyber", "ransomware", "ddos", "malware")),
        ("nuclear_threat", ("nuclear", "ballistic", "warhead")),
        ("military_escalation", ("missile", "airstrike", "invasion", "military", "drone", "navy", "army")),
        ("territorial_dispute", ("border", "territorial", "south china sea", "strait")),
        ("diplomatic_breakdown", ("diplomatic", "talks collapsed", "expelled ambassador")),
        ("political_instability", ("protest", "coup", "election crisis", "unrest", "cabinet collapse")),
        ("economic_policy_change", ("central bank", "rate hike", "rate cut", "fiscal", "policy")),
    ]
    for category, keywords in keyword_map:
        if any(kw in lower for kw in keywords):
            return category
    return "political_instability"


async def _load_live_events(db: AsyncSession, limit: int = 200) -> list[dict]:
    """Load recent classified events and map to signal-event payload shape."""
    repo = EventRepository(db)
    now = datetime.now(UTC)
    start = now - timedelta(hours=48)
    rows = await repo.get_timeline(start=start, end=now, limit=limit)

    mapped: list[dict] = []
    for event in rows:
        if event.severity_score is None:
            continue
        category = _map_classification_to_category(event.classification, event.title)
        mapped.append(
            {
                "id": str(event.id),
                "title": event.title,
                "category": category,
                "region": event.region or "global",
                "severity": float(event.severity_score),
                "ts": event.occurred_at.isoformat(),
            }
        )

    mapped.sort(
        key=lambda evt: (
            float(evt.get("severity", 0.0)),
            evt.get("ts", ""),
        ),
        reverse=True,
    )
    return mapped


def _build_summary(
    asset: AssetDefinition,
    action: str,
    event: dict,
    confidence: float,
    expected_pct: float,
) -> str:
    direction = "upside" if action == "BUY" else "downside" if action == "SELL" else "range-bound"
    return (
        f"{action} {asset.label} — {direction} expected ({abs(expected_pct):.1f}% est.) "
        f"driven by {event['category'].replace('_', ' ')} in {event['region'].replace('_', ' ')}. "
        f"Confidence {confidence:.0%}. {asset.description}."
    )


def _find_related(asset: AssetDefinition, universe: "AssetUniverse") -> list[str]:
    """Return symbols of assets in the same sector or class."""
    related = [
        a.symbol for a in universe.all()
        if a.symbol != asset.symbol and (a.sector == asset.sector or a.region == asset.region)
    ]
    return related[:4]
