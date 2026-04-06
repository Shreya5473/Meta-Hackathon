"""Alpaca Markets Broker Connector.

Supports paper trading by default.
To enable live trading: set ALPACA_PAPER=false AND BROKER_LIVE_TRADING=true.

Requires: pip install alpaca-trade-api  (NOT installed by default)
"""
from __future__ import annotations

import os
import uuid

from app.connectors.base import BaseBrokerConnector, OrderRequest, OrderResult
from app.core.logging import get_logger

logger = get_logger(__name__)

_PAPER_URL = "https://paper-api.alpaca.markets"
_LIVE_URL  = "https://api.alpaca.markets"


class AlpacaConnector(BaseBrokerConnector):
    """Alpaca Markets connector — paper mode by default.

    Environment variables:
        ALPACA_API_KEY    — Alpaca API key
        ALPACA_SECRET_KEY — Alpaca secret key
        ALPACA_PAPER      — "true" (default) | "false"
    """

    name = "alpaca"

    def __init__(self) -> None:
        self.api_key    = os.environ.get("ALPACA_API_KEY", "")
        self.secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
        self.paper_mode = os.environ.get("ALPACA_PAPER", "true").lower() != "false"
        self._client: object | None = None

    async def authorize(self) -> bool:
        if not self.api_key or not self.secret_key:
            logger.warning("alpaca_no_credentials")
            return False
        try:
            # Import only when actually used so missing SDK doesn't break app
            import alpaca_trade_api as tradeapi  # type: ignore[import]
            base_url = _PAPER_URL if self.paper_mode else _LIVE_URL
            self._check_live_guard()
            self._client = tradeapi.REST(self.api_key, self.secret_key, base_url)
            account = self._client.get_account()  # type: ignore[union-attr]
            logger.info("alpaca_authorized", status=account.status, paper=self.paper_mode)
            return True
        except ImportError:
            logger.error("alpaca_sdk_missing", hint="pip install alpaca-trade-api")
            return False
        except Exception as exc:
            logger.error("alpaca_auth_failed", error=str(exc))
            return False

    async def get_account(self) -> dict:
        if self._client is None:
            return {"error": "not_authorized"}
        try:
            acct = self._client.get_account()  # type: ignore[union-attr]
            return {
                "id":           acct.id,
                "status":       acct.status,
                "cash":         float(acct.cash),
                "buying_power": float(acct.buying_power),
                "equity":       float(acct.equity),
                "paper":        self.paper_mode,
            }
        except Exception as exc:
            return {"error": str(exc)}

    async def place_order(self, order: OrderRequest) -> OrderResult:
        self._check_live_guard()
        if self._client is None:
            return OrderResult(
                order_id=str(uuid.uuid4()),
                symbol=order.symbol,
                side=order.side,
                qty=order.qty,
                status="rejected",
                message="Connector not authorized. Call authorize() first.",
            )
        try:
            kwargs: dict = dict(
                symbol=order.symbol,
                qty=order.qty,
                side=order.side,
                type=order.order_type,
                time_in_force=order.time_in_force,
            )
            if order.limit_price is not None:
                kwargs["limit_price"] = str(order.limit_price)
            if order.stop_price is not None:
                kwargs["stop_price"] = str(order.stop_price)

            result = self._client.submit_order(**kwargs)  # type: ignore[union-attr]
            logger.info(
                "alpaca_order_placed",
                order_id=result.id, symbol=order.symbol,
                side=order.side, qty=order.qty, paper=self.paper_mode,
            )
            return OrderResult(
                order_id=str(result.id),
                symbol=order.symbol,
                side=order.side,
                qty=order.qty,
                status="accepted",
            )
        except Exception as exc:
            logger.error("alpaca_order_failed", error=str(exc))
            return OrderResult(
                order_id=str(uuid.uuid4()),
                symbol=order.symbol,
                side=order.side,
                qty=order.qty,
                status="rejected",
                message=str(exc),
            )

    async def get_positions(self) -> list[dict]:
        if self._client is None:
            return []
        try:
            positions = self._client.list_positions()  # type: ignore[union-attr]
            return [
                {
                    "symbol":      p.symbol,
                    "qty":         float(p.qty),
                    "side":        p.side,
                    "avg_entry":   float(p.avg_entry_price),
                    "market_val":  float(p.market_value),
                    "unrealized_pnl": float(p.unrealized_pl),
                }
                for p in positions
            ]
        except Exception as exc:
            logger.error("alpaca_positions_failed", error=str(exc))
            return []
