"""Contract tests — validate response schemas against Pydantic models."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.schemas.gti import GTICurrentResponse, GTIHistoryResponse
from app.schemas.signal import SignalAssetsResponse
from app.schemas.scenario import ScenarioResponse
from app.schemas.portfolio import PortfolioEvalResponse
from app.schemas.health import HealthResponse


@pytest.mark.asyncio
class TestSchemaContracts:
    """Each test validates response JSON against the Pydantic v2 contract."""

    async def test_gti_current_contract(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/gti/current")
        assert resp.status_code == 200
        model = GTICurrentResponse.model_validate(resp.json())
        assert 0.0 <= model.gti_value <= 100.0
        assert 0.0 <= model.confidence <= 1.0
        assert model.not_financial_advice is True

    async def test_gti_history_contract(self, async_client: AsyncClient) -> None:
        resp = await async_client.get(
            "/gti/history",
            params={"start": "2025-01-01T00:00:00Z", "end": "2025-01-07T00:00:00Z"},
        )
        assert resp.status_code == 200
        model = GTIHistoryResponse.model_validate(resp.json())
        assert isinstance(model.data, list)

    async def test_signals_assets_contract(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/signals/assets")
        assert resp.status_code == 200
        model = SignalAssetsResponse.model_validate(resp.json())
        assert model.not_financial_advice is True
        for sig in model.signals:
            assert sig.recommendation in ("Buy", "Sell", "Hold")
            assert 0.0 <= sig.vol_spike_prob_24h <= 1.0
            assert -1.0 <= sig.directional_bias <= 1.0

    async def test_scenario_contract(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/simulate/scenario",
            json={"duration_hours": 4, "assets": ["SPY"]},
        )
        assert resp.status_code == 200
        model = ScenarioResponse.model_validate(resp.json())
        assert model.not_financial_advice is True
        assert len(model.gti_path) == 5  # 0..4 hours

    async def test_portfolio_contract(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/portfolio/evaluate",
            json={"holdings": [{"symbol": "SPY", "weight": 1.0}]},
        )
        assert resp.status_code == 200
        model = PortfolioEvalResponse.model_validate(resp.json())
        assert model.not_financial_advice is True
        assert model.drawdown_risk.bucket in {"LOW", "MODERATE", "ELEVATED", "HIGH", "SEVERE"}
        assert model.simulated_pnl_range.p05 <= model.simulated_pnl_range.p95

    async def test_health_contract(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/health")
        assert resp.status_code == 200
        model = HealthResponse.model_validate(resp.json())
        assert model.status in ("healthy", "degraded", "unhealthy")
