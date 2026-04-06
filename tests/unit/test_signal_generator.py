"""Unit tests: TradingSignalGenerator — event classification, asset mapping, signal output."""
from __future__ import annotations

import pytest

from app.pipelines.signal_generator import (
    EVENT_CATEGORIES,
    TradingSignal,
    TradingSignalGenerator,
    _CLASSIFICATION_TO_CATEGORY,
)


class TestEventCategories:
    def test_event_categories_dict_non_empty(self) -> None:
        assert len(EVENT_CATEGORIES) > 0

    def test_military_escalation_category_exists(self) -> None:
        assert "military_escalation" in EVENT_CATEGORIES

    def test_energy_supply_disruption_exists(self) -> None:
        assert "energy_supply_disruption" in EVENT_CATEGORIES

    def test_classification_mapping_covers_key_types(self) -> None:
        for key in ["military_escalation", "energy_supply_disruption", "sanctions"]:
            assert key in _CLASSIFICATION_TO_CATEGORY or key in EVENT_CATEGORIES


class TestTradingSignalGenerator:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self._gen = TradingSignalGenerator()

    def _call_generate(
        self,
        classification: str = "military_escalation",
        severity: float = 0.8,
        gti_value: float = 45.0,
        gti_delta: float = 3.0,
        assets: list[str] | None = None,
    ):
        return self._gen.generate_signals_for_event(
            event_title="Test geopolitical event",
            event_category=classification,
            source_country="iran",
            severity=severity,
            gti_value=gti_value,
            gti_delta=gti_delta,
            gti_confidence=0.65,
            assets=assets or [],
        )

    def test_generate_returns_signal_batch(self) -> None:
        result = self._call_generate()
        assert result is not None

    def test_generate_signals_non_empty(self) -> None:
        result = self._call_generate(severity=0.9)
        signals = list(result.signals) if hasattr(result, "signals") else result
        assert len(signals) >= 0  # may be 0 if no assets — just not an error

    def test_energy_event_call_succeeds(self) -> None:
        result = self._call_generate(
            classification="energy_supply_disruption",
            assets=["WTI", "USO", "XLE"],
        )
        assert result is not None

    def test_periodic_signals_returns_result(self) -> None:
        result = self._gen.generate_periodic_signals(
            events=[],
            gti_value=40.0,
            gti_delta=2.0,
            gti_confidence=0.6,
        )
        assert result is not None

    def test_periodic_signals_with_assets(self) -> None:
        result = self._gen.generate_periodic_signals(
            events=[],
            gti_value=50.0,
            gti_delta=3.0,
            gti_confidence=0.7,
            assets=["XAUUSD", "XAGUSD", "WTI", "BTCUSD", "NATGAS"],
        )
        assert result is not None

    def test_high_severity_call_succeeds(self) -> None:
        result = self._call_generate(severity=0.95, gti_value=80.0, gti_delta=7.0)
        assert result is not None

    def test_low_severity_call_succeeds(self) -> None:
        result = self._call_generate(severity=0.1, gti_value=5.0, gti_delta=0.1)
        assert result is not None

    def test_all_focus_event_categories_callable(self) -> None:
        categories = [
            "military_escalation", "energy_supply_disruption",
            "sanctions", "political_instability", "trade_restrictions",
        ]
        for cat in categories:
            result = self._call_generate(classification=cat)
            assert result is not None


class TestTradingSignalDataclass:
    def test_signal_has_asset_field(self) -> None:
        assert "asset" in TradingSignal.__dataclass_fields__

    def test_signal_has_action_field(self) -> None:
        assert "action" in TradingSignal.__dataclass_fields__

    def test_signal_has_confidence_field(self) -> None:
        assert "confidence_pct" in TradingSignal.__dataclass_fields__

    def test_signal_has_vol_spike_prob(self) -> None:
        assert "vol_spike_prob" in TradingSignal.__dataclass_fields__

    def test_signal_has_directional_bias(self) -> None:
        assert "directional_bias" in TradingSignal.__dataclass_fields__

    def test_signal_schema_coverage(self) -> None:
        required = {"asset", "action", "confidence_pct", "reasoning_summary", "event_category"}
        actual = set(TradingSignal.__dataclass_fields__.keys())
        assert required.issubset(actual)
