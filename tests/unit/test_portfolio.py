"""Unit tests: portfolio weight validation and simulator logic."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.portfolio import Holding, PortfolioEvalRequest


class TestPortfolioWeightValidation:
    def test_valid_portfolio_passes(self) -> None:
        req = PortfolioEvalRequest(
            holdings=[
                Holding(symbol="SPY", weight=0.60, sector="equity", region="americas"),
                Holding(symbol="GLD", weight=0.20, sector="commodities", region="global"),
                Holding(symbol="TLT", weight=0.20, sector="financials", region="americas"),
            ]
        )
        assert req is not None

    def test_weights_not_summing_to_one_fails(self) -> None:
        with pytest.raises(ValidationError, match="weights must sum"):
            PortfolioEvalRequest(
                holdings=[
                    Holding(symbol="SPY", weight=0.60),
                    Holding(symbol="GLD", weight=0.10),
                ]
            )

    def test_empty_holdings_fails(self) -> None:
        with pytest.raises(ValidationError):
            PortfolioEvalRequest(holdings=[])

    def test_single_holding_full_weight(self) -> None:
        req = PortfolioEvalRequest(
            holdings=[Holding(symbol="BRK.B", weight=1.0)]
        )
        assert len(req.holdings) == 1


class TestPortfolioSimulator:
    def test_simulate_returns_all_buckets(self) -> None:
        from app.pipelines.market_model import get_impact_model
        from app.pipelines.simulators import Holding as SimHolding, PortfolioSimulator

        sim = PortfolioSimulator(get_impact_model())
        holdings = [
            SimHolding("SPY", 0.5, "equity", "americas"),
            SimHolding("GLD", 0.5, "commodities", "global"),
        ]
        result = sim.simulate(holdings, gti_value=30.0, gti_delta=2.0, gti_confidence=0.7)
        assert result.drawdown_bucket in {"LOW", "MODERATE", "ELEVATED", "HIGH", "SEVERE"}
        assert result.pnl_p05 <= result.pnl_p50 <= result.pnl_p95
        assert 0.0 <= result.expected_stress_impact <= 1.0

    def test_high_gti_increases_stress_impact(self) -> None:
        from app.pipelines.market_model import get_impact_model
        from app.pipelines.simulators import Holding as SimHolding, PortfolioSimulator

        sim = PortfolioSimulator(get_impact_model())
        holdings = [SimHolding("XLE", 1.0, "energy", "middle_east")]
        low = sim.simulate(holdings, gti_value=10.0, gti_delta=0.0, gti_confidence=0.9)
        high = sim.simulate(holdings, gti_value=80.0, gti_delta=5.0, gti_confidence=0.7)
        assert high.expected_stress_impact >= low.expected_stress_impact

    def test_sector_region_exposure_sums_to_one(self) -> None:
        from app.pipelines.market_model import get_impact_model
        from app.pipelines.simulators import Holding as SimHolding, PortfolioSimulator

        sim = PortfolioSimulator(get_impact_model())
        holdings = [
            SimHolding("SPY", 0.4, "equity", "americas"),
            SimHolding("GLD", 0.3, "commodities", "global"),
            SimHolding("TLT", 0.3, "financials", "americas"),
        ]
        result = sim.simulate(holdings, gti_value=25.0, gti_delta=0.0, gti_confidence=0.6)
        total_sector = sum(result.sector_exposure.values())
        total_region = sum(result.region_exposure.values())
        assert total_sector == pytest.approx(1.0, abs=0.001)
        assert total_region == pytest.approx(1.0, abs=0.001)
