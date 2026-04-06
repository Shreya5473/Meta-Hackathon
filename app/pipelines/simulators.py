"""Scenario and portfolio simulators."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.core.logging import get_logger
from app.pipelines.gti_engine import GTIEngine, _decay_factor
from app.pipelines.market_model import AssetFeatures, MarketImpactModel

logger = get_logger(__name__)

# ── Scenario simulator ────────────────────────────────────────────────────────

@dataclass
class ScenarioShock:
    conflict_intensity: float = 0.5
    sanctions_level: float = 0.0
    oil_supply_disruption: float = 0.0
    cyber_risk: float = 0.0
    duration_hours: int = 24
    region: str = "global"


@dataclass
class GTITrajectoryPoint:
    hour: int
    gti_value: float
    confidence: float


@dataclass
class AssetStressTrajectory:
    symbol: str
    vol_spike_prob_path: list[float]
    directional_bias_path: list[float]
    stress_peak: float
    stress_mean: float


@dataclass
class ScenarioSimResult:
    gti_path: list[GTITrajectoryPoint]       # median (p50) path — backward-compatible
    gti_path_p05: list[float]                # 5th-percentile GTI at each hour
    gti_path_p95: list[float]                # 95th-percentile GTI at each hour
    n_simulations: int                       # number of Monte Carlo paths simulated
    asset_trajectories: list[AssetStressTrajectory]
    aggregate_stress_peak: float
    aggregate_stress_mean: float


class ScenarioSimulator:
    """Vectorised Euler-Maruyama Monte Carlo simulation of GTI paths.

    GTI SDE (per simulation path):
        dGTI = -λ * GTI * dt + μ_shock * dt + σ * dW

    All n_simulations paths are evolved simultaneously as a NumPy matrix so the
    full stochastic distribution of future GTI is captured.  The median path is
    returned as gti_path for backward compatibility; 5th / 95th percentile bands
    are exposed via gti_path_p05 / gti_path_p95.
    """

    def __init__(self, gti_engine: GTIEngine, impact_model: MarketImpactModel) -> None:
        self.gti_engine = gti_engine
        self.impact_model = impact_model

    def _shock_drift(self, shock: ScenarioShock) -> float:
        """Positive drift contribution per hour from shock params."""
        return (
            7.0 * shock.conflict_intensity
            + 4.0 * shock.sanctions_level
            + 5.0 * shock.oil_supply_disruption
            + 3.0 * shock.cyber_risk
        )

    def simulate(
        self,
        shock: ScenarioShock,
        base_gti: float,
        assets: list[str],
        asset_meta: dict[str, dict[str, Any]] | None = None,
        seed: int = 42,
    ) -> ScenarioSimResult:
        n_simulations = 500
        rng = np.random.default_rng(seed)
        lambda_ = self.gti_engine.lambda_
        dt = 1.0          # 1 hour per step
        sigma = 1.5       # GTI diffusion coefficient per hour
        drift = self._shock_drift(shock)
        n_steps = shock.duration_hours

        # ── Vectorised Euler-Maruyama ─────────────────────────────────────────
        # Z shape: (n_simulations, n_steps) — all random shocks pre-sampled
        Z = rng.standard_normal((n_simulations, n_steps))

        # gti_matrix shape: (n_simulations, n_steps + 1)
        gti_matrix = np.empty((n_simulations, n_steps + 1))
        gti_matrix[:, 0] = float(base_gti)

        noise_scale = sigma * math.sqrt(dt)
        for h in range(n_steps):
            gti_prev = gti_matrix[:, h]
            dgti = -lambda_ * gti_prev * dt + drift * dt + noise_scale * Z[:, h]
            gti_matrix[:, h + 1] = np.clip(gti_prev + dgti, 0.0, 100.0)

        # ── Distribution summary at each hour ────────────────────────────────
        gti_p05 = np.percentile(gti_matrix, 5, axis=0)   # shape: (n_steps + 1,)
        gti_p50 = np.percentile(gti_matrix, 50, axis=0)  # median
        gti_p95 = np.percentile(gti_matrix, 95, axis=0)

        # ── Build gti_path from the median path (backward-compatible) ─────────
        gti_path: list[GTITrajectoryPoint] = [
            GTITrajectoryPoint(
                hour=h,
                gti_value=round(float(gti_p50[h]), 4),
                confidence=round(max(0.1, 0.9 - 0.005 * h), 4),
            )
            for h in range(n_steps + 1)
        ]

        # ── Asset stress paths driven by the median GTI trajectory ────────────
        asset_trajectories: list[AssetStressTrajectory] = []
        meta = asset_meta or {}

        for sym in assets:
            ameta = meta.get(sym, {})
            sector = ameta.get("sector")
            region = ameta.get("region", shock.region)

            vol_path: list[float] = []
            bias_path: list[float] = []
            for pt in gti_path:
                delta = (
                    pt.gti_value - float(base_gti)
                    if pt.hour == 0
                    else gti_path[pt.hour].gti_value - gti_path[pt.hour - 1].gti_value
                )
                features = AssetFeatures(
                    symbol=sym,
                    sector=sector,
                    region=region,
                    gti_value=pt.gti_value,
                    gti_delta_1h=delta,
                    gti_confidence=pt.confidence,
                    realized_vol=ameta.get("realized_vol", 0.15),
                    return_1d=ameta.get("return_1d", 0.0),
                    return_5d=ameta.get("return_5d", 0.0),
                    oil_shock=shock.oil_supply_disruption,
                    regime_vix_proxy=min(1.0, pt.gti_value / 80.0),
                )
                impact = self.impact_model.predict(features)
                vol_path.append(impact.vol_spike_prob_24h)
                bias_path.append(impact.directional_bias)

            stress_peak = max(vol_path)
            stress_mean = sum(vol_path) / len(vol_path)
            asset_trajectories.append(AssetStressTrajectory(
                symbol=sym,
                vol_spike_prob_path=vol_path,
                directional_bias_path=bias_path,
                stress_peak=round(stress_peak, 4),
                stress_mean=round(stress_mean, 4),
            ))

        all_peaks = [t.stress_peak for t in asset_trajectories]
        return ScenarioSimResult(
            gti_path=gti_path,
            gti_path_p05=[round(float(v), 4) for v in gti_p05],
            gti_path_p95=[round(float(v), 4) for v in gti_p95],
            n_simulations=n_simulations,
            asset_trajectories=asset_trajectories,
            aggregate_stress_peak=round(max(all_peaks) if all_peaks else 0.0, 4),
            aggregate_stress_mean=round(
                sum(t.stress_mean for t in asset_trajectories) / max(1, len(asset_trajectories)),
                4,
            ),
        )

# ── Portfolio simulator ────────────────────────────────────────────────────────

_DRAWDOWN_BUCKETS = [
    ("LOW", 0.05),
    ("MODERATE", 0.12),
    ("ELEVATED", 0.20),
    ("HIGH", 0.35),
    ("SEVERE", 1.0),
]


@dataclass
class Holding:
    symbol: str
    weight: float
    sector: str | None = None
    region: str | None = None


@dataclass
class PortfolioSimResult:
    expected_stress_impact: float
    pnl_p05: float
    pnl_p25: float
    pnl_p50: float
    pnl_p75: float
    pnl_p95: float
    drawdown_bucket: str
    max_drawdown_estimate: float
    sector_exposure: dict[str, float]
    region_exposure: dict[str, float]


class PortfolioSimulator:
    """Portfolio stress simulation against current and scenario GTI."""

    def __init__(self, impact_model: MarketImpactModel) -> None:
        self.impact_model = impact_model

    def _sector_region_exposure(
        self, holdings: list[Holding]
    ) -> tuple[dict[str, float], dict[str, float]]:
        sector_exp: dict[str, float] = {}
        region_exp: dict[str, float] = {}
        for h in holdings:
            sec = h.sector or "unknown"
            reg = h.region or "global"
            sector_exp[sec] = sector_exp.get(sec, 0.0) + h.weight
            region_exp[reg] = region_exp.get(reg, 0.0) + h.weight
        return sector_exp, region_exp

    def simulate(
        self,
        holdings: list[Holding],
        gti_value: float,
        gti_delta: float,
        gti_confidence: float,
        oil_shock: float = 0.0,
        n_simulations: int = 1000,
        seed: int = 42,
    ) -> PortfolioSimResult:
        rng = np.random.default_rng(seed)
        n_assets = len(holdings)

        # Per-asset expected return & vol from model
        signals = []
        for h in holdings:
            features = AssetFeatures(
                symbol=h.symbol,
                sector=h.sector,
                region=h.region or "global",
                gti_value=gti_value,
                gti_delta_1h=gti_delta,
                gti_confidence=gti_confidence,
                oil_shock=oil_shock,
                regime_vix_proxy=min(1.0, gti_value / 80.0),
            )
            sig = self.impact_model.predict(features)
            signals.append(sig)

        weights = np.array([h.weight for h in holdings])

        # Expected return per asset: directional_bias → expected daily return
        expected_returns = np.array([s.directional_bias * 0.01 for s in signals])

        # Vol per asset from vol_spike_prob
        vols = np.array([0.01 + s.vol_spike_prob_24h * 0.04 for s in signals])

        # Portfolio expected return
        port_er = float(np.dot(weights, expected_returns))

        # Monte Carlo portfolio PnL
        asset_returns = rng.normal(
            expected_returns,
            vols,
            size=(n_simulations, n_assets),
        )
        port_returns = asset_returns @ weights
        pnl = np.sort(port_returns)

        p05 = float(np.percentile(pnl, 5))
        p25 = float(np.percentile(pnl, 25))
        p50 = float(np.percentile(pnl, 50))
        p75 = float(np.percentile(pnl, 75))
        p95 = float(np.percentile(pnl, 95))

        # Max drawdown estimate (approximation from p05)
        max_drawdown = float(abs(p05) * math.sqrt(20))  # 20-day horizon

        # Stress impact: weighted average of sector_stress
        stress_impact = float(
            sum(s.sector_stress * w for s, w in zip(signals, weights.tolist()))
        )

        # Drawdown bucket
        bucket = "LOW"
        for name, threshold in _DRAWDOWN_BUCKETS:
            if max_drawdown <= threshold:
                bucket = name
                break

        sector_exp, region_exp = self._sector_region_exposure(holdings)

        return PortfolioSimResult(
            expected_stress_impact=round(min(1.0, stress_impact), 4),
            pnl_p05=round(p05, 6),
            pnl_p25=round(p25, 6),
            pnl_p50=round(p50, 6),
            pnl_p75=round(p75, 6),
            pnl_p95=round(p95, 6),
            drawdown_bucket=bucket,
            max_drawdown_estimate=round(max_drawdown, 4),
            sector_exposure=sector_exp,
            region_exposure=region_exp,
        )
