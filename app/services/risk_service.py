"""Service for global risk heatmap and country-level insights."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.repositories.gti_repo import GTIRepository

logger = get_logger(__name__)

# Simplified mapping for demonstration. In production, use a full ISO-3166 mapping.
REGION_COUNTRY_MAP = {
    "middle_east": ["ISR", "IRN", "SAU", "ARE", "EGY", "IRQ", "SYR", "YEM", "QAT"],
    "europe": ["GBR", "FRA", "DEU", "ITA", "ESP", "UKR", "RUS", "POL"],
    "asia_pacific": ["CHN", "JPN", "IND", "AUS", "KOR", "TWN", "VNM"],
    "americas": ["USA", "CAN", "MEX", "BRA", "ARG", "CHL"],
}


class RiskService:
    def __init__(self, gti_repo: GTIRepository) -> None:
        self.gti_repo = gti_repo

    async def get_heatmap(self) -> dict[str, Any]:
        """Fetch all region GTI scores and explode to country level for the map."""
        snapshots = await self.gti_repo.get_all_latest()
        
        points = []
        for snap in snapshots:
            countries = REGION_COUNTRY_MAP.get(snap.region, [])
            for iso in countries:
                points.append({
                    "country_iso": iso,
                    "risk_score": snap.gti_value,
                    "gti_delta": snap.gti_delta_1h,
                    "top_driver": snap.top_drivers[0].get("region") if snap.top_drivers else None
                })
        
        # Add fallback for missing countries via 'global' score
        global_snap = next((s for s in snapshots if s.region == 'global'), None)
        if global_snap:
            all_mapped = set([iso for list_ in REGION_COUNTRY_MAP.values() for iso in list_])
            # Simplified: just return the mapped ones for now.
            
        return {
            "points": points,
            "data_as_of": snapshots[0].ts if snapshots else datetime.now(UTC)
        }
