import type { GTIResponse, SignalsResponse, EventsResponse } from './schemas'

// ── Globe countries fallback ───────────────────────────────────────────────
export const fallbackGlobeCountries = {
    global_gti: 67.4,
    ts: new Date().toISOString(),
    countries: [
        { iso: "US", name: "United States", lat: 37.09, lng: -95.71, gti_score: 38, tension_level: "low" },
        { iso: "CN", name: "China", lat: 35.86, lng: 104.19, gti_score: 58, tension_level: "medium" },
        { iso: "RU", name: "Russia", lat: 61.52, lng: 105.31, gti_score: 92, tension_level: "critical" },
        { iso: "UA", name: "Ukraine", lat: 48.37, lng: 31.16, gti_score: 88, tension_level: "critical" },
        { iso: "IR", name: "Iran", lat: 32.42, lng: 53.68, gti_score: 85, tension_level: "critical" },
        { iso: "IL", name: "Israel", lat: 31.04, lng: 34.85, gti_score: 82, tension_level: "critical" },
        { iso: "KP", name: "North Korea", lat: 40.33, lng: 127.51, gti_score: 80, tension_level: "critical" },
        { iso: "SA", name: "Saudi Arabia", lat: 23.88, lng: 45.07, gti_score: 50, tension_level: "medium" },
        { iso: "DE", name: "Germany", lat: 51.16, lng: 10.45, gti_score: 20, tension_level: "low" },
        { iso: "GB", name: "United Kingdom", lat: 55.37, lng: -3.43, gti_score: 22, tension_level: "low" },
        { iso: "IN", name: "India", lat: 20.59, lng: 78.96, gti_score: 35, tension_level: "low" },
        { iso: "JP", name: "Japan", lat: 36.20, lng: 138.25, gti_score: 25, tension_level: "low" },
        { iso: "BR", name: "Brazil", lat: -14.23, lng: -51.92, gti_score: 32, tension_level: "low" },
        { iso: "TR", name: "Turkey", lat: 38.96, lng: 35.24, gti_score: 45, tension_level: "medium" },
        { iso: "PK", name: "Pakistan", lat: 30.37, lng: 69.34, gti_score: 52, tension_level: "medium" },
        { iso: "YE", name: "Yemen", lat: 15.55, lng: 48.51, gti_score: 78, tension_level: "high" },
        { iso: "SY", name: "Syria", lat: 34.80, lng: 38.99, gti_score: 75, tension_level: "high" },
        { iso: "IQ", name: "Iraq", lat: 33.22, lng: 43.67, gti_score: 72, tension_level: "high" },
        { iso: "AF", name: "Afghanistan", lat: 33.93, lng: 67.70, gti_score: 70, tension_level: "high" },
        { iso: "MM", name: "Myanmar", lat: 21.91, lng: 95.95, gti_score: 62, tension_level: "medium" },
        { iso: "EG", name: "Egypt", lat: 26.82, lng: 30.80, gti_score: 40, tension_level: "medium" },
        { iso: "NG", name: "Nigeria", lat: 9.08, lng: 8.67, gti_score: 42, tension_level: "medium" },
        { iso: "VE", name: "Venezuela", lat: 6.42, lng: -66.58, gti_score: 58, tension_level: "medium" },
        { iso: "AU", name: "Australia", lat: -25.27, lng: 133.77, gti_score: 15, tension_level: "low" },
        { iso: "CA", name: "Canada", lat: 56.13, lng: -106.34, gti_score: 15, tension_level: "low" },
        { iso: "KR", name: "South Korea", lat: 35.90, lng: 127.76, gti_score: 35, tension_level: "low" },
        { iso: "PL", name: "Poland", lat: 51.91, lng: 19.14, gti_score: 30, tension_level: "low" },
        { iso: "AE", name: "UAE", lat: 23.42, lng: 53.84, gti_score: 30, tension_level: "low" },
        { iso: "ZA", name: "South Africa", lat: -30.55, lng: 22.93, gti_score: 40, tension_level: "medium" },
        { iso: "MX", name: "Mexico", lat: 23.63, lng: -102.55, gti_score: 38, tension_level: "low" },
    ],
    arcs: [
        { startLat: 61.52, startLng: 105.31, endLat: 48.37, endLng: 31.16, type: "military_escalation", severity: 0.95, fromName: "Russia", toName: "Ukraine", color: ["rgba(239,68,68,0.9)", "rgba(220,38,38,0.9)"] },
        { startLat: 37.09, startLng: -95.71, endLat: 35.86, endLng: 104.19, type: "trade_restrictions", severity: 0.72, fromName: "United States", toName: "China", color: ["rgba(245,158,11,0.8)", "rgba(234,179,8,0.8)"] },
        { startLat: 32.42, startLng: 53.68, endLat: 31.04, endLng: 34.85, type: "military_escalation", severity: 0.88, fromName: "Iran", toName: "Israel", color: ["rgba(239,68,68,0.9)", "rgba(220,38,38,0.9)"] },
        { startLat: 37.09, startLng: -95.71, endLat: 32.42, endLng: 53.68, type: "sanctions", severity: 0.80, fromName: "United States", toName: "Iran", color: ["rgba(249,115,22,0.9)", "rgba(239,68,68,0.7)"] },
        { startLat: 37.09, startLng: -95.71, endLat: 61.52, endLng: 105.31, type: "sanctions", severity: 0.85, fromName: "United States", toName: "Russia", color: ["rgba(249,115,22,0.9)", "rgba(239,68,68,0.7)"] },
        { startLat: 35.86, startLng: 104.19, endLat: 20.59, endLng: 78.96, type: "diplomatic_activity", severity: 0.55, fromName: "China", toName: "India", color: ["rgba(14,165,233,0.7)", "rgba(99,102,241,0.7)"] },
        { startLat: 23.88, startLng: 45.07, endLat: 15.55, endLng: 48.51, type: "military_escalation", severity: 0.75, fromName: "Saudi Arabia", toName: "Yemen", color: ["rgba(239,68,68,0.9)", "rgba(220,38,38,0.9)"] },
        { startLat: 40.33, startLng: 127.51, endLat: 35.90, endLng: 127.76, type: "military_escalation", severity: 0.70, fromName: "North Korea", toName: "South Korea", color: ["rgba(239,68,68,0.9)", "rgba(220,38,38,0.9)"] },
    ],
    event_markers: [
        { id: "e1", lat: 32.0, lng: 35.0, title: "Middle East Escalation", severity: 0.9, classification: "military_escalation", region: "IL", ts: new Date(Date.now() - 3600000).toISOString() },
        { id: "e2", lat: 50.0, lng: 30.0, title: "Ukraine Conflict Intensifies", severity: 0.85, classification: "military_escalation", region: "UA", ts: new Date(Date.now() - 7200000).toISOString() },
        { id: "e3", lat: 39.0, lng: 126.0, title: "DPRK Missile Test", severity: 0.78, classification: "military_escalation", region: "KP", ts: new Date(Date.now() - 14400000).toISOString() },
        { id: "e4", lat: 25.0, lng: 55.0, title: "Strait of Hormuz Naval Activity", severity: 0.8, classification: "military_escalation", region: "AE", ts: new Date(Date.now() - 21600000).toISOString() },
    ],
}

// ── Market impact fallback (used when API fails or returns null) ───────────
const FALLBACK_NAMES: Record<string, string> = {
    US: "United States", CN: "China", RU: "Russia", UA: "Ukraine", IR: "Iran", IL: "Israel",
    SA: "Saudi Arabia", DE: "Germany", GB: "United Kingdom", JP: "Japan", IN: "India", BR: "Brazil",
    TR: "Turkey", PK: "Pakistan", KP: "North Korea", KR: "South Korea", AU: "Australia", CA: "Canada",
    MX: "Mexico", EG: "Egypt", ZA: "South Africa", NG: "Nigeria", AE: "UAE",
}
const FALLBACK_ASSETS: Record<string, string[]> = {
    RU: ["USOIL", "XAUUSD", "NATGAS"], UA: ["WHEAT", "CORN", "USOIL"], IR: ["USOIL", "NATGAS", "XAUUSD"],
    CN: ["COPPER", "XAUUSD", "USOIL"], US: ["SPX", "DXY", "XAUUSD"], SA: ["USOIL", "NATGAS"],
}
const BASE_PRICES: Record<string, number> = { XAUUSD: 2340, USOIL: 82, NATGAS: 3.2, WHEAT: 580, CORN: 430, SPX: 5200, DXY: 104, COPPER: 4.5 }

function genOhlcv(base: number, n = 30): Array<{ ts: string; open: number; high: number; low: number; close: number; volume: number }> {
    const rows: Array<{ ts: string; open: number; high: number; low: number; close: number; volume: number }> = []
    let price = base
    const now = Date.now()
    for (let i = 0; i < n; i++) {
        const chg = (Math.random() - 0.5) * 0.03
        const open_ = price
        const close = price * (1 + chg)
        rows.push({
            ts: new Date(now - (n - i) * 3600000).toISOString(),
            open: open_, high: Math.max(open_, close) * 1.005, low: Math.min(open_, close) * 0.995,
            close, volume: Math.floor(100000 + Math.random() * 4900000),
        })
        price = close
    }
    return rows
}

export function fallbackMarketImpact(iso: string): Record<string, any> {
    const code = (iso || "US").toUpperCase().slice(0, 2)
    const assets = FALLBACK_ASSETS[code] ?? ["XAUUSD", "USOIL", "SPX"]
    const quotes = assets.map((a) => {
        const base = BASE_PRICES[a] ?? 100
        const chg = (Math.random() - 0.5) * 5
        return {
            symbol: a,
            price: Math.round(base * (1 + chg / 100) * 100) / 100,
            change_pct: Math.round(chg * 100) / 100,
            high: base * 1.01,
            low: base * 0.99,
            open: base * 1.002,
        }
    })
    const charts: Record<string, any[]> = {}
    quotes.forEach((q) => {
        charts[q.symbol] = genOhlcv(q.price / (1 + q.change_pct / 100))
    })
    return {
        iso: code,
        name: FALLBACK_NAMES[code] ?? iso,
        gti_score: 40 + (Math.random() - 0.5) * 40,
        affected_assets: assets,
        quotes,
        charts,
        sector_exposure: { Energy: 0.5, Defense: 0.3, Commodities: 0.6, Financials: 0.3, Technology: 0.2 },
        currency_impact: [{ pair: "USD/EUR", change_pct: 0.1 }, { pair: "USD/JPY", change_pct: -0.2 }, { pair: "DXY", change_pct: 0.05 }],
        ts: new Date().toISOString(),
    }
}

// ── Enhanced signals fallback ──────────────────────────────────────────────
export const fallbackEnhancedSignals = {
    signals: [
        {
            asset: "GOLD (XAU/USD)",
            asset_class: "commodity",
            action: "BUY",
            confidence_pct: 86,
            uncertainty_pct: 8,
            reasoning_summary: "Safe-haven demand increasing due to Middle East escalation and rising global tension index.",
            triggering_event: "Iran-Israel Missile Exchange — Severity 0.88",
            impact_path: ["Middle East Conflict", "Safe Haven Demand", "Gold Price"],
            reasoning_chain: [
                { step_number: 1, description: "GTI elevated to 85 in Middle East region", evidence: "Multiple conflict signals detected in past 6h", confidence_contribution: 0.35 },
                { step_number: 2, description: "Historical correlation: GTI >80 → Gold +3.2% avg", evidence: "Backtested over 847 similar events", confidence_contribution: 0.28 },
                { step_number: 3, description: "USD weakening trend supports commodity rally", evidence: "DXY -0.4% in past session", confidence_contribution: 0.23 },
            ],
            model_version: "1.0.0",
            pipeline_version: "1.0.0",
            ts: new Date().toISOString(),
        },
        {
            asset: "CRUDE OIL (WTI)",
            asset_class: "commodity",
            action: "BUY",
            confidence_pct: 79,
            uncertainty_pct: 14,
            reasoning_summary: "Supply disruption risk from Strait of Hormuz activity driving oil premium.",
            triggering_event: "Naval Drills Near Strait of Hormuz — Severity 0.80",
            impact_path: ["Iran Tension", "Hormuz Supply Risk", "Oil Price"],
            reasoning_chain: [
                { step_number: 1, description: "Naval activity near Hormuz detected", evidence: "GDELT conflict events: 14 in past 4h", confidence_contribution: 0.40 },
                { step_number: 2, description: "20% global oil supply transits Hormuz", evidence: "EIA supply route data", confidence_contribution: 0.25 },
                { step_number: 3, description: "OPEC+ spare capacity limited", evidence: "Current utilization >92%", confidence_contribution: 0.14 },
            ],
            model_version: "1.0.0",
            pipeline_version: "1.0.0",
            ts: new Date().toISOString(),
        },
        {
            asset: "S&P 500 (SPX)",
            asset_class: "equity",
            action: "SELL",
            confidence_pct: 72,
            uncertainty_pct: 18,
            reasoning_summary: "Risk premium expansion and sector rotation into defensives amid geopolitical uncertainty.",
            triggering_event: "US-Russia Sanctions Escalation — Severity 0.85",
            impact_path: ["Geopolitical Risk", "Risk Premium", "Equity Valuations"],
            reasoning_chain: [
                { step_number: 1, description: "Global GTI at 67.4 — historically bearish for equities", evidence: "Historical win rate: 68% SELL signals at GTI >65", confidence_contribution: 0.30 },
                { step_number: 2, description: "VIX elevated, options market pricing in uncertainty", evidence: "VIX at 22.4, above 30-day avg of 16.8", confidence_contribution: 0.22 },
                { step_number: 3, description: "Tech sector particularly vulnerable to supply chain disruption", evidence: "Taiwan Strait tensions affecting semiconductor supply chain", confidence_contribution: 0.20 },
            ],
            model_version: "1.0.0",
            pipeline_version: "1.0.0",
            ts: new Date().toISOString(),
        },
        {
            asset: "WHEAT FUTURES",
            asset_class: "commodity",
            action: "BUY",
            confidence_pct: 68,
            uncertainty_pct: 22,
            reasoning_summary: "Ukraine conflict disrupting Black Sea grain exports; supply shock likely to persist.",
            triggering_event: "Ukraine Black Sea Shipping Disruption — Severity 0.88",
            impact_path: ["Ukraine Conflict", "Black Sea Export Disruption", "Wheat Price"],
            reasoning_chain: [
                { step_number: 1, description: "Ukraine + Russia supply ~30% of global wheat exports", evidence: "UN FAO trade data 2024", confidence_contribution: 0.38 },
                { step_number: 2, description: "Shipping insurance premiums spiking in Black Sea", evidence: "+340% premium increase vs pre-conflict", confidence_contribution: 0.18 },
                { step_number: 3, description: "Alternative supply routes insufficient to offset", evidence: "Argentina and Australia crop yield below avg", confidence_contribution: 0.12 },
            ],
            model_version: "1.0.0",
            pipeline_version: "1.0.0",
            ts: new Date().toISOString(),
        },
        {
            asset: "USD/JPY",
            asset_class: "currency",
            action: "SELL",
            confidence_pct: 61,
            uncertainty_pct: 25,
            reasoning_summary: "JPY safe-haven flows increasing; Bank of Japan intervention risk elevated.",
            triggering_event: "North Korea DPRK Missile Test — Severity 0.78",
            impact_path: ["DPRK Escalation", "Asia Safe Haven Flows", "JPY Strength"],
            reasoning_chain: [
                { step_number: 1, description: "Historical: DPRK events → JPY +0.8% avg within 24h", evidence: "15 similar events since 2016", confidence_contribution: 0.28 },
                { step_number: 2, description: "BOJ signaling readiness for FX intervention", evidence: "Verbal intervention at 155.00 level", confidence_contribution: 0.20 },
                { step_number: 3, description: "Position unwind from carry trade risk", evidence: "Large short JPY positions outstanding", confidence_contribution: 0.13 },
            ],
            model_version: "1.0.0",
            pipeline_version: "1.0.0",
            ts: new Date().toISOString(),
        },
        {
            asset: "NATURAL GAS (NATGAS)",
            asset_class: "commodity",
            action: "HOLD",
            confidence_pct: 55,
            uncertainty_pct: 30,
            reasoning_summary: "European storage above seasonal norms offsetting Russia supply risk. Mixed signals.",
            triggering_event: "Russia-EU Energy Dispute — Severity 0.65",
            impact_path: ["Russia Sanctions", "EU Energy Security", "Gas Storage Levels"],
            reasoning_chain: [
                { step_number: 1, description: "EU gas storage at 68% — above 5-year avg of 55%", evidence: "GIE AGSI+ storage data", confidence_contribution: 0.20 },
                { step_number: 2, description: "LNG imports from US compensating pipeline shortfall", evidence: "US LNG export capacity at record", confidence_contribution: 0.18 },
                { step_number: 3, description: "Demand uncertainty with mild winter forecast", evidence: "NOAA weather models", confidence_contribution: 0.17 },
            ],
            model_version: "1.0.0",
            pipeline_version: "1.0.0",
            ts: new Date().toISOString(),
        },
    ],
    model_version: "1.0.0",
    pipeline_version: "1.0.0",
    data_as_of: new Date().toISOString(),
    not_financial_advice: true,
}

export const fallbackGTI: GTIResponse = {
    gti_value: 71.4,
    gti_delta_1h: 2.1,
    ts: new Date().toISOString(),
    top_drivers: [
        { region: "Middle East", driver: "Conflict", contribution_weight: 0.4 },
        { region: "Asia Pacific", driver: "Trade Tensions", contribution_weight: 0.3 }
    ]
}

export const fallbackSignals: SignalsResponse['signals'] = [
    {
        symbol: "XAU/USD",
        sector: "Commodities",
        region: "Global",
        recommendation: "BUY",
        confidence_score: 85,
        uncertainty: 10,
        price: 2314.5,
        directional_bias: 1.2,
        reasoning: "Safe haven flows increasing due to elevated geopolitical stress.",
        risk_factors: ["Sudden de-escalation", "Strong USD data"],
        correlated_assets: ["SLV", "GDX"]
    },
    {
        symbol: "SPX",
        sector: "Equities",
        region: "North America",
        recommendation: "SELL",
        confidence_score: 65,
        uncertainty: 20,
        price: 5120.3,
        directional_bias: -1.5,
        reasoning: "Risk premium expanding. Sector rotation into defensives observed.",
        risk_factors: ["Earnings surprises", "Fed dovish pivot"],
        correlated_assets: ["QQQ", "VIX"]
    }
]

export const fallbackEvents: EventsResponse['events'] = [
    {
        id: "1",
        title: "Strait of Hormuz Naval Drills",
        occurred_at: new Date(Date.now() - 3600000).toISOString(),
        severity_score: 0.85,
        region: "Middle East",
        magnitude: 0.9,
        summary: "Unscheduled massive naval exercises observed, escalating regional risk premium."
    },
    {
        id: "2",
        title: "ECB Emergency Statement",
        occurred_at: new Date(Date.now() - 7200000).toISOString(),
        severity_score: 0.65,
        region: "Europe",
        magnitude: 0.6,
        summary: "Central bank highlights concerns over energy supply stability."
    }
]
