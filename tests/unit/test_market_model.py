"""Unit tests: MarketImpactModel — feature schema, predictions, key rotation."""
from __future__ import annotations

import numpy as np
import pytest

from app.pipelines.market_model import (
    FEATURE_SCHEMA,
    AssetFeatures,
    AssetImpactResult,
    BrierScoreTracker,
    MarketImpactModel,
    _recommendation,
    _sector_stress,
    feature_schema_hash,
)


# ── Feature schema ────────────────────────────────────────────────────────────

class TestFeatureSchema:
    def test_schema_has_12_features(self) -> None:
        assert len(FEATURE_SCHEMA) == 12

    def test_schema_contains_technical_indicators(self) -> None:
        assert "rsi_14" in FEATURE_SCHEMA
        assert "macd_signal_diff" in FEATURE_SCHEMA
        assert "bb_pct_b" in FEATURE_SCHEMA

    def test_schema_contains_gti_features(self) -> None:
        assert "gti_value" in FEATURE_SCHEMA
        assert "gti_delta_1h" in FEATURE_SCHEMA
        assert "gti_confidence" in FEATURE_SCHEMA

    def test_feature_hash_is_deterministic(self) -> None:
        assert feature_schema_hash() == feature_schema_hash()

    def test_feature_hash_is_16_chars(self) -> None:
        assert len(feature_schema_hash()) == 16


# ── AssetFeatures.to_array ────────────────────────────────────────────────────

class TestAssetFeaturesToArray:
    def _make_features(self, **kwargs) -> AssetFeatures:
        defaults = dict(
            symbol="GLD", sector="metals", region="global",
            gti_value=50.0, gti_delta_1h=2.0, gti_confidence=0.7,
            realized_vol=0.15, return_1d=-0.003, return_5d=0.01,
            sector_gti_weight=0.5, oil_shock=0.01, regime_vix_proxy=0.3,
            rsi_14=0.6, macd_signal_diff=0.002, bb_pct_b=0.65,
        )
        defaults.update(kwargs)
        return AssetFeatures(**defaults)

    def test_to_array_length_matches_schema(self) -> None:
        feat = self._make_features()
        arr = feat.to_array()
        assert len(arr) == len(FEATURE_SCHEMA)

    def test_gti_value_normalised_to_01(self) -> None:
        feat = self._make_features(gti_value=100.0)
        arr = feat.to_array()
        gti_idx = FEATURE_SCHEMA.index("gti_value")
        assert arr[gti_idx] == pytest.approx(1.0)

    def test_rsi_passthrough(self) -> None:
        feat = self._make_features(rsi_14=0.75)
        arr = feat.to_array()
        rsi_idx = FEATURE_SCHEMA.index("rsi_14")
        assert arr[rsi_idx] == pytest.approx(0.75)

    def test_all_values_are_floats(self) -> None:
        feat = self._make_features()
        for v in feat.to_array():
            assert isinstance(v, float)


# ── Sector stress ─────────────────────────────────────────────────────────────

class TestSectorStress:
    def test_energy_middle_east_high_stress(self) -> None:
        stress = _sector_stress("energy", {"middle_east": 1.0})
        assert stress >= 0.7

    def test_defense_europe_high_stress(self) -> None:
        stress = _sector_stress("defense", {"europe": 1.0})
        assert stress >= 0.5

    def test_unknown_sector_uses_global_default(self) -> None:
        stress = _sector_stress("unknown_sector", {"global": 0.5})
        assert 0.0 <= stress <= 1.0

    def test_stress_bounded_0_to_1(self) -> None:
        stress = _sector_stress("energy", {"middle_east": 10.0, "europe": 10.0})
        assert stress == pytest.approx(1.0)

    def test_empty_geo_vector_zero_stress(self) -> None:
        stress = _sector_stress("energy", {})
        assert stress == 0.0

    def test_crypto_sector_stress(self) -> None:
        stress = _sector_stress("crypto", {"global": 0.5})
        assert 0.0 <= stress <= 1.0


# ── Recommendation rules ─────────────────────────────────────────────────────

class TestRecommendationExtended:
    def test_all_combos_return_valid_string(self) -> None:
        valid = {"Buy", "Sell", "Hold"}
        for vol in np.linspace(0.0, 1.0, 6):
            for bias in np.linspace(-1.0, 1.0, 6):
                for unc in np.linspace(0.0, 1.0, 6):
                    assert _recommendation(float(vol), float(bias), float(unc)) in valid

    def test_max_uncertainty_always_hold(self) -> None:
        assert _recommendation(0.99, -0.99, 1.0) == "Hold"

    def test_crisis_conditions_sell(self) -> None:
        # High vol spike + strong negative bias + low uncertainty = Sell
        assert _recommendation(0.9, -0.8, 0.2) == "Sell"

    def test_calm_positive_conditions_buy(self) -> None:
        # Low vol spike + positive bias + low uncertainty = Buy
        assert _recommendation(0.1, 0.9, 0.1) == "Buy"


# ── MarketImpactModel integration ─────────────────────────────────────────────

class TestMarketImpactModelPredict:
    """These tests use the trained/bootstrapped model (not mocked)."""

    @pytest.fixture(autouse=True)
    def model(self) -> MarketImpactModel:
        self._model = MarketImpactModel()
        return self._model

    def _make_features(self, symbol: str = "GLD", sector: str = "metals") -> AssetFeatures:
        return AssetFeatures(
            symbol=symbol, sector=sector, region="global",
            gti_value=45.0, gti_delta_1h=3.0, gti_confidence=0.65,
            realized_vol=0.14, return_1d=-0.005, return_5d=0.02,
            sector_gti_weight=0.55, oil_shock=0.015, regime_vix_proxy=0.28,
            rsi_14=0.58, macd_signal_diff=0.003, bb_pct_b=0.61,
        )

    def test_predict_returns_correct_type(self) -> None:
        result = self._model.predict(self._make_features())
        assert isinstance(result, AssetImpactResult)

    def test_vol_spike_prob_bounded(self) -> None:
        result = self._model.predict(self._make_features())
        assert 0.0 <= result.vol_spike_prob_24h <= 1.0

    def test_directional_bias_bounded(self) -> None:
        result = self._model.predict(self._make_features())
        assert -1.0 <= result.directional_bias <= 1.0

    def test_confidence_score_bounded(self) -> None:
        result = self._model.predict(self._make_features())
        assert 0.0 <= result.confidence_score <= 1.0

    def test_recommendation_is_valid(self) -> None:
        result = self._model.predict(self._make_features())
        assert result.recommendation in {"Buy", "Sell", "Hold"}

    def test_symbol_preserved_in_result(self) -> None:
        feat = self._make_features(symbol="BTCUSD", sector="crypto")
        result = self._model.predict(feat)
        assert result.symbol == "BTCUSD"

    def test_feature_hash_in_result(self) -> None:
        result = self._model.predict(self._make_features())
        assert result.feature_hash == feature_schema_hash()

    def test_high_gti_crisis_conditions(self) -> None:
        """Both calm and crisis predictions should be valid and bounded."""
        calm = AssetFeatures(
            symbol="GLD", sector="metals", region="global",
            gti_value=5.0, gti_delta_1h=0.1, gti_confidence=0.9,
            realized_vol=0.08, return_1d=0.001, return_5d=0.005,
            sector_gti_weight=0.1, oil_shock=0.0, regime_vix_proxy=0.1,
            rsi_14=0.5, macd_signal_diff=0.0, bb_pct_b=0.5,
        )
        crisis = AssetFeatures(
            symbol="GLD", sector="metals", region="middle_east",
            gti_value=90.0, gti_delta_1h=8.0, gti_confidence=0.3,
            realized_vol=0.55, return_1d=-0.04, return_5d=-0.08,
            sector_gti_weight=0.9, oil_shock=0.12, regime_vix_proxy=0.85,
            rsi_14=0.2, macd_signal_diff=-0.009, bb_pct_b=0.05,
        )
        r_calm = self._model.predict(calm)
        r_crisis = self._model.predict(crisis)
        # Both must produce valid bounded predictions
        assert 0.0 <= r_calm.vol_spike_prob_24h <= 1.0
        assert 0.0 <= r_crisis.vol_spike_prob_24h <= 1.0
        # Crisis uncertainty should be higher (high vol + low confidence)
        assert r_crisis.uncertainty_score >= r_calm.uncertainty_score

    def test_predict_focus_assets(self) -> None:
        """All 10 focus assets should produce valid predictions."""
        focus = [
            ("XAUUSD", "metals"),   ("XAGUSD", "metals"),
            ("WTI",    "energy"),   ("NATGAS", "energy"),
            ("BTCUSD", "crypto"),   ("LMT",    "defense"),
            ("RTX",    "defense"),  ("NOC",    "defense"),
            ("GD",     "defense"),  ("BA",     "defense"),
        ]
        for symbol, sector in focus:
            feat = self._make_features(symbol=symbol, sector=sector)
            result = self._model.predict(feat)
            assert result.symbol == symbol
            assert result.recommendation in {"Buy", "Sell", "Hold"}
            assert 0.0 <= result.vol_spike_prob_24h <= 1.0


# ── Key rotation (FinnhubLiveIndicators) ─────────────────────────────────────

class TestFinnhubKeyRotation:
    def test_single_key_stored_in_list(self) -> None:
        from app.pipelines.live_indicators import FinnhubLiveIndicators
        ind = FinnhubLiveIndicators(api_key="testkey123")
        assert ind._keys == ["testkey123"]

    def test_next_key_rotates(self) -> None:
        from app.pipelines.live_indicators import FinnhubLiveIndicators
        ind = FinnhubLiveIndicators(api_key="key1")
        ind._keys = ["key1", "key2"]
        ind._key_idx = 0
        assert ind._next_key() == "key1"
        assert ind._next_key() == "key2"
        assert ind._next_key() == "key1"  # wraps

    def test_api_key_property_returns_first(self) -> None:
        from app.pipelines.live_indicators import FinnhubLiveIndicators
        ind = FinnhubLiveIndicators(api_key="primary")
        ind._keys = ["primary", "secondary"]
        assert ind._api_key == "primary"


class TestRealMarketAdapterKeyRotation:
    def test_adapter_loads_multiple_keys(self) -> None:
        from app.pipelines.market_feeds import RealMarketAdapter
        adapter = RealMarketAdapter()
        assert len(adapter._keys) >= 1

    def test_next_key_increments_index(self) -> None:
        from app.pipelines.market_feeds import RealMarketAdapter
        adapter = RealMarketAdapter()
        adapter._keys = ["k1", "k2"]
        adapter._key_index = 0
        assert adapter._next_key() == "k1"
        assert adapter._next_key() == "k2"
        assert adapter._next_key() == "k1"

    def test_api_key_property_backwards_compat(self) -> None:
        from app.pipelines.market_feeds import RealMarketAdapter
        adapter = RealMarketAdapter()
        adapter._keys = ["mykey"]
        assert adapter._api_key == "mykey"

    def test_empty_keys_returns_empty_string(self) -> None:
        from app.pipelines.market_feeds import RealMarketAdapter
        adapter = RealMarketAdapter()
        adapter._keys = []
        assert adapter._api_key == ""

    def test_effective_rate_limit_scales_with_keys(self) -> None:
        from app.pipelines.market_feeds import RealMarketAdapter, _FINNHUB_RATE_LIMIT
        adapter = RealMarketAdapter()
        adapter._keys = ["k1", "k2"]
        effective = len(adapter._keys) * _FINNHUB_RATE_LIMIT
        assert effective == 120
