"""Integration tests — all API endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.event import Event


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_returns_200(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/health")
        assert resp.status_code == 200

    async def test_health_response_structure(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/health")
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "db" in data
        assert "redis" in data
        assert "ts" in data

    async def test_health_status_is_valid(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/health")
        assert resp.json()["status"] in ("healthy", "degraded", "unhealthy")


@pytest.mark.asyncio
class TestGTIEndpoints:
    async def test_gti_current_returns_200(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/gti/current")
        assert resp.status_code == 200

    async def test_gti_current_has_required_fields(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/gti/current")
        data = resp.json()
        required = {
            "region", "gti_value", "gti_delta_1h", "confidence",
            "top_drivers", "calculation_version", "ts",
            "model_version", "pipeline_version", "data_as_of",
            "not_financial_advice",
        }
        assert required.issubset(data.keys())

    async def test_gti_current_not_financial_advice_true(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/gti/current")
        assert resp.json()["not_financial_advice"] is True

    async def test_gti_current_value_bounded(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/gti/current")
        val = resp.json()["gti_value"]
        assert 0.0 <= val <= 100.0

    async def test_gti_current_with_region(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/gti/current?region=europe")
        assert resp.status_code == 200
        assert resp.json()["region"] == "europe"

    async def test_gti_history_returns_200(self, async_client: AsyncClient) -> None:
        resp = await async_client.get(
            "/gti/history",
            params={
                "start": "2025-01-01T00:00:00Z",
                "end": "2025-01-08T00:00:00Z",
                "region": "global",
            },
        )
        assert resp.status_code == 200

    async def test_gti_history_has_data_array(self, async_client: AsyncClient) -> None:
        resp = await async_client.get(
            "/gti/history",
            params={
                "start": "2025-01-01T00:00:00Z",
                "end": "2025-01-08T00:00:00Z",
            },
        )
        data = resp.json()
        assert "data" in data
        assert isinstance(data["data"], list)


@pytest.mark.asyncio
class TestSignalsEndpoints:
    async def test_signals_assets_returns_200(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/signals/assets")
        assert resp.status_code == 200

    async def test_signals_assets_structure(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/signals/assets")
        data = resp.json()
        assert "signals" in data
        assert "count" in data
        assert "not_financial_advice" in data
        assert data["not_financial_advice"] is True

    async def test_signals_assets_with_region(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/signals/assets?region=americas&timeframe=24h")
        assert resp.status_code == 200

    async def test_signals_assets_invalid_timeframe(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/signals/assets?timeframe=99d")
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestSignalsV2Endpoints:
    async def test_signals_v2_all_returns_200(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/signals/v2/all")
        assert resp.status_code == 200

    async def test_signals_v2_uses_database_events_when_available(
        self,
        async_client: AsyncClient,
        test_db_session,
    ) -> None:
        event = Event(
            content_hash="signals-v2-live-event-test",
            title="Pipeline outage disrupts LNG shipments in Europe",
            body="A major route reports prolonged outage and export constraints.",
            url="https://example.com/news/lng-outage",
            source="test_source",
            region="europe",
            occurred_at=datetime.now(UTC) - timedelta(minutes=5),
            ingested_at=datetime.now(UTC),
            classification="energy_supply_disruption",
            sentiment_score=-0.8,
            severity_score=0.92,
            entities=["Europe", "LNG"],
            geo_risk_vector={"europe": 0.9, "global": 0.4},
            embedding=[0.1, 0.2, 0.3],
        )
        test_db_session.add(event)
        await test_db_session.commit()

        resp = await async_client.get("/signals/v2/all?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["events_used"] >= 1
        assert data["events_source"] == "database"

    async def test_signals_v2_returns_trade_setup_fields(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/signals/v2/all?limit=5")
        data = resp.json()
        assert "signals" in data
        assert data["signals"]
        first = data["signals"][0]
        assert "trade_setup" in first
        assert "current_price" in first["trade_setup"]
        assert "risk_reward" in first["trade_setup"]


@pytest.mark.asyncio
class TestEventsEndpoint:
    async def test_events_timeline_returns_200(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/events/timeline")
        assert resp.status_code == 200

    async def test_events_timeline_structure(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/events/timeline")
        data = resp.json()
        assert "events" in data
        assert "count" in data
        assert isinstance(data["events"], list)

    async def test_events_timeline_with_region_filter(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/events/timeline?region=middle_east")
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestScenarioEndpoint:
    async def test_scenario_returns_200(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/simulate/scenario",
            json={
                "conflict_intensity": 0.7,
                "sanctions_level": 0.3,
                "oil_supply_disruption": 0.5,
                "cyber_risk": 0.1,
                "duration_hours": 12,
                "region": "middle_east",
                "assets": ["SPY", "GLD"],
            },
        )
        assert resp.status_code == 200

    async def test_scenario_response_has_gti_path(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/simulate/scenario",
            json={
                "conflict_intensity": 0.5,
                "duration_hours": 6,
                "assets": ["USO"],
            },
        )
        data = resp.json()
        assert "gti_path" in data
        assert len(data["gti_path"]) == 7  # 0..6 inclusive

    async def test_scenario_response_has_trajectories(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/simulate/scenario",
            json={"assets": ["SPY", "GLD", "TLT"], "duration_hours": 4},
        )
        data = resp.json()
        assert len(data["asset_trajectories"]) == 3

    async def test_scenario_invalid_intensity(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/simulate/scenario",
            json={"conflict_intensity": 2.0},  # out of range
        )
        assert resp.status_code == 422

    async def test_scenario_not_financial_advice(self, async_client: AsyncClient) -> None:
        resp = await async_client.post("/simulate/scenario", json={})
        data = resp.json()
        assert data.get("not_financial_advice") is True


@pytest.mark.asyncio
class TestPortfolioEndpoint:
    async def test_portfolio_valid_returns_200(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/portfolio/evaluate",
            json={
                "holdings": [
                    {"symbol": "SPY", "weight": 0.6, "sector": "equity", "region": "americas"},
                    {"symbol": "GLD", "weight": 0.4, "sector": "commodities", "region": "global"},
                ]
            },
        )
        assert resp.status_code == 200

    async def test_portfolio_response_has_pnl_range(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/portfolio/evaluate",
            json={
                "holdings": [
                    {"symbol": "SPY", "weight": 1.0},
                ]
            },
        )
        data = resp.json()
        assert "simulated_pnl_range" in data
        pnl = data["simulated_pnl_range"]
        assert pnl["p05"] <= pnl["p50"] <= pnl["p95"]

    async def test_portfolio_invalid_weights_422(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/portfolio/evaluate",
            json={
                "holdings": [
                    {"symbol": "SPY", "weight": 0.3},
                    {"symbol": "GLD", "weight": 0.1},
                ]
            },
        )
        assert resp.status_code == 422

    async def test_portfolio_scenario_adjusted(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/portfolio/evaluate",
            json={
                "holdings": [{"symbol": "XLE", "weight": 1.0}],
                "include_scenario": True,
                "scenario_conflict_intensity": 0.8,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["scenario_adjusted"] is True


@pytest.mark.asyncio
class TestAlertsEndpoint:
    async def test_subscribe_discord_returns_201(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/alerts/subscribe",
            json={
                "channel": "discord",
                "webhook_url": "https://discord.com/api/webhooks/123/abc",
                "region_filter": "middle_east",
                "gti_threshold": 60.0,
            },
        )
        assert resp.status_code == 201

    async def test_subscribe_response_has_id(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/alerts/subscribe",
            json={
                "channel": "slack",
                "webhook_url": "https://hooks.slack.com/services/abc/def",
            },
        )
        data = resp.json()
        assert "id" in data
        assert "channel" in data
        assert data["channel"] == "slack"

    async def test_subscribe_invalid_channel_422(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/alerts/subscribe",
            json={"channel": "telegram", "webhook_url": "https://example.com/hook"},
        )
        assert resp.status_code == 422

    async def test_subscribe_invalid_url_422(self, async_client: AsyncClient) -> None:
        resp = await async_client.post(
            "/alerts/subscribe",
            json={"channel": "discord", "webhook_url": "not-a-url"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestModelStatusEndpoint:
    async def test_model_status_returns_200(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/meta/model-status")
        assert resp.status_code == 200

    async def test_model_status_has_versions(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/meta/model-status")
        data = resp.json()
        assert "gti_version" in data
        assert "pipeline_version" in data
        assert "active_models" in data


@pytest.mark.asyncio
class TestMarketLiveEndpoint:
    async def test_market_live_endpoint_returns_structure(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/market/live")
        assert resp.status_code == 200
        data = resp.json()
        assert "prices" in data
        assert "count" in data
        assert "data_source" in data
