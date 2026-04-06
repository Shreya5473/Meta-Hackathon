"""Interactive Brokers Connector Stub.

Full implementation requires the IB TWS Gateway running locally.
Requires: pip install ib_insync  (NOT installed by default)

Set gateway_host and gateway_port via environment variables or
config/data_sources.yaml.
"""
from __future__ import annotations

import os
import uuid

from app.connectors.base import BaseBrokerConnector, OrderRequest, OrderResult
from app.core.logging import get_logger

logger = get_logger(__name__)


class IBKRConnector(BaseBrokerConnector):
    """Interactive Brokers connector stub.

    Environment variables:
        IBKR_GATEWAY_HOST — default localhost
        IBKR_GATEWAY_PORT — default 4001 (paper) / 4002 (live)
    """

    name = "ibkr"

    def __init__(self) -> None:
        self.host       = os.environ.get("IBKR_GATEWAY_HOST", "localhost")
        self.port       = int(os.environ.get("IBKR_GATEWAY_PORT", "4001"))
        self.paper_mode = self.port == 4001
        self._ib: object | None = None

    async def authorize(self) -> bool:
        try:
            from ib_insync import IB  # type: ignore[import]
            self._check_live_guard()
            ib = IB()
            await ib.connectAsync(self.host, self.port, clientId=1)
            self._ib = ib
            logger.info("ibkr_connected", host=self.host, port=self.port)
            return True
        except ImportError:
            logger.error("ibkr_sdk_missing", hint="pip install ib_insync")
            return False
        except Exception as exc:
            logger.error("ibkr_connect_failed", error=str(exc))
            return False

    async def get_account(self) -> dict:
        if self._ib is None:
            return {"error": "not_connected"}
        try:
            summary = await self._ib.accountSummaryAsync()  # type: ignore[union-attr]
            return {"raw": [str(s) for s in summary[:10]], "paper": self.paper_mode}
        except Exception as exc:
            return {"error": str(exc)}

    async def place_order(self, order: OrderRequest) -> OrderResult:
        self._check_live_guard()
        # Full implementation requires building IB Contract + Order objects.
        # This stub logs the intent and returns a pending status.
        logger.warning(
            "ibkr_order_stub",
            symbol=order.symbol, side=order.side, qty=order.qty,
            hint="Full IBKR order execution not yet implemented.",
        )
        return OrderResult(
            order_id=str(uuid.uuid4()),
            symbol=order.symbol,
            side=order.side,
            qty=order.qty,
            status="pending",
            message="IBKR connector is a stub. Full implementation pending.",
        )

    async def get_positions(self) -> list[dict]:
        if self._ib is None:
            return []
        try:
            positions = await self._ib.reqPositionsAsync()  # type: ignore[union-attr]
            return [{"contract": str(p.contract), "position": p.position} for p in positions]
        except Exception as exc:
            logger.error("ibkr_positions_failed", error=str(exc))
            return []
