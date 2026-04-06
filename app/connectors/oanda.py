"""OANDA v20 Practice API — Broker Connector.

Places paper market orders via the OANDA v20 REST API.
Only Practice (demo) environment is supported; live trading
requires explicit opt-in via BROKER_LIVE_TRADING=true.

Requires: oandapyV20  (pip install oandapyV20)

Environment variables (set in .env):
    OANDA_API_KEY         — Practice API token from OANDA dashboard
    OANDA_ACCOUNT_ID      — Account ID (format: 001-001-xxxxxxx-001)
    OANDA_ENVIRONMENT     — "practice" (default) | "live"
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime

from app.connectors.base import BaseBrokerConnector, OrderRequest, OrderResult
from app.core.logging import get_logger

logger = get_logger(__name__)

# Instruments that OANDA accesses — portfolio symbols → OANDA format
_SYMBOL_MAP: dict[str, str] = {
    "EURUSD": "EUR_USD",
    "GBPUSD": "GBP_USD",
    "USDJPY": "USD_JPY",
    "USDCHF": "USD_CHF",
    "AUDUSD": "AUD_USD",
    "USDCAD": "USD_CAD",
    "NZDUSD": "NZD_USD",
}


def _to_oanda_instrument(symbol: str) -> str:
    """Convert portfolio symbol to OANDA instrument name."""
    upper = symbol.upper().replace("/", "").replace("-", "")
    return _SYMBOL_MAP.get(upper, upper[:3] + "_" + upper[3:] if len(upper) == 6 else upper)


class OandaConnector(BaseBrokerConnector):
    """OANDA v20 broker connector — practice mode by default.

    All order volumes are in OANDA units (1 unit = 1 unit of base currency).
    A qty of 1000 means 1000 EUR for EUR_USD.
    """

    name = "oanda"
    paper_mode = True   # hardcoded — practice only unless explicitly overridden

    def __init__(self) -> None:
        self.api_key = os.environ.get("OANDA_API_KEY", "")
        self.account_id = os.environ.get("OANDA_ACCOUNT_ID", "")
        self.environment = os.environ.get("OANDA_ENVIRONMENT", "practice")
        self._client: object | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_configured(self) -> bool:
        return bool(
            self.api_key
            and self.account_id
            and "REPLACE_WITH" not in self.api_key
            and "your-oanda" not in self.account_id
        )

    def _make_client(self):  # type: ignore[return]
        try:
            import oandapyV20  # type: ignore[import]
            env = "practice" if self.environment != "live" else "live"
            return oandapyV20.API(access_token=self.api_key, environment=env)
        except ImportError:
            raise RuntimeError("oandapyV20 not installed — run: pip install oandapyV20")

    def _sync_place_order(self, instrument: str, units: int) -> dict:
        """Synchronous OANDA order — called via asyncio.to_thread."""
        import oandapyV20.endpoints.orders as oanda_orders  # type: ignore[import]

        client = self._make_client()
        data = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units),  # negative = sell
                "timeInForce": "FOK",  # Fill-or-Kill for market orders
                "positionFill": "DEFAULT",
            }
        }
        req = oanda_orders.OrderCreate(self.account_id, data=data)
        resp = client.request(req)
        return resp  # type: ignore[return-value]

    def _sync_get_account(self) -> dict:
        import oandapyV20.endpoints.accounts as accts  # type: ignore[import]
        client = self._make_client()
        req = accts.AccountDetails(self.account_id)
        resp = client.request(req)
        return resp  # type: ignore[return-value]

    def _sync_get_positions(self) -> list[dict]:
        import oandapyV20.endpoints.positions as pos  # type: ignore[import]
        client = self._make_client()
        req = pos.OpenPositions(self.account_id)
        resp = client.request(req)
        return resp.get("positions", [])  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # BaseBrokerConnector interface
    # ------------------------------------------------------------------

    async def authorize(self) -> bool:
        if not self._is_configured():
            logger.warning("oanda_not_configured", hint="Set OANDA_API_KEY + OANDA_ACCOUNT_ID in .env")
            return False
        try:
            acct = await asyncio.to_thread(self._sync_get_account)
            balance = acct.get("account", {}).get("balance", "?")
            logger.info("oanda_authorized", balance=balance, environment=self.environment)
            return True
        except Exception as exc:
            logger.error("oanda_auth_failed", error=str(exc))
            return False

    async def get_account(self) -> dict:
        if not self._is_configured():
            return {"error": "oanda_not_configured"}
        try:
            raw = await asyncio.to_thread(self._sync_get_account)
            acct = raw.get("account", {})
            return {
                "id": acct.get("id"),
                "currency": acct.get("currency"),
                "balance": float(acct.get("balance", 0)),
                "nav": float(acct.get("NAV", 0)),
                "unrealized_pnl": float(acct.get("unrealizedPL", 0)),
                "realized_pnl": float(acct.get("pl", 0)),
                "paper": self.paper_mode,
                "environment": self.environment,
            }
        except Exception as exc:
            return {"error": str(exc)}

    async def place_order(self, order: OrderRequest) -> OrderResult:
        self._check_live_guard()
        if not self._is_configured():
            return OrderResult(
                order_id=str(uuid.uuid4()),
                symbol=order.symbol,
                side=order.side,
                qty=order.qty,
                status="rejected",
                message="OANDA not configured. Set OANDA_API_KEY + OANDA_ACCOUNT_ID in .env",
                ts=datetime.now(UTC),
            )
        instrument = _to_oanda_instrument(order.symbol)
        # OANDA units: positive = buy, negative = sell
        units = int(order.qty) if order.side == "buy" else -int(order.qty)
        try:
            resp = await asyncio.to_thread(self._sync_place_order, instrument, units)
            fill = resp.get("orderFillTransaction", {})
            order_id = fill.get("id") or resp.get("relatedTransactionIDs", [str(uuid.uuid4())])[0]
            filled_price = float(fill.get("price", 0)) if fill.get("price") else None
            logger.info(
                "oanda_order_placed",
                order_id=order_id,
                instrument=instrument,
                units=units,
                filled_price=filled_price,
            )
            return OrderResult(
                order_id=str(order_id),
                symbol=order.symbol,
                side=order.side,
                qty=order.qty,
                status="accepted",
                filled_price=filled_price,
                ts=datetime.now(UTC),
            )
        except Exception as exc:
            logger.error("oanda_order_failed", error=str(exc), instrument=instrument)
            return OrderResult(
                order_id=str(uuid.uuid4()),
                symbol=order.symbol,
                side=order.side,
                qty=order.qty,
                status="rejected",
                message=str(exc),
                ts=datetime.now(UTC),
            )

    async def get_positions(self) -> list[dict]:
        if not self._is_configured():
            return []
        try:
            raw = await asyncio.to_thread(self._sync_get_positions)
            return [
                {
                    "instrument": p.get("instrument"),
                    "long_units": p.get("long", {}).get("units", "0"),
                    "short_units": p.get("short", {}).get("units", "0"),
                    "unrealized_pnl": float(p.get("unrealizedPL", 0)),
                    "pl": float(p.get("pl", 0)),
                }
                for p in raw
            ]
        except Exception as exc:
            logger.error("oanda_positions_failed", error=str(exc))
            return []
