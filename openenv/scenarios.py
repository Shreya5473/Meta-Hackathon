"""GeoTrade OpenEnv — scenario datasets.

All scenarios are self-contained dicts with:
  - geopolitical context
  - market snapshot
  - ground-truth answers (used by graders)
  - step-by-step evolution (for the hard multi-step task)

No external APIs required — all data is synthetic but calibrated to real
historical geo-financial correlations observed in the GeoTrade system.
"""
from __future__ import annotations

from typing import Any

# ── Asset metadata ─────────────────────────────────────────────────────────────

ASSET_META: dict[str, dict[str, Any]] = {
    "XAUUSD": {"name": "Gold Spot / USD",      "asset_class": "commodity", "gti_sensitivity": 0.85},
    "NATGAS":  {"name": "Natural Gas",          "asset_class": "commodity", "gti_sensitivity": 0.80},
    "WTI":     {"name": "WTI Crude Oil",        "asset_class": "commodity", "gti_sensitivity": 0.88},
    "BRENT":   {"name": "Brent Crude Oil",      "asset_class": "commodity", "gti_sensitivity": 0.87},
    "EURUSD":  {"name": "EUR / USD",            "asset_class": "forex",     "gti_sensitivity": 0.65},
    "USDJPY":  {"name": "USD / JPY",            "asset_class": "forex",     "gti_sensitivity": 0.70},
    "USDCHF":  {"name": "USD / CHF",            "asset_class": "forex",     "gti_sensitivity": 0.72},
    "GBPUSD":  {"name": "GBP / USD",            "asset_class": "forex",     "gti_sensitivity": 0.60},
    "SPX":     {"name": "S&P 500",              "asset_class": "equity",    "gti_sensitivity": 0.75},
    "NDX":     {"name": "NASDAQ 100",           "asset_class": "equity",    "gti_sensitivity": 0.70},
    "DAX":     {"name": "DAX 40",               "asset_class": "equity",    "gti_sensitivity": 0.72},
    "COPPER":  {"name": "Copper Spot",          "asset_class": "commodity", "gti_sensitivity": 0.68},
    "TLT":     {"name": "US 20yr Treasury ETF", "asset_class": "bond",      "gti_sensitivity": 0.55},
    "WHEAT":   {"name": "Wheat",                "asset_class": "commodity", "gti_sensitivity": 0.75},
}


def _snap(
    symbols: list[str],
    prices: dict[str, float],
    vol_regimes: dict[str, str] | None = None,
    changes: dict[str, float] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build a market_snapshot dict from compact inputs."""
    vol_regimes = vol_regimes or {}
    changes = changes or {}
    snap: dict[str, dict[str, Any]] = {}
    for sym in symbols:
        meta = ASSET_META[sym]
        snap[sym] = {
            "symbol": sym,
            "name": meta["name"],
            "asset_class": meta["asset_class"],
            "price": prices.get(sym, 1.0),
            "daily_change_pct": changes.get(sym, 0.0),
            "volatility_regime": vol_regimes.get(sym, "NORMAL"),
            "gti_sensitivity": meta["gti_sensitivity"],
        }
    return snap


# ══════════════════════════════════════════════════════════════════════════════
# TASK 1 — EASY: Geopolitical Signal Identification
# Single-step. Agent must identify top-3 impacted assets and direction.
# ══════════════════════════════════════════════════════════════════════════════

EASY_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "easy_001",
        "geopolitical_context": {
            "gti_score": 72.0,
            "gti_delta": 18.0,
            "region": "europe",
            "severity": "high",
            "categories": ["energy_supply_disruption", "sanctions"],
            "headline": "Russia halts all natural gas pipeline exports to Europe",
            "description": (
                "Russia has announced an immediate suspension of natural gas flows through "
                "major pipelines to Europe, citing 'technical issues' following expanded "
                "Western sanctions. European gas storage levels are at 62% — below the "
                "seasonal average of 78%. Winter heating demand is near peak."
            ),
            "news_headlines": [
                "EU emergency energy ministers meeting called for tomorrow",
                "Germany activates gas emergency plan Level 2",
                "LNG spot prices surge 34% in Asian markets",
            ],
            "affected_sectors": ["energy", "utilities", "industrials"],
        },
        "market_snapshot": _snap(
            ["NATGAS", "XAUUSD", "EURUSD", "WTI", "SPX"],
            prices={"NATGAS": 2.85, "XAUUSD": 2340.0, "EURUSD": 1.085, "WTI": 78.5, "SPX": 5200.0},
        ),
        "ground_truth": {
            "top_impacted": ["NATGAS", "EURUSD", "XAUUSD"],
            "directions": {"NATGAS": "BUY", "EURUSD": "SELL", "XAUUSD": "BUY", "WTI": "BUY", "SPX": "SELL"},
            "explanation": (
                "Gas supply disruption → NATGAS price spike. EUR weakens on energy cost shock "
                "hitting European economies. Gold rises as safe haven. Oil rises on energy scarcity narrative."
            ),
        },
    },
    {
        "id": "easy_002",
        "geopolitical_context": {
            "gti_score": 68.0,
            "gti_delta": 22.0,
            "region": "middle_east",
            "severity": "high",
            "categories": ["military_escalation", "energy_supply_disruption"],
            "headline": "Houthi missile strikes close Strait of Hormuz to tanker traffic",
            "description": (
                "Houthi forces have launched a coordinated missile and drone campaign forcing "
                "the temporary closure of the Strait of Hormuz — through which ~21% of global "
                "oil supply transits daily. Saudi Aramco has declared force majeure on two LNG "
                "shipments. US 5th Fleet is mobilising."
            ),
            "news_headlines": [
                "Oil tanker 'Pacific Voyager' struck in Red Sea",
                "Saudi Arabia suspends Ras Tanura port operations",
                "OPEC emergency virtual summit called",
            ],
            "affected_sectors": ["energy", "defense", "shipping"],
        },
        "market_snapshot": _snap(
            ["WTI", "BRENT", "XAUUSD", "USDJPY", "SPX"],
            prices={"WTI": 79.2, "BRENT": 83.1, "XAUUSD": 2310.0, "USDJPY": 149.5, "SPX": 5180.0},
        ),
        "ground_truth": {
            "top_impacted": ["WTI", "BRENT", "XAUUSD"],
            "directions": {"WTI": "BUY", "BRENT": "BUY", "XAUUSD": "BUY", "USDJPY": "BUY", "SPX": "SELL"},
            "explanation": (
                "Strait of Hormuz closure creates immediate oil supply shock → WTI/Brent surge. "
                "Gold rises as crisis safe haven. JPY and CHF strengthen (safe-haven flows). "
                "Equities sell off on stagflation fears."
            ),
        },
    },
    {
        "id": "easy_003",
        "geopolitical_context": {
            "gti_score": 55.0,
            "gti_delta": 14.0,
            "region": "asia_pacific",
            "severity": "medium",
            "categories": ["trade_restrictions", "supply_chain_disruption"],
            "headline": "US announces 60% tariffs on all Chinese semiconductor imports",
            "description": (
                "The US Commerce Department has published a final rule imposing 60% tariffs on "
                "semiconductor and electronic component imports from China, effective in 30 days. "
                "China's Ministry of Commerce warns of 'equivalent countermeasures' targeting "
                "US agricultural exports and rare-earth minerals."
            ),
            "news_headlines": [
                "TSMC shares fall 8% in pre-market on supply chain fears",
                "Apple warns of Q3 margin compression",
                "China rare-earth export quotas to be reviewed",
            ],
            "affected_sectors": ["technology", "semiconductors", "agriculture"],
        },
        "market_snapshot": _snap(
            ["NDX", "COPPER", "XAUUSD", "USDJPY", "WHEAT"],
            prices={"NDX": 18500.0, "COPPER": 4.35, "XAUUSD": 2295.0, "USDJPY": 151.2, "WHEAT": 5.65},
        ),
        "ground_truth": {
            "top_impacted": ["NDX", "COPPER", "WHEAT"],
            "directions": {"NDX": "SELL", "COPPER": "SELL", "WHEAT": "BUY", "XAUUSD": "BUY", "USDJPY": "BUY"},
            "explanation": (
                "Tech tariffs hit NASDAQ-listed chip/hardware companies. Copper falls on China "
                "economic slowdown fears (China consumes ~55% of global copper). Wheat rises "
                "on China retaliatory agricultural tariff risk to US exports."
            ),
        },
    },
    {
        "id": "easy_004",
        "geopolitical_context": {
            "gti_score": 38.0,
            "gti_delta": -12.0,
            "region": "europe",
            "severity": "low",
            "categories": ["diplomatic_breakdown", "sanctions"],
            "headline": "Russia-Ukraine ceasefire agreement signed in Istanbul",
            "description": (
                "A preliminary ceasefire agreement between Russia and Ukraine has been signed "
                "after marathon negotiations in Istanbul mediated by Turkey and Saudi Arabia. "
                "The agreement halts active combat immediately. Sanctions relief talks will "
                "begin within 60 days. European energy markets react to potential pipeline resumption."
            ),
            "news_headlines": [
                "Kyiv confirms ceasefire effective at 06:00 UTC",
                "EU lifts 'emergency energy plan' — gas storage now 71%",
                "Russian gas futures fall 22% in early trading",
            ],
            "affected_sectors": ["energy", "defense", "reconstruction"],
        },
        "market_snapshot": _snap(
            ["NATGAS", "EURUSD", "DAX", "XAUUSD", "WTI"],
            prices={"NATGAS": 3.10, "EURUSD": 1.072, "DAX": 17800.0, "XAUUSD": 2360.0, "WTI": 81.0},
        ),
        "ground_truth": {
            "top_impacted": ["NATGAS", "DAX", "EURUSD"],
            "directions": {"NATGAS": "SELL", "DAX": "BUY", "EURUSD": "BUY", "XAUUSD": "SELL", "WTI": "SELL"},
            "explanation": (
                "Ceasefire reduces European energy risk premium → NATGAS falls, EUR strengthens. "
                "European equities (DAX) rally on reconstruction optimism and energy stability. "
                "Gold loses safe-haven bid. Oil softens on potential Russian supply return."
            ),
        },
    },
    {
        "id": "easy_005",
        "geopolitical_context": {
            "gti_score": 62.0,
            "gti_delta": 25.0,
            "region": "asia_pacific",
            "severity": "high",
            "categories": ["military_escalation", "territorial_dispute"],
            "headline": "China declares air-defense identification zone over Taiwan Strait",
            "description": (
                "China's PLA Air Force has declared a new Air Defense Identification Zone (ADIZ) "
                "covering the entire Taiwan Strait, demanding that all foreign military and "
                "commercial aircraft file flight plans with Beijing. The US has called the move "
                "'illegal and provocative' and ordered two carrier strike groups to the region."
            ),
            "news_headlines": [
                "Taiwan TAIEX falls 6.2% — circuit breaker triggered",
                "TSMC announces supply chain contingency plan",
                "South Korea and Japan raise military readiness levels",
            ],
            "affected_sectors": ["technology", "semiconductors", "defense"],
        },
        "market_snapshot": _snap(
            ["NDX", "XAUUSD", "USDJPY", "COPPER", "TLT"],
            prices={"NDX": 18200.0, "XAUUSD": 2380.0, "USDJPY": 150.8, "COPPER": 4.28, "TLT": 92.5},
        ),
        "ground_truth": {
            "top_impacted": ["NDX", "XAUUSD", "USDJPY"],
            "directions": {"NDX": "SELL", "XAUUSD": "BUY", "USDJPY": "BUY", "COPPER": "SELL", "TLT": "BUY"},
            "explanation": (
                "Taiwan Strait crisis threatens semiconductor supply chain (TSMC = ~60% of leading-edge "
                "chip production) → NDX/tech sell-off. Gold and JPY surge as crisis safe havens. "
                "Treasury bonds rally on flight-to-quality. Copper falls on China economic slowdown fears."
            ),
        },
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# TASK 2 — MEDIUM: Portfolio Geopolitical Hedging
# Single-step. Agent must rebalance a 6-asset portfolio to manage geo risk.
# ══════════════════════════════════════════════════════════════════════════════

MEDIUM_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "medium_001",
        "geopolitical_context": {
            "gti_score": 74.0,
            "gti_delta": 28.0,
            "region": "middle_east",
            "severity": "high",
            "categories": ["military_escalation", "energy_supply_disruption"],
            "headline": "Iran-Israel direct military exchange escalates; oil facilities targeted",
            "description": (
                "Iran has launched ballistic missiles at Israeli energy infrastructure, with "
                "retaliatory Israeli airstrikes on Iranian oil refineries confirmed. The Strait "
                "of Hormuz is at elevated closure risk. Regional allies are mobilising. "
                "Crisis is classified as HIGH by GeoTrade GTI engine (score 74, up 28 in 24h)."
            ),
            "news_headlines": [
                "Iran Revolutionary Guards: 'We will close the Strait if attacked again'",
                "Brent crude up 12% in Asian session",
                "US deploys additional carrier group to Persian Gulf",
            ],
            "affected_sectors": ["energy", "defense", "financials"],
        },
        "market_snapshot": _snap(
            ["SPX", "XAUUSD", "WTI", "EURUSD", "USDJPY", "NATGAS"],
            prices={"SPX": 5150.0, "XAUUSD": 2350.0, "WTI": 82.0, "EURUSD": 1.082, "USDJPY": 150.0, "NATGAS": 3.0},
            vol_regimes={"SPX": "HIGH", "WTI": "EXTREME", "NATGAS": "HIGH"},
        ),
        "initial_portfolio": {"SPX": 0.40, "XAUUSD": 0.10, "WTI": 0.10, "EURUSD": 0.15, "USDJPY": 0.10, "NATGAS": 0.05},
        "initial_cash": 0.10,
        "ground_truth": {
            "optimal_weights": {"SPX": 0.15, "XAUUSD": 0.25, "WTI": 0.25, "EURUSD": 0.05, "USDJPY": 0.15, "NATGAS": 0.10},
            "optimal_cash": 0.05,
            "key_moves": {
                "SPX": "REDUCE",     # Risk-off: cut equity exposure significantly
                "XAUUSD": "INCREASE",# Safe haven
                "WTI": "INCREASE",   # Oil supply shock
                "EURUSD": "REDUCE",  # EUR vulnerable to energy cost crisis
                "USDJPY": "INCREASE",# Safe haven flow into JPY
                "NATGAS": "INCREASE",# Energy supply disruption
            },
            "reasoning_keywords": ["safe haven", "oil", "supply disruption", "risk off", "hedg"],
        },
    },
    {
        "id": "medium_002",
        "geopolitical_context": {
            "gti_score": 65.0,
            "gti_delta": 20.0,
            "region": "asia_pacific",
            "severity": "high",
            "categories": ["trade_restrictions", "supply_chain_disruption", "territorial_dispute"],
            "headline": "US-China trade war reignites: mutual 80% tariffs on tech and agriculture",
            "description": (
                "Following breakdown of trade talks in Geneva, both the US and China have announced "
                "sweeping 80% tariffs on each other's technology products and agricultural exports, "
                "effective 14 days. China also restricts exports of 5 critical rare-earth elements "
                "essential for semiconductor manufacturing."
            ),
            "news_headlines": [
                "WTO emergency session convened; dispute resolution timeline 12–18 months",
                "Apple, NVIDIA shares down 9–11% in pre-market",
                "China soybean buyers cancel US contracts worth $4.2B",
            ],
            "affected_sectors": ["technology", "agriculture", "industrials"],
        },
        "market_snapshot": _snap(
            ["NDX", "XAUUSD", "COPPER", "WHEAT", "USDJPY", "TLT"],
            prices={"NDX": 18100.0, "XAUUSD": 2320.0, "COPPER": 4.25, "WHEAT": 5.80, "USDJPY": 152.0, "TLT": 91.5},
            vol_regimes={"NDX": "HIGH", "COPPER": "HIGH"},
        ),
        "initial_portfolio": {"NDX": 0.35, "XAUUSD": 0.10, "COPPER": 0.15, "WHEAT": 0.10, "USDJPY": 0.10, "TLT": 0.15},
        "initial_cash": 0.05,
        "ground_truth": {
            "optimal_weights": {"NDX": 0.12, "XAUUSD": 0.22, "COPPER": 0.08, "WHEAT": 0.20, "USDJPY": 0.18, "TLT": 0.18},
            "optimal_cash": 0.02,
            "key_moves": {
                "NDX": "REDUCE",     # Tech tariffs crush NASDAQ
                "XAUUSD": "INCREASE",# Safe haven
                "COPPER": "REDUCE",  # China slowdown = demand destruction
                "WHEAT": "INCREASE", # Agricultural export disruption inflates food prices
                "USDJPY": "INCREASE",# JPY safe haven
                "TLT": "INCREASE",   # Flight to bonds on equity risk-off
            },
            "reasoning_keywords": ["tariff", "tech", "safe haven", "agriculture", "rare earth", "bond"],
        },
    },
    {
        "id": "medium_003",
        "geopolitical_context": {
            "gti_score": 58.0,
            "gti_delta": 16.0,
            "region": "europe",
            "severity": "medium",
            "categories": ["sanctions", "political_instability", "economic_policy_change"],
            "headline": "Russia seizes assets of Western companies; EU responds with sweeping sanctions",
            "description": (
                "Russia has formally nationalised assets of 43 EU and US companies operating in Russia, "
                "valued at an estimated $28B. The EU has responded with its 15th sanctions package, "
                "targeting Russian financial institutions and commodities. Market concerns focus on "
                "European bank exposure and natural gas supply reliability."
            ),
            "news_headlines": [
                "Societe Generale, UniCredit confirm Russia asset seizures",
                "EU sanctions include ban on Russian LNG imports from 2026",
                "Ruble hits 6-month low vs USD",
            ],
            "affected_sectors": ["financials", "energy", "industrials"],
        },
        "market_snapshot": _snap(
            ["DAX", "XAUUSD", "NATGAS", "EURUSD", "USDCHF", "TLT"],
            prices={"DAX": 17900.0, "XAUUSD": 2330.0, "NATGAS": 2.95, "EURUSD": 1.078, "USDCHF": 0.905, "TLT": 92.0},
            vol_regimes={"DAX": "HIGH", "NATGAS": "HIGH"},
        ),
        "initial_portfolio": {"DAX": 0.30, "XAUUSD": 0.10, "NATGAS": 0.10, "EURUSD": 0.20, "USDCHF": 0.10, "TLT": 0.15},
        "initial_cash": 0.05,
        "ground_truth": {
            "optimal_weights": {"DAX": 0.12, "XAUUSD": 0.20, "NATGAS": 0.18, "EURUSD": 0.10, "USDCHF": 0.20, "TLT": 0.18},
            "optimal_cash": 0.02,
            "key_moves": {
                "DAX": "REDUCE",      # European bank exposure + growth headwinds
                "XAUUSD": "INCREASE", # Safe haven
                "NATGAS": "INCREASE", # LNG ban tightens European supply long-term
                "EURUSD": "REDUCE",   # EUR under pressure from sanctions economic cost
                "USDCHF": "INCREASE", # CHF safe haven
                "TLT": "INCREASE",    # Bond flight-to-quality
            },
            "reasoning_keywords": ["sanction", "european bank", "gas", "safe haven", "CHF", "risk"],
        },
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# TASK 3 — HARD: Crisis Cascade Portfolio Management
# 5-step multi-turn episode. Agent manages a portfolio through an evolving crisis.
# ══════════════════════════════════════════════════════════════════════════════

HARD_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "hard_001",
        "name": "Middle East Escalation & Ceasefire",
        "assets": ["WTI", "XAUUSD", "SPX", "USDJPY", "NATGAS", "TLT"],
        "initial_portfolio": {"WTI": 0.15, "XAUUSD": 0.10, "SPX": 0.35, "USDJPY": 0.10, "NATGAS": 0.10, "TLT": 0.15},
        "initial_cash": 0.05,
        "steps": [
            {
                "step": 0,
                "geopolitical_context": {
                    "gti_score": 32.0, "gti_delta": 5.0,
                    "region": "middle_east", "severity": "low",
                    "categories": ["political_instability"],
                    "headline": "IAEA flags Iran nuclear enrichment acceleration",
                    "description": "IAEA reports Iran has increased uranium enrichment to 84%, just below weapons-grade. US and EU issue diplomatic warnings. Situation described as 'concerning but not immediately dangerous'.",
                    "news_headlines": ["Iran enrichment at 84% — IAEA says 'serious concern'", "US State Dept: Iran 'testing boundaries'"],
                    "affected_sectors": ["energy", "defense"],
                },
                "price_moves": {"WTI": 0.012, "XAUUSD": 0.008, "SPX": -0.005, "USDJPY": 0.003, "NATGAS": 0.005, "TLT": 0.004},
                "optimal_action": {
                    "WTI": ("BUY", 0.18), "XAUUSD": ("BUY", 0.13), "SPX": ("HOLD", 0.33),
                    "USDJPY": ("BUY", 0.12), "NATGAS": ("HOLD", 0.10), "TLT": ("BUY", 0.12),
                },
                "reasoning_keywords": ["nuclear", "Iran", "oil", "safe haven", "moderate"],
            },
            {
                "step": 1,
                "geopolitical_context": {
                    "gti_score": 52.0, "gti_delta": 20.0,
                    "region": "middle_east", "severity": "medium",
                    "categories": ["military_escalation", "nuclear_threat"],
                    "headline": "Israel strikes Iranian nuclear facility; Iran vows retaliation",
                    "description": "Israeli airstrikes have destroyed Iran's Fordow nuclear facility. Iran has declared a 'day of mourning and retaliation', mobilising Revolutionary Guard units. Strait of Hormuz passage is on elevated alert.",
                    "news_headlines": ["Fordow facility destroyed — IAF confirms", "Oil futures up 8% overnight", "Iran IRGC activates naval units in Gulf"],
                    "affected_sectors": ["energy", "defense", "financials"],
                },
                "price_moves": {"WTI": 0.08, "XAUUSD": 0.025, "SPX": -0.028, "USDJPY": 0.015, "NATGAS": 0.035, "TLT": 0.018},
                "optimal_action": {
                    "WTI": ("BUY", 0.25), "XAUUSD": ("BUY", 0.20), "SPX": ("SELL", 0.18),
                    "USDJPY": ("BUY", 0.15), "NATGAS": ("BUY", 0.12), "TLT": ("BUY", 0.08),
                },
                "reasoning_keywords": ["escalat", "oil supply", "risk off", "safe haven", "Hormuz"],
            },
            {
                "step": 2,
                "geopolitical_context": {
                    "gti_score": 81.0, "gti_delta": 29.0,
                    "region": "middle_east", "severity": "critical",
                    "categories": ["military_escalation", "energy_supply_disruption"],
                    "headline": "Iran mines Strait of Hormuz; 21% of global oil supply blocked",
                    "description": "Iran has deployed naval mines across the Strait of Hormuz, halting all tanker traffic. Saudi Aramco declares force majeure. OPEC+ holds emergency call. US 5th Fleet has begun mine-clearing operations estimated to take 5–10 days.",
                    "news_headlines": ["Strait CLOSED — insurance underwriters halt coverage", "WTI +19% in 24h — highest since 2008", "G7 to release emergency strategic reserves"],
                    "affected_sectors": ["energy", "shipping", "industrials", "financials"],
                },
                "price_moves": {"WTI": 0.19, "XAUUSD": 0.035, "SPX": -0.052, "USDJPY": 0.020, "NATGAS": 0.065, "TLT": 0.025},
                "optimal_action": {
                    "WTI": ("BUY", 0.30), "XAUUSD": ("BUY", 0.22), "SPX": ("SELL", 0.10),
                    "USDJPY": ("BUY", 0.15), "NATGAS": ("BUY", 0.15), "TLT": ("HOLD", 0.06),
                },
                "reasoning_keywords": ["Hormuz", "mine", "oil spike", "emergency", "critical"],
            },
            {
                "step": 3,
                "geopolitical_context": {
                    "gti_score": 73.0, "gti_delta": -8.0,
                    "region": "middle_east", "severity": "high",
                    "categories": ["military_escalation", "diplomatic_breakdown"],
                    "headline": "US mine-clearing operation succeeds; Iran agrees to talks under pressure",
                    "description": "US Navy has successfully cleared the Strait of Hormuz of mines. Iran has agreed to 'preliminary ceasefire discussions' brokered by Oman, under intense international pressure. Oil prices remain elevated but begin to ease slightly as tanker traffic resumes.",
                    "news_headlines": ["First tanker passes through Strait in 72h", "Brent down 6% from peak on talks news", "Iran FM arrives in Muscat for ceasefire talks"],
                    "affected_sectors": ["energy", "defense", "diplomacy"],
                },
                "price_moves": {"WTI": -0.06, "XAUUSD": -0.010, "SPX": 0.022, "USDJPY": -0.008, "NATGAS": -0.025, "TLT": -0.012},
                "optimal_action": {
                    "WTI": ("SELL", 0.22), "XAUUSD": ("HOLD", 0.20), "SPX": ("BUY", 0.18),
                    "USDJPY": ("HOLD", 0.13), "NATGAS": ("SELL", 0.10), "TLT": ("SELL", 0.10),
                },
                "reasoning_keywords": ["de-escalat", "ceasefire", "partial sell", "oil easing", "talks"],
            },
            {
                "step": 4,
                "geopolitical_context": {
                    "gti_score": 42.0, "gti_delta": -31.0,
                    "region": "middle_east", "severity": "medium",
                    "categories": ["diplomatic_breakdown"],
                    "headline": "Comprehensive ceasefire signed; sanctions relief framework announced",
                    "description": "Iran and Israel have signed a comprehensive ceasefire agreement in Muscat, with a 90-day roadmap for sanctions relief and nuclear inspections. Oil markets have reacted with a sharp retreat from crisis highs. Safe-haven assets are unwinding as risk appetite returns.",
                    "news_headlines": ["Muscat Accord signed — 90-day peace framework", "WTI falls 11% — back below $85", "S&P 500 futures up 2.5% on peace news"],
                    "affected_sectors": ["energy", "equities", "reconstruction"],
                },
                "price_moves": {"WTI": -0.11, "XAUUSD": -0.025, "SPX": 0.025, "USDJPY": -0.015, "NATGAS": -0.04, "TLT": -0.018},
                "optimal_action": {
                    "WTI": ("SELL", 0.12), "XAUUSD": ("SELL", 0.12), "SPX": ("BUY", 0.30),
                    "USDJPY": ("SELL", 0.10), "NATGAS": ("SELL", 0.08), "TLT": ("SELL", 0.08),
                },
                "reasoning_keywords": ["ceasefire", "risk on", "equities", "unwind", "peace"],
            },
        ],
        "scoring": {
            "weights": {"prediction_accuracy": 0.35, "pnl_performance": 0.40, "risk_management": 0.25},
            "benchmark_pnl": 0.142,
            "max_allowed_drawdown": 0.08,
        },
    },
    {
        "id": "hard_002",
        "name": "US-China Taiwan Strait Crisis",
        "assets": ["NDX", "XAUUSD", "COPPER", "USDJPY", "TLT", "WTI"],
        "initial_portfolio": {"NDX": 0.30, "XAUUSD": 0.10, "COPPER": 0.15, "USDJPY": 0.10, "TLT": 0.20, "WTI": 0.10},
        "initial_cash": 0.05,
        "steps": [
            {
                "step": 0,
                "geopolitical_context": {
                    "gti_score": 38.0, "gti_delta": 8.0,
                    "region": "asia_pacific", "severity": "low",
                    "categories": ["territorial_dispute", "political_instability"],
                    "headline": "China conducts unannounced military drills near Taiwan",
                    "description": "PLA has conducted surprise military exercises in the Taiwan Strait involving 45 aircraft and 12 naval vessels. Taiwan's MND has raised its threat level from 'yellow' to 'orange'. Markets are monitoring but reaction is muted.",
                    "news_headlines": ["PLA exercises: largest since 2023", "Taiwan raises threat level to orange", "TSMC declines to comment on contingency plans"],
                    "affected_sectors": ["technology", "semiconductors"],
                },
                "price_moves": {"NDX": -0.015, "XAUUSD": 0.010, "COPPER": -0.008, "USDJPY": 0.005, "TLT": 0.008, "WTI": 0.003},
                "optimal_action": {
                    "NDX": ("HOLD", 0.27), "XAUUSD": ("BUY", 0.14), "COPPER": ("SELL", 0.12),
                    "USDJPY": ("BUY", 0.12), "TLT": ("BUY", 0.22), "WTI": ("HOLD", 0.10),
                },
                "reasoning_keywords": ["Taiwan", "tech", "semiconductor", "mild", "monitoring"],
            },
            {
                "step": 1,
                "geopolitical_context": {
                    "gti_score": 62.0, "gti_delta": 24.0,
                    "region": "asia_pacific", "severity": "high",
                    "categories": ["military_escalation", "trade_restrictions"],
                    "headline": "China declares naval blockade of Taiwan; US deploys carrier groups",
                    "description": "China has declared a naval blockade of Taiwan, prohibiting all foreign vessels. The US has deployed 3 carrier strike groups to the Western Pacific. Semiconductor supply chains are in immediate jeopardy — Taiwan produces 90% of sub-3nm chips.",
                    "news_headlines": ["TSMC halts all non-Taiwan shipments", "Biden: US will defend Taiwan", "Asian markets in freefall — circuit breakers triggered in Tokyo"],
                    "affected_sectors": ["technology", "defense", "shipping"],
                },
                "price_moves": {"NDX": -0.072, "XAUUSD": 0.030, "COPPER": -0.028, "USDJPY": 0.018, "TLT": 0.022, "WTI": 0.015},
                "optimal_action": {
                    "NDX": ("SELL", 0.14), "XAUUSD": ("BUY", 0.24), "COPPER": ("SELL", 0.08),
                    "USDJPY": ("BUY", 0.18), "TLT": ("BUY", 0.26), "WTI": ("BUY", 0.08),
                },
                "reasoning_keywords": ["blockade", "chip", "TSMC", "risk off", "safe haven"],
            },
            {
                "step": 2,
                "geopolitical_context": {
                    "gti_score": 88.0, "gti_delta": 26.0,
                    "region": "asia_pacific", "severity": "critical",
                    "categories": ["military_escalation", "supply_chain_disruption", "cyber_attack"],
                    "headline": "Chinese cyber attacks disable US carrier systems; Taiwan invasion imminent",
                    "description": "Sophisticated cyber attacks attributed to China's PLA Unit 61398 have partially disabled navigation systems on two US carriers. Taiwan Strait is now effectively a war zone. Global semiconductor stocks in freefall. Emergency G7 summit convened.",
                    "news_headlines": ["TSMC self-destructs fab equipment per contingency plan", "NASDAQ halted — S&P circuit breaker at -7%", "Emergency G7 summit in Brussels"],
                    "affected_sectors": ["technology", "defense", "financials", "manufacturing"],
                },
                "price_moves": {"NDX": -0.095, "XAUUSD": 0.048, "COPPER": -0.038, "USDJPY": 0.025, "TLT": 0.035, "WTI": 0.022},
                "optimal_action": {
                    "NDX": ("SELL", 0.06), "XAUUSD": ("BUY", 0.30), "COPPER": ("SELL", 0.05),
                    "USDJPY": ("BUY", 0.20), "TLT": ("BUY", 0.32), "WTI": ("BUY", 0.05),
                },
                "reasoning_keywords": ["critical", "cyber", "TSMC", "maximum risk off", "defense", "bond"],
            },
            {
                "step": 3,
                "geopolitical_context": {
                    "gti_score": 75.0, "gti_delta": -13.0,
                    "region": "asia_pacific", "severity": "high",
                    "categories": ["diplomatic_breakdown", "sanctions"],
                    "headline": "China withdraws naval forces; G7 sanctions package announced",
                    "description": "Following intense diplomatic pressure and the G7 emergency summit, China has 'voluntarily withdrawn' naval forces from immediate Taiwan waters, stating drills are complete. However, comprehensive G7 economic sanctions on China — targeting semiconductors, luxury goods, and financial services — are announced effective in 30 days.",
                    "news_headlines": ["PLA withdraws — markets begin to stabilise", "G7 sanctions: $2.1T in Chinese trade targeted", "NDX recovers 4% off lows"],
                    "affected_sectors": ["technology", "financials", "trade"],
                },
                "price_moves": {"NDX": 0.04, "XAUUSD": -0.015, "COPPER": -0.012, "USDJPY": -0.010, "TLT": -0.015, "WTI": -0.008},
                "optimal_action": {
                    "NDX": ("BUY", 0.15), "XAUUSD": ("HOLD", 0.26), "COPPER": ("SELL", 0.05),
                    "USDJPY": ("HOLD", 0.18), "TLT": ("SELL", 0.25), "WTI": ("HOLD", 0.07),
                },
                "reasoning_keywords": ["partial de-escalat", "sanctions", "partial recovery", "tech rebound"],
            },
            {
                "step": 4,
                "geopolitical_context": {
                    "gti_score": 48.0, "gti_delta": -27.0,
                    "region": "asia_pacific", "severity": "medium",
                    "categories": ["trade_restrictions", "economic_policy_change"],
                    "headline": "US-China begin trade framework negotiations; 60-day sanctions pause",
                    "description": "Following bilateral back-channel talks, both sides have agreed to a 60-day sanctions pause to allow trade framework negotiations. Markets view this as a de-escalation milestone. Semiconductor supply chain concerns remain but confidence is improving.",
                    "news_headlines": ["60-day sanctions pause: Wall Street cheers", "TSMC announces plans to resume some shipping routes", "G7 willing to modify sanctions if talks succeed"],
                    "affected_sectors": ["technology", "trade", "equities"],
                },
                "price_moves": {"NDX": 0.038, "XAUUSD": -0.022, "COPPER": 0.015, "USDJPY": -0.012, "TLT": -0.020, "WTI": -0.005},
                "optimal_action": {
                    "NDX": ("BUY", 0.28), "XAUUSD": ("SELL", 0.12), "COPPER": ("BUY", 0.14),
                    "USDJPY": ("SELL", 0.10), "TLT": ("SELL", 0.18), "WTI": ("HOLD", 0.10),
                },
                "reasoning_keywords": ["negotiations", "risk on", "tech recovery", "copper recovery", "unwind"],
            },
        ],
        "scoring": {
            "weights": {"prediction_accuracy": 0.35, "pnl_performance": 0.40, "risk_management": 0.25},
            "benchmark_pnl": 0.118,
            "max_allowed_drawdown": 0.10,
        },
    },
]

# ── Public accessors ──────────────────────────────────────────────────────────

def get_easy_scenario(idx: int = 0) -> dict:
    return EASY_SCENARIOS[idx % len(EASY_SCENARIOS)]


def get_medium_scenario(idx: int = 0) -> dict:
    return MEDIUM_SCENARIOS[idx % len(MEDIUM_SCENARIOS)]


def get_hard_scenario(idx: int = 0) -> dict:
    return HARD_SCENARIOS[idx % len(HARD_SCENARIOS)]


ALL_SCENARIOS = {
    "task_easy": EASY_SCENARIOS,
    "task_medium": MEDIUM_SCENARIOS,
    "task_hard": HARD_SCENARIOS,
}
