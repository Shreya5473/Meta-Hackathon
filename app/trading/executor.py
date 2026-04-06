"""Trade Executor — OrderManager.

Consumes ML signals (vol_spike_prob, directional_bias, recommendation)
produced by :mod:`app.pipelines.market_model` and converts them into
paper orders executed on the OANDA v20 Practice API.

Signal → Action mapping
------------------------
* vol_spike_prob > 0.70 AND directional_bias < -0.02  → **SELL** (de-risk)
* vol_spike_prob < 0.30 AND directional_bias > +0.02  → **BUY**  (opportunity)
* everything else                                      → **HOLD**

All trade decisions (including HOLDs) are written to the ``trade_log``
table for audit and P&L tracking.

Only OANDA FX instruments are executed automatically.  Non-forex
holdings (equities, indices) are logged as HOLD unless a compatible
broker connector is added later.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import OrderRequest
from app.connectors.oanda import OandaConnector
from app.core.logging import get_logger
from app.models.trade import TradeLog

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Instruments routable to OANDA (portfolio symbol → tradeable)
_OANDA_SYMBOLS: frozenset[str] = frozenset(
    {"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"}
)

# Default notional unit size per F. trade (units of base currency)
_DEFAULT_UNITS = int(os.environ.get("TRADE_DEFAULT_UNITS", "1000"))

# Signal thresholds
_SELL_VOL_THRESHOLD = 0.70
_SELL_BIAS_THRESHOLD = -0.02
_BUY_VOL_THRESHOLD = 0.30
_BUY_BIAS_THRESHOLD = 0.02


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class SignalInput:
    """ML signal for a single holding."""

    symbol: str
    vol_spike_prob: float
    directional_bias: float
    recommendation: str
    weight: float = 1.0


@dataclass
class TradeDecision:
    """The executor's decision for one holding."""

    symbol: str
    action: str          # "buy" | "sell" | "hold"
    reason: str
    quantity: float | None = None
    fill_price: float | None = None
    order_id: str | None = None
    status: str = "hold"
    broker: str = "paper"
    signal_vol_spike: float | None = None
    signal_bias: float | None = None
    recommendation: str | None = None
    note: str = ""
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "reason": self.reason,
            "quantity": self.quantity,
            "fill_price": self.fill_price,
            "order_id": self.order_id,
            "status": self.status,
            "broker": self.broker,
            "signal_vol_spike": self.signal_vol_spike,
            "signal_bias": self.signal_bias,
            "recommendation": self.recommendation,
            "note": self.note,
            "ts": self.ts.isoformat(),
        }


# ---------------------------------------------------------------------------
# OrderManager
# ---------------------------------------------------------------------------


class OrderManager:
    """Evaluate ML signals and execute paper orders via OANDA."""

    def __init__(self) -> None:
        self._oanda = OandaConnector()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def process_signals(
        self,
        email: str,
        signals: list[SignalInput],
        db: AsyncSession,
    ) -> list[TradeDecision]:
        """Evaluate each signal and place orders where warranted.

        Args:
            email:   Portfolio owner (anonymous email key).
            signals: ML signals from :func:`~app.pipelines.market_model`.
            db:      Async DB session for writing trade_log rows.

        Returns:
            List of :class:`TradeDecision` objects (one per signal).
        """
        decisions: list[TradeDecision] = []

        for sig in signals:
            action = self._determine_action(sig)
            decision = await self._execute_action(sig, action)
            decisions.append(decision)

        # Persist all decisions to trade_log in a single batch
        await self._log_trades(email, decisions, db)
        return decisions

    # ------------------------------------------------------------------
    # Signal → action
    # ------------------------------------------------------------------

    def _determine_action(self, sig: SignalInput) -> str:
        """Apply threshold logic to determine buy / sell / hold."""
        if (
            sig.vol_spike_prob > _SELL_VOL_THRESHOLD
            and sig.directional_bias < _SELL_BIAS_THRESHOLD
        ):
            return "sell"
        if (
            sig.vol_spike_prob < _BUY_VOL_THRESHOLD
            and sig.directional_bias > _BUY_BIAS_THRESHOLD
        ):
            return "buy"
        return "hold"

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _execute_action(
        self, sig: SignalInput, action: str
    ) -> TradeDecision:
        base = TradeDecision(
            symbol=sig.symbol,
            action=action,
            reason=self._reason_string(sig, action),
            signal_vol_spike=sig.vol_spike_prob,
            signal_bias=sig.directional_bias,
            recommendation=sig.recommendation,
        )

        if action == "hold":
            base.status = "hold"
            base.broker = "none"
            base.note = "Signal within neutral zone — no trade needed"
            return base

        # Determine executor: OANDA for forex, paper-log for others
        sym_upper = sig.symbol.upper()
        if sym_upper in _OANDA_SYMBOLS:
            return await self._execute_oanda(base, action, _DEFAULT_UNITS)
        else:
            # Non-forex: log as a paper signal (no live broker for equities yet)
            base.status = "paper_signal"
            base.broker = "paper"
            base.quantity = _DEFAULT_UNITS
            base.note = f"No live broker for {sig.symbol}; logged as paper signal"
            logger.info(
                "trade_paper_signal",
                symbol=sig.symbol,
                action=action,
                vol=sig.vol_spike_prob,
                bias=sig.directional_bias,
            )
            return base

    async def _execute_oanda(
        self, decision: TradeDecision, action: str, units: int
    ) -> TradeDecision:
        """Place a market order via the OANDA Practice API."""
        order_req = OrderRequest(
            symbol=decision.symbol,
            side=action,
            qty=float(units),
            order_type="market",
            note=f"GeoTrade automated signal vol={decision.signal_vol_spike:.3f} bias={decision.signal_bias:.4f}",
        )

        try:
            result = await self._oanda.place_order(order_req)
            decision.order_id = result.order_id
            decision.status = result.status
            decision.fill_price = result.filled_price
            decision.quantity = units
            decision.broker = "oanda"
            if result.status == "accepted":
                logger.info(
                    "trade_executed",
                    symbol=decision.symbol,
                    action=action,
                    units=units,
                    fill=result.filled_price,
                    order_id=result.order_id,
                )
            else:
                decision.note = result.message
                logger.warning(
                    "trade_rejected",
                    symbol=decision.symbol,
                    action=action,
                    reason=result.message,
                )
        except Exception as exc:
            decision.status = "error"
            decision.broker = "oanda"
            decision.note = str(exc)
            logger.error("trade_execution_error", symbol=decision.symbol, error=str(exc))

        return decision

    # ------------------------------------------------------------------
    # Logging to DB
    # ------------------------------------------------------------------

    async def _log_trades(
        self,
        email: str,
        decisions: list[TradeDecision],
        db: AsyncSession,
    ) -> None:
        for dec in decisions:
            row = TradeLog(
                id=uuid.uuid4(),
                ts=dec.ts,
                email=email,
                symbol=dec.symbol,
                action=dec.action,
                quantity=dec.quantity,
                price=dec.fill_price,
                signal_vol_spike=dec.signal_vol_spike,
                signal_bias=dec.signal_bias,
                recommendation=dec.recommendation,
                order_id=dec.order_id,
                status=dec.status,
                broker=dec.broker,
                note=dec.note,
            )
            db.add(row)
        try:
            await db.commit()
            logger.info("trade_log_written", count=len(decisions), email=email)
        except Exception as exc:
            await db.rollback()
            logger.error("trade_log_write_failed", error=str(exc))

    @staticmethod
    def _reason_string(sig: SignalInput, action: str) -> str:
        return (
            f"vol_spike={sig.vol_spike_prob:.3f} bias={sig.directional_bias:.4f}"
            f" → {action.upper()}"
        )
