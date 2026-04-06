"""Trade Setup Calculator.

Computes entry price, stop loss, target price, and risk/reward ratio
for each signal using ATR-based volatility estimation.

Inputs:
    - Current price (from market data or synthetic)
    - Realized volatility
    - Directional bias
    - Action (BUY/SELL/HOLD)

Outputs:
    - entry_price
    - stop_loss
    - target_price
    - risk_reward_ratio
    - volatility_label   (LOW / MEDIUM / HIGH / EXTREME)
    - atr_estimate       (percentage)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)

# Multipliers for stop/target relative to ATR
_STOP_ATR_MULT   = 1.5   # stop = entry ± 1.5 × ATR
_TARGET_ATR_MULT = 3.0   # target = entry ± 3.0 × ATR  →  R:R ≈ 2.0


@dataclass
class TradeSetup:
    """Complete trade setup parameters for one signal."""
    entry_price:       float
    stop_loss:         float
    target_price:      float
    risk_reward_ratio: float
    atr_estimate_pct:  float          # ATR as % of price
    volatility_label:  str            # LOW / MEDIUM / HIGH / EXTREME
    bullish_strength:  float          # 0–1
    bearish_strength:  float          # 0–1
    max_position_pct:  float          # suggested max portfolio % (Kelly-lite)

    def to_dict(self) -> dict:
        return {
            "entry_price":       round(self.entry_price, 4),
            "stop_loss":         round(self.stop_loss, 4),
            "target_price":      round(self.target_price, 4),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "atr_estimate_pct":  round(self.atr_estimate_pct * 100, 2),
            "volatility_label":  self.volatility_label,
            "bullish_strength":  round(self.bullish_strength, 3),
            "bearish_strength":  round(self.bearish_strength, 3),
            "max_position_pct":  round(self.max_position_pct * 100, 1),
        }


def _vol_label(realized_vol: float) -> str:
    if realized_vol < 0.08:
        return "LOW"
    if realized_vol < 0.18:
        return "MEDIUM"
    if realized_vol < 0.35:
        return "HIGH"
    return "EXTREME"


def _atr_from_vol(realized_vol: float, price: float, horizon_days: int = 1) -> float:
    """Approximate ATR from annualized volatility.

    ATR_daily ≈ σ_annual / sqrt(252) × price
    """
    daily_vol = realized_vol / math.sqrt(252)
    return daily_vol * price * math.sqrt(horizon_days)


def _kelly_fraction(
    win_rate: float,
    rr_ratio: float,
    confidence: float,
) -> float:
    """Simplified fractional Kelly position sizing.

    Kelly = (p × rr - (1-p)) / rr
    We apply a 0.25 fraction for safety + confidence scaling.
    """
    kelly = (win_rate * rr_ratio - (1 - win_rate)) / max(rr_ratio, 0.01)
    kelly = max(0.0, kelly)
    return min(0.05, kelly * 0.25 * confidence)  # cap at 5% of portfolio


def compute_trade_setup(
    action: str,
    price: float,
    realized_vol: float,
    directional_bias: float,
    confidence: float,
    win_rate: float = 0.55,
) -> TradeSetup:
    """Compute trade setup for a given signal.

    Args:
        action:          "BUY" | "SELL" | "HOLD"
        price:           Current market price
        realized_vol:    Annualized realized volatility (0–1)
        directional_bias: -1 to 1 (model output)
        confidence:      0–1 signal confidence
        win_rate:        Historical win rate (from backtesting)
    """
    # Guard: clamp inputs
    price        = max(price, 0.0001)
    realized_vol = max(min(realized_vol, 2.0), 0.01)
    confidence   = max(min(confidence, 1.0), 0.0)

    atr = _atr_from_vol(realized_vol, price)

    vol_label = _vol_label(realized_vol)
    atr_pct   = atr / price

    if action == "BUY":
        entry      = price
        stop_loss  = entry - atr * _STOP_ATR_MULT
        target     = entry + atr * _TARGET_ATR_MULT
    elif action == "SELL":
        entry      = price
        stop_loss  = entry + atr * _STOP_ATR_MULT
        target     = entry - atr * _TARGET_ATR_MULT
    else:  # HOLD
        entry      = price
        stop_loss  = price - atr * 1.0
        target     = price + atr * 1.0

    risk   = abs(entry - stop_loss)
    reward = abs(target - entry)
    rr     = reward / max(risk, 1e-8)

    # Directional strength → bullish / bearish
    bias   = max(min(directional_bias, 1.0), -1.0)
    bull   = max(0.0, bias)
    bear   = max(0.0, -bias)
    # Normalize so both sum ≤ 1 and reflect confidence
    bull   = round(bull * confidence, 3)
    bear   = round(bear * confidence, 3)

    max_pos = _kelly_fraction(win_rate, rr, confidence)

    return TradeSetup(
        entry_price=round(entry, 6),
        stop_loss=round(stop_loss, 6),
        target_price=round(target, 6),
        risk_reward_ratio=round(rr, 2),
        atr_estimate_pct=round(atr_pct, 4),
        volatility_label=vol_label,
        bullish_strength=bull,
        bearish_strength=bear,
        max_position_pct=round(max_pos, 4),
    )
