"""Abstract Broker Connector Interface.

All broker implementations must subclass BaseBrokerConnector and
implement the four abstract methods below.

IMPORTANT: This module intentionally does NOT import any broker SDK.
The import happens only inside the concrete connector classes so that
missing SDKs do not break the rest of the application.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal


@dataclass
class OrderRequest:
    """Represents an order to be placed via a broker."""
    symbol:      str
    side:        Literal["buy", "sell"]
    qty:         float                   # number of units / shares
    order_type:  Literal["market", "limit", "stop_limit"] = "market"
    limit_price: float | None = None
    stop_price:  float | None = None
    time_in_force: Literal["day", "gtc", "ioc"] = "day"
    # Metadata — linked back to the GEOTRADE signal
    signal_id:   str | None = None
    note:        str = ""


@dataclass
class OrderResult:
    """Result returned after placing an order."""
    order_id:    str
    symbol:      str
    side:        str
    qty:         float
    status:      Literal["accepted", "rejected", "pending", "filled", "cancelled"]
    filled_price: float | None = None
    message:     str = ""
    ts:          datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "order_id":    self.order_id,
            "symbol":      self.symbol,
            "side":        self.side,
            "qty":         self.qty,
            "status":      self.status,
            "filled_price": self.filled_price,
            "message":     self.message,
            "ts":          self.ts.isoformat(),
        }


class BaseBrokerConnector(ABC):
    """Abstract interface that all broker connectors must implement.

    ⚠️  Automatic execution is disabled by default.
        Users must call authorize() and explicitly enable live trading
        via BROKER_LIVE_TRADING=true in the environment.
    """

    name: str = "base"
    paper_mode: bool = True

    @abstractmethod
    async def authorize(self) -> bool:
        """Verify API credentials and return True if connected."""

    @abstractmethod
    async def get_account(self) -> dict:
        """Return account balance, buying power, and positions."""

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Submit an order. Must raise if paper_mode is False and not authorized."""

    @abstractmethod
    async def get_positions(self) -> list[dict]:
        """Return list of open positions."""

    def _check_live_guard(self) -> None:
        """Raise if live trading is attempted without explicit enable."""
        import os
        if not self.paper_mode and os.environ.get("BROKER_LIVE_TRADING") != "true":
            raise PermissionError(
                "Live trading is disabled. Set BROKER_LIVE_TRADING=true "
                "in your environment after reviewing the risks."
            )

    def __repr__(self) -> str:
        mode = "PAPER" if self.paper_mode else "LIVE ⚠️"
        return f"<{self.__class__.__name__} mode={mode}>"
