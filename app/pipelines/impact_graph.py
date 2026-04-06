"""Event → Market Impact Graph Engine.

A graph-based model that connects countries, events, commodities, sectors,
and financial assets. Geopolitical shocks propagate through the network using
weighted edges that model real-world supply-chain and trade dependencies.

Architecture
────────────
Nodes:
    COUNTRY   — ISO-3166 alpha-3 codes (USA, CHN, IRN, …)
    COMMODITY — crude_oil, gold, wheat, natural_gas, copper, …
    SECTOR    — energy, defense, technology, financials, …
    ASSET     — ticker symbols (SPY, GLD, USO, …)

Edges:
    COUNTRY → COMMODITY   (production / consumption weight)
    COUNTRY → SECTOR      (industry exposure weight)
    COMMODITY → ASSET     (commodity-tracking weight)
    SECTOR → ASSET        (sector-tracking weight)
    COUNTRY → COUNTRY     (trade dependency weight)

Shock Propagation:
    When a country experiences a geopolitical event, the engine propagates
    the shock through the graph using a BFS-like algorithm with damping.
    Each hop reduces the impact by a configurable attenuation factor.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class NodeType(str, Enum):
    COUNTRY = "country"
    COMMODITY = "commodity"
    SECTOR = "sector"
    ASSET = "asset"
    EVENT_TYPE = "event_type"


@dataclass
class GraphNode:
    id: str
    node_type: NodeType
    label: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    weight: float  # 0..1 propagation strength
    relationship: str  # e.g. "produces", "tracks", "trades_with"


@dataclass
class ShockImpact:
    """Result of propagating a shock through the impact graph."""
    node_id: str
    node_type: NodeType
    impact_score: float  # 0..1
    path: list[str]  # propagation path from source
    hop_count: int


@dataclass
class PropagationResult:
    """Full result of shock propagation."""
    source_country: str
    event_type: str
    severity: float
    commodity_impacts: list[ShockImpact]
    sector_impacts: list[ShockImpact]
    asset_impacts: list[ShockImpact]
    country_spillover: list[ShockImpact]
    total_nodes_affected: int


class ImpactGraph:
    """BFS shock propagation on a pre-built geopolitical knowledge graph."""

    def __init__(self, damping: float = 0.6, max_hops: int = 4) -> None:
        self.damping = damping
        self.max_hops = max_hops
        self.nodes: dict[str, GraphNode] = {}
        self.adjacency: dict[str, list[GraphEdge]] = defaultdict(list)
        self._built = False

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        self.adjacency[edge.source].append(edge)
        # Bidirectional for trade dependencies
        if edge.relationship in ("trades_with", "allied_with"):
            reverse = GraphEdge(
                source=edge.target,
                target=edge.source,
                weight=edge.weight * 0.8,
                relationship=edge.relationship,
            )
            self.adjacency[edge.target].append(reverse)

    def build_default_graph(self) -> None:
        """Construct the default geopolitical knowledge graph."""
        if self._built:
            return
        self._build_countries()
        self._build_commodities()
        self._build_sectors()
        self._build_assets()
        self._build_event_types()
        self._build_edges()
        self._built = True
        logger.info(
            "impact_graph_built",
            nodes=len(self.nodes),
            edges=sum(len(v) for v in self.adjacency.values()),
        )

    def propagate_shock(
        self,
        source_country: str,
        event_type: str,
        severity: float,
        event_multipliers: dict[str, float] | None = None,
    ) -> PropagationResult:
        """Propagate a geopolitical shock through the graph using BFS."""
        self.build_default_graph()

        # Event type determines which edge relationships are amplified
        multipliers = event_multipliers or _EVENT_TYPE_MULTIPLIERS.get(
            event_type, {}
        )

        visited: dict[str, ShockImpact] = {}
        queue: deque[tuple[str, float, list[str], int]] = deque()

        # Start from the source country
        if source_country not in self.nodes:
            logger.warning("unknown_source_country", country=source_country)
            return PropagationResult(
                source_country=source_country,
                event_type=event_type,
                severity=severity,
                commodity_impacts=[],
                sector_impacts=[],
                asset_impacts=[],
                country_spillover=[],
                total_nodes_affected=0,
            )

        initial_impact = severity
        queue.append((source_country, initial_impact, [source_country], 0))

        while queue:
            current_id, current_impact, path, hop = queue.popleft()

            if current_id in visited:
                # Keep highest impact
                if visited[current_id].impact_score >= current_impact:
                    continue

            node = self.nodes.get(current_id)
            if node is None:
                continue

            visited[current_id] = ShockImpact(
                node_id=current_id,
                node_type=node.node_type,
                impact_score=round(min(1.0, current_impact), 4),
                path=path,
                hop_count=hop,
            )

            if hop >= self.max_hops:
                continue

            # Propagate to neighbors
            for edge in self.adjacency.get(current_id, []):
                rel_multiplier = multipliers.get(edge.relationship, 1.0)
                propagated = (
                    current_impact
                    * edge.weight
                    * self.damping
                    * rel_multiplier
                )

                if propagated < 0.01:  # noise floor
                    continue

                if edge.target not in visited or visited[edge.target].impact_score < propagated:
                    queue.append((
                        edge.target,
                        propagated,
                        path + [edge.target],
                        hop + 1,
                    ))

        # Partition results by node type
        commodity_impacts = []
        sector_impacts = []
        asset_impacts = []
        country_spillover = []

        for impact in visited.values():
            if impact.node_id == source_country:
                continue
            if impact.node_type == NodeType.COMMODITY:
                commodity_impacts.append(impact)
            elif impact.node_type == NodeType.SECTOR:
                sector_impacts.append(impact)
            elif impact.node_type == NodeType.ASSET:
                asset_impacts.append(impact)
            elif impact.node_type == NodeType.COUNTRY:
                country_spillover.append(impact)

        # Sort each by impact descending
        for lst in (commodity_impacts, sector_impacts, asset_impacts, country_spillover):
            lst.sort(key=lambda x: x.impact_score, reverse=True)

        return PropagationResult(
            source_country=source_country,
            event_type=event_type,
            severity=severity,
            commodity_impacts=commodity_impacts,
            sector_impacts=sector_impacts,
            asset_impacts=asset_impacts,
            country_spillover=country_spillover,
            total_nodes_affected=len(visited) - 1,
        )

    def get_asset_exposure(self, asset_id: str) -> dict[str, float]:
        """Return all countries + commodities that influence a given asset."""
        self.build_default_graph()
        exposure: dict[str, float] = {}

        # Reverse BFS from asset
        queue: deque[tuple[str, float]] = deque([(asset_id, 1.0)])
        visited = set()

        while queue:
            current, weight = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            # Find edges pointing TO current
            for source_id, edges in self.adjacency.items():
                for edge in edges:
                    if edge.target == current:
                        prop = weight * edge.weight
                        if prop > 0.01:
                            node = self.nodes.get(source_id)
                            if node and node.node_type in (NodeType.COUNTRY, NodeType.COMMODITY):
                                exposure[source_id] = max(
                                    exposure.get(source_id, 0.0), round(prop, 4)
                                )
                            queue.append((source_id, prop * self.damping))

        return dict(sorted(exposure.items(), key=lambda x: x[1], reverse=True))

    # ── Graph construction helpers ────────────────────────────────────────────

    def _build_countries(self) -> None:
        countries = {
            "USA": "United States", "CHN": "China", "RUS": "Russia",
            "IRN": "Iran", "SAU": "Saudi Arabia", "ISR": "Israel",
            "GBR": "United Kingdom", "DEU": "Germany", "FRA": "France",
            "JPN": "Japan", "IND": "India", "AUS": "Australia",
            "BRA": "Brazil", "CAN": "Canada", "MEX": "Mexico",
            "TWN": "Taiwan", "KOR": "South Korea", "ARE": "UAE",
            "UKR": "Ukraine", "POL": "Poland", "ITA": "Italy",
            "ESP": "Spain", "NGA": "Nigeria", "IRQ": "Iraq",
            "YEM": "Yemen", "SYR": "Syria", "EGY": "Egypt",
            "TUR": "Turkey", "QAT": "Qatar", "VNM": "Vietnam",
            "ARG": "Argentina", "CHL": "Chile", "COL": "Colombia",
            "VEN": "Venezuela", "LBY": "Libya", "NOR": "Norway",
            "IDN": "Indonesia", "MYS": "Malaysia", "THA": "Thailand",
            "PHL": "Philippines", "ZAF": "South Africa",
        }
        for iso, name in countries.items():
            self.add_node(GraphNode(
                id=iso, node_type=NodeType.COUNTRY,
                label=name, metadata={"iso3": iso},
            ))

    def _build_commodities(self) -> None:
        commodities = [
            "crude_oil", "natural_gas", "gold", "silver", "copper",
            "wheat", "corn", "soybeans", "iron_ore", "lithium",
            "uranium", "palladium", "platinum", "aluminum",
            "rare_earths", "semiconductors", "lng",
        ]
        for c in commodities:
            self.add_node(GraphNode(
                id=c, node_type=NodeType.COMMODITY,
                label=c.replace("_", " ").title(),
            ))

    def _build_sectors(self) -> None:
        sectors = [
            "energy", "defense", "technology", "financials",
            "commodities", "utilities", "consumer_discretionary",
            "consumer_staples", "healthcare", "industrials",
            "materials", "real_estate", "communications",
            "transportation", "agriculture",
            "metals", "crypto",   # added for XAUUSD/XAGUSD and BTCUSD
        ]
        for s in sectors:
            self.add_node(GraphNode(
                id=s, node_type=NodeType.SECTOR,
                label=s.replace("_", " ").title(),
            ))

    def _build_assets(self) -> None:
        assets = {
            # Commodities
            "USO": {"sector": "energy", "class": "commodity", "label": "US Oil Fund"},
            "GLD": {"sector": "commodities", "class": "commodity", "label": "SPDR Gold"},
            "SLV": {"sector": "commodities", "class": "commodity", "label": "iShares Silver"},
            "UNG": {"sector": "energy", "class": "commodity", "label": "US Natural Gas"},
            "WEAT": {"sector": "agriculture", "class": "commodity", "label": "Wheat ETF"},
            "CORN": {"sector": "agriculture", "class": "commodity", "label": "Corn ETF"},
            # Equities
            "SPY": {"sector": "broad_market", "class": "equity", "label": "S&P 500"},
            "QQQ": {"sector": "technology", "class": "equity", "label": "Nasdaq 100"},
            "XLE": {"sector": "energy", "class": "equity", "label": "Energy Select"},
            "XLF": {"sector": "financials", "class": "equity", "label": "Financial Select"},
            "ITA": {"sector": "defense", "class": "equity", "label": "iShares Aerospace/Defense"},
            "XLK": {"sector": "technology", "class": "equity", "label": "Tech Select"},
            "XLV": {"sector": "healthcare", "class": "equity", "label": "Healthcare Select"},
            "JETS": {"sector": "transportation", "class": "equity", "label": "US Global Jets"},
            "EEM": {"sector": "broad_market", "class": "equity", "label": "Emerging Markets"},
            # Defense stocks (focus universe)
            "LMT": {"sector": "defense", "class": "equity", "label": "Lockheed Martin"},
            "RTX": {"sector": "defense", "class": "equity", "label": "Raytheon Technologies"},
            "NOC": {"sector": "defense", "class": "equity", "label": "Northrop Grumman"},
            "GD":  {"sector": "defense", "class": "equity", "label": "General Dynamics"},
            "BA":  {"sector": "defense", "class": "equity", "label": "Boeing"},
            # Commodity canonical symbols (resolve to ETF proxies via FINNHUB_SYMBOL_MAP)
            "XAUUSD": {"sector": "metals",  "class": "commodity", "label": "Gold"},
            "XAGUSD": {"sector": "metals",  "class": "commodity", "label": "Silver"},
            "WTI":    {"sector": "energy",  "class": "commodity", "label": "WTI Crude Oil"},
            "NATGAS": {"sector": "energy",  "class": "commodity", "label": "Natural Gas"},
            "BTCUSD": {"sector": "crypto",  "class": "crypto",    "label": "Bitcoin"},
            # Currencies / bonds
            "UUP": {"sector": "financials", "class": "currency", "label": "US Dollar Index"},
            "FXY": {"sector": "financials", "class": "currency", "label": "Japanese Yen"},
            "FXE": {"sector": "financials", "class": "currency", "label": "Euro"},
            "TLT": {"sector": "financials", "class": "bond", "label": "20+ Year Treasury"},
            "TIP": {"sector": "financials", "class": "bond", "label": "TIPS"},
        }
        for symbol, meta in assets.items():
            self.add_node(GraphNode(
                id=symbol, node_type=NodeType.ASSET,
                label=meta["label"], metadata=meta,
            ))

    def _build_event_types(self) -> None:
        event_types = [
            "military_escalation", "sanctions", "trade_restrictions",
            "energy_supply_disruption", "cyber_attack",
            "political_instability", "economic_policy_change",
            "diplomatic_breakdown", "territorial_dispute",
            "nuclear_threat", "refugee_crisis",
        ]
        for et in event_types:
            self.add_node(GraphNode(
                id=et, node_type=NodeType.EVENT_TYPE,
                label=et.replace("_", " ").title(),
            ))

    def _build_edges(self) -> None:
        # ── Country → Commodity (production weights) ──────────────────────
        _production = [
            # Major oil producers
            ("SAU", "crude_oil", 0.95, "produces"),
            ("RUS", "crude_oil", 0.85, "produces"),
            ("USA", "crude_oil", 0.80, "produces"),
            ("IRN", "crude_oil", 0.80, "produces"),
            ("IRQ", "crude_oil", 0.75, "produces"),
            ("ARE", "crude_oil", 0.70, "produces"),
            ("NGA", "crude_oil", 0.65, "produces"),
            ("LBY", "crude_oil", 0.60, "produces"),
            ("NOR", "crude_oil", 0.55, "produces"),
            ("CAN", "crude_oil", 0.60, "produces"),
            ("VEN", "crude_oil", 0.55, "produces"),
            # Natural gas
            ("RUS", "natural_gas", 0.90, "produces"),
            ("USA", "natural_gas", 0.75, "produces"),
            ("QAT", "natural_gas", 0.85, "produces"),
            ("IRN", "natural_gas", 0.70, "produces"),
            ("NOR", "natural_gas", 0.65, "produces"),
            ("AUS", "natural_gas", 0.60, "produces"),
            # LNG
            ("QAT", "lng", 0.90, "produces"),
            ("AUS", "lng", 0.80, "produces"),
            ("USA", "lng", 0.70, "produces"),
            # Gold
            ("CHN", "gold", 0.75, "produces"),
            ("AUS", "gold", 0.70, "produces"),
            ("RUS", "gold", 0.65, "produces"),
            ("ZAF", "gold", 0.55, "produces"),
            # Wheat
            ("RUS", "wheat", 0.80, "produces"),
            ("UKR", "wheat", 0.75, "produces"),
            ("USA", "wheat", 0.65, "produces"),
            ("CAN", "wheat", 0.60, "produces"),
            ("AUS", "wheat", 0.55, "produces"),
            ("FRA", "wheat", 0.50, "produces"),
            # Copper
            ("CHL", "copper", 0.85, "produces"),
            ("CHN", "copper", 0.60, "produces"),
            ("PER", "copper", 0.55, "produces"),  # Won't have node but edge is safe
            # Semiconductors
            ("TWN", "semiconductors", 0.95, "produces"),
            ("KOR", "semiconductors", 0.80, "produces"),
            ("CHN", "semiconductors", 0.60, "produces"),
            ("USA", "semiconductors", 0.55, "produces"),
            ("JPN", "semiconductors", 0.50, "produces"),
            # Rare earths
            ("CHN", "rare_earths", 0.95, "produces"),
            ("AUS", "rare_earths", 0.40, "produces"),
            # Lithium
            ("AUS", "lithium", 0.70, "produces"),
            ("CHL", "lithium", 0.65, "produces"),
            ("CHN", "lithium", 0.55, "produces"),
            ("ARG", "lithium", 0.50, "produces"),
            # Iron ore
            ("AUS", "iron_ore", 0.85, "produces"),
            ("BRA", "iron_ore", 0.75, "produces"),
            # Corn / soybeans
            ("USA", "corn", 0.75, "produces"),
            ("BRA", "corn", 0.60, "produces"),
            ("USA", "soybeans", 0.70, "produces"),
            ("BRA", "soybeans", 0.75, "produces"),
            ("ARG", "soybeans", 0.55, "produces"),
            # Uranium
            ("KAZ", "uranium", 0.85, "produces"),
            ("AUS", "uranium", 0.50, "produces"),
            ("CAN", "uranium", 0.55, "produces"),
        ]
        for src, tgt, w, rel in _production:
            if src in self.nodes and tgt in self.nodes:
                self.add_edge(GraphEdge(source=src, target=tgt, weight=w, relationship=rel))

        # ── Country → Sector (industry weight) ───────────────────────────
        _country_sector = [
            ("USA", "technology", 0.90), ("USA", "financials", 0.85),
            ("USA", "defense", 0.90), ("USA", "healthcare", 0.80),
            ("CHN", "technology", 0.80), ("CHN", "industrials", 0.85),
            ("CHN", "materials", 0.80),
            ("TWN", "technology", 0.95),
            ("KOR", "technology", 0.85),
            ("JPN", "technology", 0.75), ("JPN", "industrials", 0.70),
            ("DEU", "industrials", 0.80), ("DEU", "technology", 0.60),
            ("GBR", "financials", 0.80),
            ("SAU", "energy", 0.95), ("IRN", "energy", 0.85),
            ("RUS", "energy", 0.90), ("RUS", "defense", 0.75),
            ("ISR", "defense", 0.80), ("ISR", "technology", 0.75),
            ("IND", "technology", 0.65), ("IND", "industrials", 0.60),
            ("BRA", "agriculture", 0.75), ("BRA", "materials", 0.70),
            ("AUS", "materials", 0.80), ("AUS", "energy", 0.60),
        ]
        for src, tgt, w in _country_sector:
            if src in self.nodes and tgt in self.nodes:
                self.add_edge(GraphEdge(source=src, target=tgt, weight=w, relationship="industry_exposure"))

        # ── Commodity → Asset (tracking) ─────────────────────────────────
        _commodity_asset = [
            ("crude_oil", "USO",    0.95), ("crude_oil", "XLE",    0.70),
            ("crude_oil", "WTI",    0.98),                                  # canonical symbol
            ("natural_gas", "UNG",  0.90), ("natural_gas", "XLE",  0.50),
            ("natural_gas", "NATGAS", 0.97),                                # canonical symbol
            ("gold",   "GLD",       0.95), ("gold",   "XAUUSD",    0.98),  # canonical symbol
            ("silver", "SLV",       0.90), ("silver", "XAGUSD",    0.97),  # canonical symbol
            ("wheat",  "WEAT",      0.90), ("corn",   "CORN",      0.90),
            ("semiconductors", "QQQ", 0.65), ("semiconductors", "XLK", 0.70),
        ]
        for src, tgt, w in _commodity_asset:
            if src in self.nodes and tgt in self.nodes:
                self.add_edge(GraphEdge(source=src, target=tgt, weight=w, relationship="tracks"))

        # ── Sector → Asset (ETF mapping) ─────────────────────────────────
        _sector_asset = [
            ("energy", "XLE", 0.90), ("energy", "USO", 0.70),
            ("energy", "WTI", 0.95),    ("energy", "NATGAS", 0.88),
            ("defense", "ITA", 0.90),
            ("defense", "LMT", 0.88),   ("defense", "RTX", 0.86),
            ("defense", "NOC", 0.84),   ("defense", "GD", 0.82),
            ("defense", "BA", 0.78),
            ("technology", "QQQ", 0.85), ("technology", "XLK", 0.90),
            ("financials", "XLF", 0.90), ("financials", "TLT", 0.50),
            ("healthcare", "XLV", 0.90),
            ("transportation", "JETS", 0.85),
            ("metals", "XAUUSD", 0.95),  ("metals", "XAGUSD", 0.88),
            ("crypto", "BTCUSD", 0.90),
        ]
        for src, tgt, w in _sector_asset:
            if src in self.nodes and tgt in self.nodes:
                self.add_edge(GraphEdge(source=src, target=tgt, weight=w, relationship="sector_tracks"))

        # ── Country trade dependencies ───────────────────────────────────
        _trade_deps = [
            ("USA", "CHN", 0.80), ("USA", "CAN", 0.70), ("USA", "MEX", 0.65),
            ("USA", "JPN", 0.55), ("USA", "DEU", 0.55), ("USA", "GBR", 0.60),
            ("USA", "KOR", 0.50), ("USA", "TWN", 0.60),
            ("CHN", "JPN", 0.65), ("CHN", "KOR", 0.60), ("CHN", "AUS", 0.65),
            ("CHN", "TWN", 0.75), ("CHN", "BRA", 0.55),
            ("DEU", "FRA", 0.65), ("DEU", "ITA", 0.55), ("DEU", "GBR", 0.60),
            ("RUS", "DEU", 0.55), ("RUS", "CHN", 0.60), ("RUS", "TUR", 0.45),
            ("SAU", "CHN", 0.55), ("SAU", "IND", 0.50), ("SAU", "JPN", 0.45),
            ("SAU", "USA", 0.50),
            ("IRN", "CHN", 0.50), ("IRN", "IND", 0.40), ("IRN", "TUR", 0.40),
            ("ISR", "USA", 0.65),
            ("UKR", "POL", 0.45), ("UKR", "DEU", 0.40),
            ("JPN", "KOR", 0.50), ("JPN", "TWN", 0.45),
            ("IND", "USA", 0.50), ("IND", "AUS", 0.40),
        ]
        for src, tgt, w in _trade_deps:
            if src in self.nodes and tgt in self.nodes:
                self.add_edge(GraphEdge(source=src, target=tgt, weight=w, relationship="trades_with"))

        # ── Safe-haven flows (inverse relationships) ─────────────────────
        # When tension rises, these assets gain
        safe_havens = [
            ("gold", "GLD",    0.80), ("gold", "TLT",    0.40),
            ("gold", "XAUUSD", 0.90),                            # canonical gold
            ("silver", "XAGUSD", 0.85),                          # canonical silver
            ("gold", "BTCUSD", 0.35),                            # BTC partial safe-haven
        ]
        for src, tgt, w in safe_havens:
            if src in self.nodes and tgt in self.nodes:
                self.add_edge(GraphEdge(
                    source=src, target=tgt, weight=w,
                    relationship="safe_haven_flow",
                ))

        # ── Country → Defense sector (USA/ISR/RUS primary) ───────────────
        _defense_country_asset = [
            ("USA", "LMT",    0.85), ("USA", "RTX",    0.82),
            ("USA", "NOC",    0.80), ("USA", "GD",     0.78),
            ("USA", "BA",     0.72), ("ISR", "LMT",   0.50),
            ("ISR", "RTX",    0.55), ("RUS", "NOC",   0.30),
        ]
        for src, tgt, w in _defense_country_asset:
            if src in self.nodes and tgt in self.nodes:
                self.add_edge(GraphEdge(source=src, target=tgt, weight=w, relationship="defense_demand"))

    def to_serializable(self) -> dict[str, Any]:
        """Serialize graph structure for API responses / visualization."""
        self.build_default_graph()
        nodes_out = []
        for n in self.nodes.values():
            nodes_out.append({
                "id": n.id,
                "type": n.node_type.value,
                "label": n.label,
            })

        edges_out = []
        seen = set()
        for source_id, edges in self.adjacency.items():
            for e in edges:
                key = f"{e.source}->{e.target}:{e.relationship}"
                if key not in seen:
                    seen.add(key)
                    edges_out.append({
                        "source": e.source,
                        "target": e.target,
                        "weight": e.weight,
                        "relationship": e.relationship,
                    })

        return {"nodes": nodes_out, "edges": edges_out}


# ── Event type multipliers (amplify certain edge types) ──────────────────────

_EVENT_TYPE_MULTIPLIERS: dict[str, dict[str, float]] = {
    "military_escalation": {
        "produces": 1.5, "trades_with": 1.3, "industry_exposure": 1.2,
        "safe_haven_flow": 2.0,
    },
    "sanctions": {
        "trades_with": 2.0, "produces": 1.5, "industry_exposure": 1.3,
    },
    "trade_restrictions": {
        "trades_with": 2.5, "produces": 1.2, "tracks": 1.3,
    },
    "energy_supply_disruption": {
        "produces": 2.5, "tracks": 1.8, "trades_with": 1.2,
        "sector_tracks": 1.5,
    },
    "cyber_attack": {
        "industry_exposure": 2.0, "sector_tracks": 1.5, "trades_with": 0.8,
    },
    "political_instability": {
        "trades_with": 1.3, "industry_exposure": 1.2, "produces": 1.1,
    },
    "economic_policy_change": {
        "trades_with": 1.5, "industry_exposure": 1.5, "sector_tracks": 1.3,
    },
    "diplomatic_breakdown": {
        "trades_with": 1.8, "produces": 1.2, "safe_haven_flow": 1.5,
    },
    "territorial_dispute": {
        "trades_with": 1.5, "produces": 1.8, "safe_haven_flow": 1.8,
    },
    "nuclear_threat": {
        "safe_haven_flow": 3.0, "trades_with": 1.5, "produces": 1.5,
    },
}

# ── Module-level singleton ───────────────────────────────────────────────────

_impact_graph: ImpactGraph | None = None


def get_impact_graph() -> ImpactGraph:
    global _impact_graph  # noqa: PLW0603
    if _impact_graph is None:
        _impact_graph = ImpactGraph()
        _impact_graph.build_default_graph()
    return _impact_graph
