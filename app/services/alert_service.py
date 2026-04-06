"""Alert notification service — dispatch to Discord/Slack webhooks."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.alert import AlertSubscription
from app.repositories.market_repo import AlertRepository
from app.schemas.health import AlertSubscribeRequest, AlertSubscribeResponse

logger = get_logger(__name__)


class AlertService:
    def __init__(self, alert_repo: AlertRepository) -> None:
        self.alert_repo = alert_repo

    async def subscribe(self, req: AlertSubscribeRequest) -> AlertSubscribeResponse:
        sub = AlertSubscription(
            channel=req.channel,
            webhook_url=str(req.webhook_url),
            region_filter=req.region_filter,
            gti_threshold=req.gti_threshold,
            is_active=True,
            config=req.config,
        )
        await self.alert_repo.create(sub)
        logger.info("alert_subscription_created", channel=req.channel, id=str(sub.id))
        return AlertSubscribeResponse(
            id=sub.id,
            channel=sub.channel,
            region_filter=sub.region_filter,
            gti_threshold=sub.gti_threshold,
            is_active=sub.is_active,
            created_at=sub.created_at,
        )

    async def dispatch_gti_alert(self, gti_value: float, region: str) -> None:
        """Dispatch GTI threshold alerts to all matching subscribers."""
        subs = await self.alert_repo.get_active_for_region(region)
        for sub in subs:
            if sub.gti_threshold is None or gti_value >= sub.gti_threshold:
                await self._send_webhook(sub, gti_value, region)

    async def _send_webhook(
        self, sub: AlertSubscription, gti_value: float, region: str
    ) -> None:
        payload = self._build_payload(sub.channel, gti_value, region)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(str(sub.webhook_url), json=payload)
                resp.raise_for_status()

            # Update last triggered at
            sub.last_triggered_at = datetime.now(UTC)
            logger.info(
                "alert_dispatched",
                channel=sub.channel,
                region=region,
                gti_value=gti_value,
            )
        except Exception as exc:
            logger.error("alert_dispatch_failed", error=str(exc), sub_id=str(sub.id))

    @staticmethod
    def _build_payload(channel: str, gti_value: float, region: str) -> dict:
        message = (
            f"🚨 *GeoTrade Alert* — Region: `{region}`\n"
            f"GTI Value: `{gti_value:.1f}` | ⚠️ Not financial advice."
        )
        if channel == "discord":
            return {"content": message}
        elif channel == "slack":
            return {"text": message}
        else:
            return {"message": message, "gti_value": gti_value, "region": region}
