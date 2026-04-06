"""Enhanced trading signal generator.

Combines ML model outputs with the Impact Graph propagation to produce
rich, explainable BUY/SELL/HOLD trading signals with full reasoning chains.

Each signal includes:
    - Asset name and class
    - BUY/SELL/HOLD indicator
    - Confidence score (0–100%)
    - Uncertainty estimate
    - Reasoning chain (multi-step causal explanation)
    - Triggering geopolitical event
    - Impact graph path (how the shock reaches this asset)
    - Historical context
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.pipelines.impact_graph import ImpactGraph, PropagationResult, get_impact_graph
from app.pipelines.live_indicators import FinnhubLiveIndicators
from app.pipelines.market_model import (
    AssetFeatures,
    AssetImpactResult,
    MarketImpactModel,
    get_impact_model,
)

logger = get_logger(__name__)


# ── Event category classification labels (expanded) ─────────────────────────

EVENT_CATEGORIES = [
    "military_escalation",
    "sanctions",
    "trade_restrictions",
    "energy_supply_disruption",
    "cyber_attack",
    "political_instability",
    "economic_policy_change",
    "diplomatic_breakdown",
    "territorial_dispute",
    "nuclear_threat",
    "refugee_crisis",
    "election_uncertainty",
    "central_bank_action",
    "supply_chain_disruption",
]

# Map NLP classification → event categories for the signal generator
_CLASSIFICATION_TO_CATEGORY: dict[str, str] = {
    "escalation": "military_escalation",
    "tension": "political_instability",
    "normal": "economic_policy_change",
}


@dataclass
class ReasoningStep:
    """Single step in the AI reasoning chain."""
    step_number: int
    description: str
    evidence: str
    confidence_contribution: float


@dataclass
class TradingSignal:
    """Rich trading signal with full reasoning chain."""
    asset: str
    asset_class: str  # commodity / equity / currency / bond
    action: str  # BUY / SELL / HOLD
    confidence_pct: float  # 0–100
    uncertainty_pct: float  # 0–100
    reasoning_summary: str
    reasoning_chain: list[ReasoningStep]
    triggering_event: str  # title of the geopolitical event
    event_category: str
    impact_path: list[str]  # graph path from event to asset
    vol_spike_prob: float
    directional_bias: float
    sector_stress: float
    price_direction: str  # "up" / "down" / "neutral"
    expected_magnitude: str  # "minimal" / "moderate" / "significant" / "severe"
    time_horizon: str  # "short-term" / "medium-term" / "long-term"
    related_assets: list[str]  # other assets affected by same event
    signal: str | None = None  # Alias for action for frontend compatibility
    bullish_strength: float = 0.0
    bearish_strength: float = 0.0
    volatility: str = "MEDIUM"  # LOW / MEDIUM / HIGH
    
    # Trade setup
    entry: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0
    risk_reward: float = 0.0
    atr: float = 0.0
    max_position: float = 0.0
    
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self):
        if self.signal is None:
            self.signal = self.action.upper()
        # Ensure Bullish + Bearish = 100%
        if self.bullish_strength + self.bearish_strength == 0:
            self.bullish_strength = (self.directional_bias + 1) * 50
            self.bearish_strength = 100 - self.bullish_strength


@dataclass
class SignalBatch:
    """Batch of trading signals from a single event or computation cycle."""
    signals: list[TradingSignal]
    global_tension_index: float
    event_count: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class TradingSignalGenerator:
    """Generates explainable trading signals by combining ML model
    outputs with graph-based impact propagation."""

    def __init__(
        self,
        impact_model: MarketImpactModel | None = None,
        impact_graph: ImpactGraph | None = None,
    ) -> None:
        self.model = impact_model or get_impact_model()
        self.graph = impact_graph or get_impact_graph()

    def generate_signals_for_event(
        self,
        event_title: str,
        event_category: str,
        source_country: str,
        severity: float,
        gti_value: float,
        gti_delta: float,
        gti_confidence: float,
        assets: list[str] | None = None,
        asset_meta: dict[str, dict[str, Any]] | None = None,
        live_indicators: dict[str, dict[str, float]] | None = None,
    ) -> SignalBatch:
        """Generate trading signals triggered by a specific geopolitical event.

        Parameters
        ----------
        live_indicators:
            Optional pre-fetched Finnhub technical indicators keyed by symbol,
            e.g. ``{"SPY": {"rsi_14": 0.6, "macd_signal_diff": 0.01, "bb_pct_b": 0.7}}``.
            If provided, values are injected into the ML feature vector for each asset.
        """

        # Step 1: Propagate shock through impact graph
        propagation = self.graph.propagate_shock(
            source_country=source_country,
            event_type=event_category,
            severity=severity,
        )

        # Step 2: Determine affected assets
        if assets is None:
            # Use graph-propagated assets
            assets = [
                ai.node_id for ai in propagation.asset_impacts
                if ai.impact_score > 0.05
            ]
            if not assets:
                assets = [
                    "XAUUSD", "XAGUSD", "WTI", "NATGAS", "BTCUSD",
                    "LMT", "RTX", "NOC", "GD", "BA", "ITA",
                ]

        meta = asset_meta or {}
        live_inds = live_indicators or {}
        signals: list[TradingSignal] = []

        for asset in assets:
            signal = self._generate_single_signal(
                asset=asset,
                event_title=event_title,
                event_category=event_category,
                source_country=source_country,
                severity=severity,
                gti_value=gti_value,
                gti_delta=gti_delta,
                gti_confidence=gti_confidence,
                propagation=propagation,
                asset_meta=meta.get(asset, {}),
                live_indicators=live_inds.get(asset),
            )
            if signal is not None:
                signals.append(signal)

        # Sort by confidence descending
        signals.sort(key=lambda s: s.confidence_pct, reverse=True)

        return SignalBatch(
            signals=signals,
            global_tension_index=gti_value,
            event_count=1,
        )

    def generate_periodic_signals(
        self,
        events: list[dict[str, Any]],
        gti_value: float,
        gti_delta: float,
        gti_confidence: float,
        assets: list[str] | None = None,
    ) -> SignalBatch:
        """Generate signals from multiple recent events for periodic computation."""
        if assets is None:
            assets = [
                "XAUUSD", "XAGUSD", "WTI", "NATGAS", "BTCUSD",
                "LMT", "RTX", "NOC", "GD", "BA", "ITA",
                "SPY", "QQQ", "TLT", "XLE", "XLF",
            ]

        all_signals: list[TradingSignal] = []

        for event in events:
            category = _CLASSIFICATION_TO_CATEGORY.get(
                event.get("classification", "normal"),
                "political_instability",
            )

            # Infer country from geo_risk_vector
            geo_vec = event.get("geo_risk_vector", {})
            source_country = self._infer_country(geo_vec, event.get("entities", []))

            batch = self.generate_signals_for_event(
                event_title=event.get("title", "Unknown event"),
                event_category=category,
                source_country=source_country,
                severity=event.get("severity_score", 0.3),
                gti_value=gti_value,
                gti_delta=gti_delta,
                gti_confidence=gti_confidence,
                assets=assets,
            )
            all_signals.extend(batch.signals)

        # Deduplicate by asset (keep highest confidence per asset)
        best_per_asset: dict[str, TradingSignal] = {}
        for sig in all_signals:
            if sig.asset not in best_per_asset or sig.confidence_pct > best_per_asset[sig.asset].confidence_pct:
                best_per_asset[sig.asset] = sig

        return SignalBatch(
            signals=sorted(best_per_asset.values(), key=lambda s: s.confidence_pct, reverse=True),
            global_tension_index=gti_value,
            event_count=len(events),
        )

    def _generate_single_signal(
        self,
        asset: str,
        event_title: str,
        event_category: str,
        source_country: str,
        severity: float,
        gti_value: float,
        gti_delta: float,
        gti_confidence: float,
        propagation: PropagationResult,
        asset_meta: dict[str, Any],
        live_indicators: dict[str, float] | None = None,
    ) -> TradingSignal | None:
        """Generate a single signal for one asset."""

        sector = asset_meta.get("sector")
        region = asset_meta.get("region", "global")
        asset_class = asset_meta.get("class", "equity")

        # Get graph impact for this asset
        graph_impact = next(
            (ai for ai in propagation.asset_impacts if ai.node_id == asset),
            None,
        )
        graph_score = graph_impact.impact_score if graph_impact else 0.05
        impact_path = graph_impact.path if graph_impact else [source_country, asset]

        # Build features for ML model
        oil_shock = 0.0
        if event_category == "energy_supply_disruption":
            oil_shock = severity * 0.8
        elif event_category == "military_escalation" and source_country in (
            "SAU", "IRN", "IRQ", "RUS", "ARE",
        ):
            oil_shock = severity * 0.5

        live_inds = live_indicators or {}
        features = AssetFeatures(
            symbol=asset,
            sector=sector,
            region=region,
            gti_value=gti_value,
            gti_delta_1h=gti_delta,
            gti_confidence=gti_confidence,
            realized_vol=asset_meta.get("realized_vol", 0.15),
            return_1d=asset_meta.get("return_1d", 0.0),
            return_5d=asset_meta.get("return_5d", 0.0),
            oil_shock=oil_shock,
            regime_vix_proxy=min(1.0, gti_value / 80.0),
            rsi_14=live_inds.get("rsi_14", 0.5),
            macd_signal_diff=live_inds.get("macd_signal_diff", 0.0),
            bb_pct_b=live_inds.get("bb_pct_b", 0.5),
        )

        ml_result = self.model.predict(features)

        # Build reasoning chain
        reasoning_chain = self._build_reasoning_chain(
            asset=asset,
            asset_class=asset_class,
            event_title=event_title,
            event_category=event_category,
            source_country=source_country,
            severity=severity,
            gti_value=gti_value,
            gti_delta=gti_delta,
            ml_result=ml_result,
            graph_score=graph_score,
            impact_path=impact_path,
        )

        # Determine action with combined graph + ML scores
        combined_confidence = 0.6 * ml_result.confidence_score + 0.4 * graph_score
        action = self._determine_action(ml_result, combined_confidence, graph_score)

        # Price direction and magnitude
        price_dir = "up" if ml_result.directional_bias > 0.1 else "down" if ml_result.directional_bias < -0.1 else "neutral"
        magnitude = self._magnitude(ml_result.vol_spike_prob_24h, graph_score)

        # Safe-haven assets reverse direction
        if asset in ("GLD", "TLT", "TIP") and event_category in (
            "military_escalation", "nuclear_threat", "territorial_dispute",
        ):
            if action == "Sell":
                action = "Buy"
                price_dir = "up"
            elif action == "Hold" and severity > 0.5:
                action = "Buy"
                price_dir = "up"

        # Time horizon
        time_horizon = "short-term" if severity > 0.7 else "medium-term" if severity > 0.4 else "long-term"

        # Related assets (from same graph propagation)
        related = [
            ai.node_id for ai in propagation.asset_impacts
            if ai.node_id != asset and ai.impact_score > 0.05
        ][:5]

        # Confidence percentage
        conf_pct = round(combined_confidence * 100, 1)
        unc_pct = round(ml_result.uncertainty_score * 100, 1)

        # Summary reasoning
        summary = self._build_summary(
            asset, action, event_title, event_category,
            source_country, conf_pct, price_dir,
        )

        return TradingSignal(
            asset=asset,
            asset_class=asset_class,
            action=action.upper(),
            confidence_pct=conf_pct,
            uncertainty_pct=unc_pct,
            reasoning_summary=summary,
            reasoning_chain=reasoning_chain,
            triggering_event=event_title,
            event_category=event_category,
            impact_path=impact_path,
            vol_spike_prob=ml_result.vol_spike_prob_24h,
            directional_bias=ml_result.directional_bias,
            sector_stress=ml_result.sector_stress,
            price_direction=price_dir,
            expected_magnitude=magnitude,
            time_horizon=time_horizon,
            related_assets=related,
        )

    def _build_reasoning_chain(
        self,
        asset: str,
        asset_class: str,
        event_title: str,
        event_category: str,
        source_country: str,
        severity: float,
        gti_value: float,
        gti_delta: float,
        ml_result: AssetImpactResult,
        graph_score: float,
        impact_path: list[str],
    ) -> list[ReasoningStep]:
        steps = []

        # Step 1: Event detection
        steps.append(ReasoningStep(
            step_number=1,
            description=f"Geopolitical event detected: {event_category.replace('_', ' ')}",
            evidence=f"'{event_title}' involving {source_country} with severity {severity:.0%}",
            confidence_contribution=0.15,
        ))

        # Step 2: GTI assessment
        trend = "rising" if gti_delta > 0.5 else "stable" if abs(gti_delta) < 0.5 else "falling"
        steps.append(ReasoningStep(
            step_number=2,
            description=f"Global Tension Index at {gti_value:.1f}, trend is {trend}",
            evidence=f"GTI moved {gti_delta:+.1f} in the last hour, supporting {'elevated' if gti_value > 50 else 'moderate'} risk assessment",
            confidence_contribution=0.20,
        ))

        # Step 3: Impact propagation
        path_str = " → ".join(impact_path)
        steps.append(ReasoningStep(
            step_number=3,
            description=f"Impact propagation: {path_str}",
            evidence=f"Graph propagation score: {graph_score:.0%}. Shock travels through supply chain/trade dependencies.",
            confidence_contribution=0.25,
        ))

        # Step 4: ML prediction
        vol_label = "high" if ml_result.vol_spike_prob_24h > 0.6 else "moderate" if ml_result.vol_spike_prob_24h > 0.3 else "low"
        bias_label = "bullish" if ml_result.directional_bias > 0.2 else "bearish" if ml_result.directional_bias < -0.2 else "neutral"
        steps.append(ReasoningStep(
            step_number=4,
            description=f"ML model predicts {vol_label} volatility and {bias_label} bias for {asset}",
            evidence=(
                f"24h vol spike probability: {ml_result.vol_spike_prob_24h:.0%}, "
                f"directional bias: {ml_result.directional_bias:+.2f}, "
                f"sector stress: {ml_result.sector_stress:.0%}"
            ),
            confidence_contribution=0.25,
        ))

        # Step 5: Final assessment
        steps.append(ReasoningStep(
            step_number=5,
            description=f"Combined assessment for {asset} ({asset_class})",
            evidence=f"Recommendation: {ml_result.recommendation} with uncertainty {ml_result.uncertainty_score:.0%}",
            confidence_contribution=0.15,
        ))

        return steps

    def _determine_action(
        self, ml_result: AssetImpactResult, combined_conf: float, graph_score: float
    ) -> str:
        """Determine action using both ML recommendation and graph impact."""
        if ml_result.uncertainty_score > 0.75:
            return "Hold"

        if graph_score > 0.3 and ml_result.vol_spike_prob_24h > 0.6:
            if ml_result.directional_bias < -0.2:
                return "Sell"
            elif ml_result.directional_bias > 0.2:
                return "Buy"

        return ml_result.recommendation

    def _magnitude(self, vol_prob: float, graph_score: float) -> str:
        combined = vol_prob * 0.6 + graph_score * 0.4
        if combined > 0.7:
            return "severe"
        elif combined > 0.5:
            return "significant"
        elif combined > 0.25:
            return "moderate"
        return "minimal"

    def _build_summary(
        self,
        asset: str,
        action: str,
        event_title: str,
        event_category: str,
        source_country: str,
        confidence: float,
        price_dir: str,
    ) -> str:
        category_readable = event_category.replace("_", " ")
        return (
            f"{action.upper()} {asset} — {category_readable} involving {source_country} "
            f"is expected to drive prices {price_dir}. Confidence: {confidence:.0f}%. "
            f"Triggered by: {event_title[:100]}"
        )

    def _infer_country(self, geo_vec: dict[str, float], entities: list[str]) -> str:
        """Best-effort country inference from event metadata."""
        # Map regions to representative countries
        _region_to_country = {
            "middle_east": "SAU",
            "europe": "DEU",
            "asia_pacific": "CHN",
            "americas": "USA",
            "africa": "NGA",
        }

        if geo_vec:
            top_region = max(geo_vec, key=geo_vec.get)
            if top_region != "global":
                return _region_to_country.get(top_region, "USA")

        # Try entity matching
        _entity_to_country = {
            "china": "CHN", "russia": "RUS", "iran": "IRN", "saudi": "SAU",
            "israel": "ISR", "ukraine": "UKR", "taiwan": "TWN", "korea": "KOR",
            "japan": "JPN", "india": "IND", "brazil": "BRA", "turkey": "TUR",
            "united states": "USA", "us": "USA", "usa": "USA",
            "germany": "DEU", "france": "FRA", "united kingdom": "GBR",
        }
        for entity in entities:
            for keyword, iso in _entity_to_country.items():
                if keyword in entity.lower():
                    return iso

        return "USA"


# ── Module singleton ──────────────────────────────────────────────────────────

_signal_generator: TradingSignalGenerator | None = None


def get_signal_generator() -> TradingSignalGenerator:
    global _signal_generator  # noqa: PLW0603
    if _signal_generator is None:
        _signal_generator = TradingSignalGenerator()
    return _signal_generator
