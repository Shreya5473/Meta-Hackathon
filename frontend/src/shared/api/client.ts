import { GTIResponseSchema, SignalsResponseSchema, EventsResponseSchema, type GTIResponse, type SignalsResponse, type EventsResponse } from './schemas'
import { fallbackGTI, fallbackSignals, fallbackEvents, fallbackGlobeCountries, fallbackEnhancedSignals, fallbackMarketImpact } from './mockData'

// Fallback for production when VITE_API_URL isn't available at build (e.g. Vercel env not passed)
const RENDER_API = 'https://geotrade-8pei.onrender.com/api/v1'
const defaultBase = typeof window !== 'undefined' && !/localhost|127\.0\.0\.1/.test(window.location.hostname)
  ? RENDER_API
  : 'http://localhost:8000/api/v1'
export const API_BASE = (import.meta.env.VITE_API_URL as string)?.trim() || defaultBase

function mapSignalV2ToLegacy(signal: any): any {
    return {
        symbol: signal.symbol,
        sector: signal.sector ?? signal.category,
        asset_class: signal.asset_class,
        category: signal.category,
        region: signal.region,
        recommendation: signal.action,
        confidence_score: typeof signal.confidence_pct === 'number' ? signal.confidence_pct : 50,
        uncertainty: typeof signal.uncertainty_pct === 'number' ? signal.uncertainty_pct : 30,
        price: signal.trade_setup?.current_price ?? undefined,
        directional_bias: signal.action === 'BUY'
            ? Math.abs(signal.trade_setup?.risk_reward ?? 1)
            : signal.action === 'SELL'
                ? -Math.abs(signal.trade_setup?.risk_reward ?? 1)
                : 0,
        reasoning: signal.reasoning_summary ?? '',
        risk_factors: [],
        correlated_assets: signal.related_assets ?? [],
    }
}

function mapSignalsAssetsToLegacy(signal: any): any {
    return {
        ...signal,
        confidence_score: typeof signal.confidence_score === 'number'
            ? signal.confidence_score * 100
            : (1 - (signal.uncertainty ?? 0.5)) * 100,
        uncertainty: typeof signal.uncertainty === 'number' ? signal.uncertainty * 100 : 40,
        directional_bias: typeof signal.directional_bias === 'number' ? signal.directional_bias * 100 : 0,
    }
}

export const api = {
    getGti: async (): Promise<GTIResponse> => {
        try {
            const res = await fetch(`${API_BASE}/gti/current`, { signal: AbortSignal.timeout(5000) })
            if (!res.ok) return fallbackGTI
            const json = await res.json()
            const parsed = GTIResponseSchema.safeParse(json)
            if (!parsed.success) return fallbackGTI
            return parsed.data
        } catch {
            return fallbackGTI
        }
    },

    getSignals: async (): Promise<SignalsResponse> => {
        // Primary: richer event-aware signal engine (v2)
        try {
            const res = await fetch(`${API_BASE}/signals/v2/all?limit=80`, { signal: AbortSignal.timeout(10000) })
            if (res.ok) {
                const json = await res.json()
                if (Array.isArray(json?.signals) && json.signals.length > 0) {
                    return { signals: json.signals.map(mapSignalV2ToLegacy) }
                }
            }
        } catch {
            // fallback below
        }

        // Secondary: legacy model endpoint
        try {
            const res = await fetch(`${API_BASE}/signals/assets`, { signal: AbortSignal.timeout(5000) })
            if (!res.ok) return { signals: fallbackSignals }
            const json = await res.json()
            const normalized = {
                ...json,
                signals: Array.isArray(json?.signals) ? json.signals.map(mapSignalsAssetsToLegacy) : [],
            }
            const parsed = SignalsResponseSchema.safeParse(normalized)
            if (!parsed.success) return { signals: fallbackSignals }
            return parsed.data
        } catch {
            return { signals: fallbackSignals }
        }
    },

    getEvents: async (): Promise<EventsResponse> => {
        try {
            const res = await fetch(`${API_BASE}/events/timeline`, { signal: AbortSignal.timeout(5000) })
            if (!res.ok) return { events: fallbackEvents }
            const json = await res.json()
            const parsed = EventsResponseSchema.safeParse(json)
            if (!parsed.success) return { events: fallbackEvents }
            return parsed.data
        } catch {
            return { events: fallbackEvents }
        }
    },

    getGlobeCountries: async (): Promise<any> => {
        try {
            const res = await fetch(`${API_BASE}/globe/countries`, { signal: AbortSignal.timeout(5000) })
            if (!res.ok) return fallbackGlobeCountries
            return res.json()
        } catch {
            return fallbackGlobeCountries
        }
    },

    getCountryMarketImpact: async (iso: string): Promise<any> => {
        try {
            const res = await fetch(`${API_BASE}/globe/market-impact/${encodeURIComponent(iso)}`, { signal: AbortSignal.timeout(8000) })
            if (!res.ok) return fallbackMarketImpact(iso)
            return res.json()
        } catch {
            return fallbackMarketImpact(iso)
        }
    },

    getEnhancedSignals: async (region?: string): Promise<any> => {
        try {
            const url = region
                ? `${API_BASE}/signals/enhanced?region=${encodeURIComponent(region)}`
                : `${API_BASE}/signals/enhanced`
            const res = await fetch(url, { signal: AbortSignal.timeout(8000) })
            if (!res.ok) return fallbackEnhancedSignals
            return res.json()
        } catch {
            return fallbackEnhancedSignals
        }
    },

    getSignalsV2: async (params?: { category?: string; action?: string; limit?: number }): Promise<any> => {
        try {
            const qs = new URLSearchParams()
            if (params?.category) qs.set('category', params.category)
            if (params?.action)   qs.set('action', params.action)
            if (params?.limit)    qs.set('limit', String(params.limit))
            const url = `${API_BASE}/signals/v2/all${qs.toString() ? '?' + qs.toString() : ''}`
            const res = await fetch(url, { signal: AbortSignal.timeout(10000) })
            if (!res.ok) return null
            return res.json()
        } catch {
            return null
        }
    },

    getAssetUniverse: async (): Promise<any> => {
        try {
            const res = await fetch(`${API_BASE}/signals/v2/universe`, { signal: AbortSignal.timeout(8000) })
            if (!res.ok) return null
            return res.json()
        } catch {
            return null
        }
    },

    getLivePrices: async (symbols?: string[]): Promise<Record<string, { price: number; change_pct: number; source?: string }>> => {
        try {
            const qs = new URLSearchParams()
            if (symbols && symbols.length > 0) {
                qs.set('symbols', symbols.join(','))
            }
            const url = `${API_BASE}/market/live${qs.toString() ? '?' + qs.toString() : ''}`
            const res = await fetch(url, { signal: AbortSignal.timeout(5000) })
            if (!res.ok) return {}
            const json = await res.json()
            const items = Array.isArray(json?.prices) ? json.prices : []
            return Object.fromEntries(
                items
                    .filter((row: any) => row?.symbol && typeof row?.price === 'number')
                    .map((row: any) => [String(row.symbol), { price: row.price, change_pct: row.change_pct ?? 0, source: row.source }])
            )
        } catch {
            return {}
        }
    },

    simulateScenario: async (params: any) => {
        const res = await fetch(`${API_BASE}/simulate/scenario`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(params)
        })
        return res.json()
    },
    evaluatePortfolio: async (params: any) => {
        const res = await fetch(`${API_BASE}/portfolio/evaluate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(params)
        })
        return res.json()
    },

    // ── Cart / email-keyed portfolio ──────────────────────────────────────
    getCart: async (email: string): Promise<any> => {
        try {
            const res = await fetch(
                `${API_BASE}/portfolio/cart?email=${encodeURIComponent(email)}`,
                { signal: AbortSignal.timeout(8000) }
            )
            if (!res.ok) return null
            return res.json()
        } catch {
            return null
        }
    },

    saveCart: async (email: string, holdings: any[], name = 'My Portfolio'): Promise<any> => {
        const res = await fetch(`${API_BASE}/portfolio/cart`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, holdings, name }),
        })
        if (!res.ok) throw new Error(`saveCart failed: ${res.status}`)
        return res.json()
    },

    getPortfolioRisk: async (email: string): Promise<any> => {
        const res = await fetch(`${API_BASE}/portfolio/risk`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email }),
            signal: AbortSignal.timeout(20000),
        })
        if (!res.ok) {
            const err = await res.json().catch(() => ({}))
            throw new Error(err?.detail || `Risk request failed: ${res.status}`)
        }
        return res.json()
    },
}
