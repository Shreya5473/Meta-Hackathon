"""Impact graph service — API-facing service for graph operations."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.pipelines.impact_graph import ImpactGraph, PropagationResult, get_impact_graph

logger = get_logger(__name__)


class ImpactGraphService:
    """Service layer for querying and operating on the impact graph."""

    def __init__(self, graph: ImpactGraph | None = None) -> None:
        self.graph = graph or get_impact_graph()

    def get_graph_data(self) -> dict[str, Any]:
        """Return serializable graph for visualization."""
        return self.graph.to_serializable()

    def propagate_shock(
        self,
        source_country: str,
        event_type: str,
        severity: float,
    ) -> dict[str, Any]:
        """Propagate a shock and return structured results."""
        result = self.graph.propagate_shock(
            source_country=source_country,
            event_type=event_type,
            severity=severity,
        )

        return {
            "source_country": result.source_country,
            "event_type": result.event_type,
            "severity": result.severity,
            "total_nodes_affected": result.total_nodes_affected,
            "commodity_impacts": [
                {
                    "id": ci.node_id,
                    "impact_score": ci.impact_score,
                    "path": ci.path,
                    "hops": ci.hop_count,
                }
                for ci in result.commodity_impacts
            ],
            "sector_impacts": [
                {
                    "id": si.node_id,
                    "impact_score": si.impact_score,
                    "path": si.path,
                    "hops": si.hop_count,
                }
                for si in result.sector_impacts
            ],
            "asset_impacts": [
                {
                    "id": ai.node_id,
                    "impact_score": ai.impact_score,
                    "path": ai.path,
                    "hops": ai.hop_count,
                }
                for ai in result.asset_impacts
            ],
            "country_spillover": [
                {
                    "id": cs.node_id,
                    "impact_score": cs.impact_score,
                    "path": cs.path,
                    "hops": cs.hop_count,
                }
                for cs in result.country_spillover
            ],
        }

    def get_asset_exposure(self, asset_id: str) -> dict[str, float]:
        """Return country/commodity exposure for a given asset."""
        return self.graph.get_asset_exposure(asset_id)
