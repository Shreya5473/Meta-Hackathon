"""Unit tests: GTI engine — decay, contribution, confidence."""
from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.pipelines.gti_engine import (
    GTIEngine,
    _decay_factor,
    _sentiment_to_factor,
    _confidences,
    EventContribution,
)


class TestDecayFunction:
    def test_zero_age_no_decay(self) -> None:
        assert _decay_factor(0.0, 0.05) == pytest.approx(1.0)

    def test_positive_age_decays(self) -> None:
        factor = _decay_factor(10.0, 0.05)
        assert 0 < factor < 1.0

    def test_half_life_approximately_14h(self) -> None:
        # lambda=0.05 → half-life = ln(2)/0.05 ≈ 13.86h
        half_life = math.log(2) / 0.05
        assert _decay_factor(half_life, 0.05) == pytest.approx(0.5, abs=0.01)

    def test_large_age_near_zero(self) -> None:
        assert _decay_factor(200.0, 0.05) < 0.001


class TestSentimentFactor:
    def test_very_negative_sentiment_high_factor(self) -> None:
        assert _sentiment_to_factor(-1.0) == pytest.approx(1.0)

    def test_neutral_sentiment_medium_factor(self) -> None:
        assert _sentiment_to_factor(0.0) == pytest.approx(0.5)

    def test_positive_sentiment_low_factor(self) -> None:
        assert _sentiment_to_factor(1.0) == pytest.approx(0.0)

    def test_output_bounded_by_zero(self) -> None:
        assert _sentiment_to_factor(0.8) >= 0.0


class TestGTIEngine:
    def setup_method(self) -> None:
        self.engine = GTIEngine()

    def _make_event(
        self,
        severity: float = 0.7,
        sentiment: float = -0.5,
        age_hours: float = 1.0,
        region: str = "middle_east",
    ) -> dict:
        return {
            "id": uuid.uuid4(),
            "occurred_at": datetime.now(UTC) - timedelta(hours=age_hours),
            "severity_score": severity,
            "sentiment_score": sentiment,
            "region": region,
            "geo_risk_vector": {region: 0.9, "global": 0.3},
            "classification": "escalation",
        }

    def test_empty_events_returns_zero_without_prior(self) -> None:
        result = self.engine.compute(events=[], region="global")
        assert result.gti_value == 0.0
        assert result.confidence == 0.0

    def test_escalation_event_raises_gti(self) -> None:
        events = [self._make_event(severity=0.9, sentiment=-0.9, age_hours=0.5)]
        result = self.engine.compute(events=events, region="middle_east")
        assert result.gti_value > 0.0

    def test_prior_gti_decays_without_new_events(self) -> None:
        now = datetime.now(UTC)
        r1 = self.engine.compute(
            events=[self._make_event()],
            region="global",
            now=now - timedelta(hours=5),
        )
        r2 = self.engine.compute(
            events=[],
            prev_gti=r1.gti_value,
            prev_ts=now - timedelta(hours=5),
            region="global",
            now=now,
        )
        assert r2.gti_value < r1.gti_value

    def test_gti_bounded_between_0_and_100(self) -> None:
        # Flood with high-severity events
        events = [
            self._make_event(severity=1.0, sentiment=-1.0, age_hours=0.0)
            for _ in range(100)
        ]
        result = self.engine.compute(events=events, region="middle_east")
        assert 0.0 <= result.gti_value <= 100.0

    def test_top_drivers_limited_to_5(self) -> None:
        events = [self._make_event() for _ in range(20)]
        result = self.engine.compute(events=events, region="middle_east")
        assert len(result.top_drivers) <= 5

    def test_confidence_increases_with_event_count(self) -> None:
        few = [self._make_event() for _ in range(2)]
        many = [self._make_event() for _ in range(25)]
        r_few = self.engine.compute(events=few, region="middle_east")
        r_many = self.engine.compute(events=many, region="middle_east")
        assert r_many.confidence > r_few.confidence

    def test_calculation_version_in_output(self) -> None:
        result = self.engine.compute(events=[], region="global")
        assert result.calculation_version is not None
        assert len(result.calculation_version) > 0

    def test_region_filtered_events(self) -> None:
        # Only middle_east events should strongly contribute to middle_east GTI
        me_events = [self._make_event(region="middle_east") for _ in range(5)]
        eu_events = [
            {
                "id": uuid.uuid4(),
                "occurred_at": datetime.now(UTC) - timedelta(hours=1),
                "severity_score": 0.9,
                "sentiment_score": -0.9,
                "region": "europe",
                "geo_risk_vector": {"europe": 0.9},
                "classification": "escalation",
            }
            for _ in range(5)
        ]
        r_me = self.engine.compute(events=me_events, region="middle_east")
        r_eu = self.engine.compute(events=eu_events, region="middle_east")
        # Middle east events contribute more to middle_east GTI
        assert r_me.gti_value > r_eu.gti_value


class TestRecommendationRules:
    """Unit tests for the recommendation rule layer (market_model)."""

    def test_sell_on_high_vol_negative_bias(self) -> None:
        from app.pipelines.market_model import _recommendation
        assert _recommendation(0.85, -0.60, 0.30) == "Sell"

    def test_buy_on_low_vol_positive_bias(self) -> None:
        from app.pipelines.market_model import _recommendation
        assert _recommendation(0.20, 0.60, 0.20) == "Buy"

    def test_hold_on_high_uncertainty(self) -> None:
        from app.pipelines.market_model import _recommendation
        assert _recommendation(0.80, -0.80, 0.90) == "Hold"

    def test_hold_when_ambiguous(self) -> None:
        from app.pipelines.market_model import _recommendation
        assert _recommendation(0.50, 0.10, 0.50) == "Hold"

    def test_recommendation_is_one_of_valid_values(self) -> None:
        from app.pipelines.market_model import _recommendation
        valid = {"Buy", "Sell", "Hold"}
        for vol in [0.1, 0.5, 0.9]:
            for bias in [-0.8, 0.0, 0.8]:
                for unc in [0.1, 0.5, 0.9]:
                    assert _recommendation(vol, bias, unc) in valid


class TestBrierScoreTracker:
    def test_brier_score_perfect_predictor(self) -> None:
        from app.pipelines.market_model import BrierScoreTracker
        tracker = BrierScoreTracker()
        for _ in range(100):
            tracker.update(1.0, 1)
            tracker.update(0.0, 0)
        assert tracker.brier_score == pytest.approx(0.0, abs=1e-9)

    def test_brier_score_worst_predictor(self) -> None:
        from app.pipelines.market_model import BrierScoreTracker
        tracker = BrierScoreTracker()
        for _ in range(100):
            tracker.update(0.0, 1)
            tracker.update(1.0, 0)
        assert tracker.brier_score == pytest.approx(1.0, abs=1e-9)

    def test_to_dict_structure(self) -> None:
        from app.pipelines.market_model import BrierScoreTracker
        tracker = BrierScoreTracker()
        tracker.update(0.7, 1)
        d = tracker.to_dict()
        assert "brier_score" in d
        assert "n_observations" in d
        assert "reliability_bins" in d
        assert d["n_observations"] == 1
