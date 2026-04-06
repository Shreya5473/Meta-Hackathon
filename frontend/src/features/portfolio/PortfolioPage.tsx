/**
 * PortfolioPage — full portfolio UI shown only to registered (email) users.
 *
 * Features:
 *  - Add / remove symbols from a curated asset list
 *  - Persist holdings to the backend (keyed by email)
 *  - Trigger live portfolio risk analysis (GTI + ML model)
 *  - Show per-asset risk sorted by severity
 *  - "data_unavailable" state rendered cleanly — no fake values
 */
import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    Briefcase, Plus, Trash2, BarChart3, AlertTriangle,
    RefreshCw, CheckCircle2, TrendingUp, TrendingDown, Minus, Info,
} from 'lucide-react'
import { cn } from '@/shared/ui/Panel'
import { useCart, useSaveCart, usePortfolioRisk } from '@/shared/api/hooks'
import type { CartHolding } from '@/shared/state/store'

// ── Curated asset universe (mirrors config/assets.yaml top picks) ─────────────
const ASSET_UNIVERSE: CartHolding[] = [
    { symbol: 'SPX',     label: 'S&P 500',        weight: 1, sector: 'broad_equity', region: 'americas' },
    { symbol: 'NDX',     label: 'Nasdaq 100',      weight: 1, sector: 'technology',   region: 'americas' },
    { symbol: 'DJI',     label: 'Dow Jones',       weight: 1, sector: 'broad_equity', region: 'americas' },
    { symbol: 'DAX',     label: 'DAX',             weight: 1, sector: 'broad_equity', region: 'europe' },
    { symbol: 'NKY',     label: 'Nikkei 225',      weight: 1, sector: 'broad_equity', region: 'asia_pacific' },
    { symbol: 'XAUUSD',  label: 'Gold',            weight: 1, sector: 'metals',       region: 'global' },
    { symbol: 'XAGUSD',  label: 'Silver',          weight: 1, sector: 'metals',       region: 'global' },
    { symbol: 'WTI',     label: 'WTI Crude Oil',   weight: 1, sector: 'energy',       region: 'middle_east' },
    { symbol: 'BRENT',   label: 'Brent Oil',       weight: 1, sector: 'energy',       region: 'middle_east' },
    { symbol: 'NATGAS',  label: 'Natural Gas',     weight: 1, sector: 'energy',       region: 'europe' },
    { symbol: 'COPPER',  label: 'Copper',          weight: 1, sector: 'metals',       region: 'asia_pacific' },
    { symbol: 'WHEAT',   label: 'Wheat',           weight: 1, sector: 'grains',       region: 'europe' },
    { symbol: 'EURUSD',  label: 'EUR/USD',         weight: 1, sector: 'currencies',   region: 'europe' },
    { symbol: 'USDJPY',  label: 'USD/JPY',         weight: 1, sector: 'currencies',   region: 'asia_pacific' },
    { symbol: 'USDCNY',  label: 'USD/CNY',         weight: 1, sector: 'currencies',   region: 'asia_pacific' },
]

const RISK_COLOR: Record<string, string> = {
    HIGH:     'text-red-400',
    ELEVATED: 'text-amber-400',
    MODERATE: 'text-yellow-400',
    LOW:      'text-green-400',
}

const RISK_BG: Record<string, string> = {
    HIGH:     'bg-red-500/10 border-red-500/30',
    ELEVATED: 'bg-amber-500/10 border-amber-500/30',
    MODERATE: 'bg-yellow-500/10 border-yellow-500/30',
    LOW:      'bg-green-500/10 border-green-500/30',
}

interface PortfolioPageProps {
    email: string
    onRegisterClick?: () => void
}

export function PortfolioPage({ email }: PortfolioPageProps) {
    const { data: cartData, isLoading: cartLoading } = useCart(email)
    const saveCart = useSaveCart(email)
    const riskMutation = usePortfolioRisk()

    const [holdings, setHoldings] = useState<CartHolding[]>([])
    const [saved, setSaved] = useState(false)
    const [searchQuery, setSearchQuery] = useState('')

    // Hydrate holdings from backend on first load
    useEffect(() => {
        if (cartData?.holdings && cartData.holdings.length > 0) {
            setHoldings(cartData.holdings)
        }
    }, [cartData])

    const addHolding = (asset: CartHolding) => {
        if (holdings.some(h => h.symbol === asset.symbol)) return
        setHoldings(prev => [...prev, { ...asset }])
        setSaved(false)
    }

    const removeHolding = (symbol: string) => {
        setHoldings(prev => prev.filter(h => h.symbol !== symbol))
        setSaved(false)
    }

    const handleSave = useCallback(async () => {
        if (holdings.length === 0) return
        try {
            await saveCart.mutateAsync({ holdings })
            setSaved(true)
        } catch {
            // error handled via mutation state
        }
    }, [holdings, saveCart])

    const handleAnalyse = useCallback(async () => {
        if (holdings.length === 0) return
        // Save first so backend has latest holdings
        await handleSave()
        riskMutation.mutate(email)
    }, [holdings, handleSave, riskMutation, email])

    const riskData = riskMutation.data
    const filteredUniverse = ASSET_UNIVERSE.filter(a =>
        !holdings.some(h => h.symbol === a.symbol) &&
        (a.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
         a.symbol.toLowerCase().includes(searchQuery.toLowerCase()))
    )

    return (
        <div className="h-full overflow-y-auto p-3 sm:p-5 space-y-4 font-mono">

            {/* ── Header ── */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Briefcase className="h-4 w-4 text-white" />
                    <h2 className="text-[13px] font-bold tracking-widest text-white uppercase">Portfolio</h2>
                </div>
                <span className="text-[10px] text-gray-500 border border-gray-700/50 rounded px-2 py-1">
                    {email}
                </span>
            </div>

            {/* ── My Holdings ── */}
            <section>
                <div className="flex items-center justify-between mb-2">
                    <p className="text-[10px] uppercase tracking-widest text-gray-500">
                        My Holdings ({holdings.length})
                    </p>
                    <div className="flex items-center gap-2">
                        {saveCart.isError && (
                            <span className="text-[10px] text-red-400">Save failed</span>
                        )}
                        <button
                            onClick={handleSave}
                            disabled={holdings.length === 0 || saveCart.isPending || saved}
                            className={cn(
                                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-semibold transition-all border',
                                saved
                                    ? 'bg-green-500/10 border-green-500/30 text-green-400 cursor-default'
                                    : 'bg-white/5 border-white/20 text-white hover:bg-white/10 disabled:opacity-40 disabled:cursor-not-allowed'
                            )}
                        >
                            {saveCart.isPending
                                ? <RefreshCw className="h-3 w-3 animate-spin" />
                                : saved
                                    ? <CheckCircle2 className="h-3 w-3" />
                                    : null
                            }
                            {saved ? 'SAVED' : 'SAVE'}
                        </button>
                        <button
                            onClick={handleAnalyse}
                            disabled={holdings.length === 0 || riskMutation.isPending || saveCart.isPending}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-semibold bg-purple-500/10 border border-purple-500/30 text-purple-400 hover:bg-purple-500/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                            {riskMutation.isPending
                                ? <RefreshCw className="h-3 w-3 animate-spin" />
                                : <BarChart3 className="h-3 w-3" />
                            }
                            ANALYSE RISK
                        </button>
                    </div>
                </div>

                {cartLoading ? (
                    <div className="flex items-center justify-center py-8 text-gray-600 text-[11px]">
                        <RefreshCw className="h-3.5 w-3.5 animate-spin mr-2" /> Loading…
                    </div>
                ) : holdings.length === 0 ? (
                    <div className="flex items-center gap-2 p-4 rounded-lg border border-dashed border-gray-700/50 text-gray-600 text-[11px]">
                        <Plus className="h-3.5 w-3.5" />
                        Add assets from the list below to build your portfolio
                    </div>
                ) : (
                    <div className="space-y-1.5">
                        <AnimatePresence initial={false}>
                            {holdings.map(h => (
                                <motion.div
                                    key={h.symbol}
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    transition={{ duration: 0.18 }}
                                    className="flex items-center justify-between px-3 py-2 rounded-lg bg-[#07091a]/80 border border-white/10 group hover:border-white/20 transition-colors"
                                >
                                    <div className="flex items-center gap-2 min-w-0">
                                        <span className="text-white font-bold text-[11px] shrink-0">{h.symbol}</span>
                                        <span className="text-gray-400 text-[11px] truncate">{h.label}</span>
                                        {h.sector && (
                                            <span className="hidden sm:inline text-[9px] text-gray-600 border border-gray-700/40 rounded px-1.5 py-0.5 shrink-0">
                                                {h.sector}
                                            </span>
                                        )}
                                    </div>
                                    <button
                                        onClick={() => removeHolding(h.symbol)}
                                        className="shrink-0 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/10 hover:text-red-400 text-gray-600 transition-all"
                                    >
                                        <Trash2 className="h-3.5 w-3.5" />
                                    </button>
                                </motion.div>
                            ))}
                        </AnimatePresence>
                    </div>
                )}
            </section>

            {/* ── Risk Analysis Results ── */}
            <AnimatePresence>
                {(riskMutation.data || riskMutation.isError) && (
                    <motion.section
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 12 }}
                        className="space-y-3"
                    >
                        <p className="text-[10px] uppercase tracking-widest text-gray-500">Risk Analysis</p>

                        {riskMutation.isError ? (
                            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-[11px]">
                                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                                {String(riskMutation.error)}
                            </div>
                        ) : riskData ? (
                            <>
                                {/* Summary card */}
                                <div className={cn(
                                    'flex items-center justify-between p-3 rounded-lg border',
                                    RISK_BG[riskData.risk_classification] ?? RISK_BG.LOW
                                )}>
                                    <div>
                                        <p className="text-[9px] uppercase tracking-widest text-gray-500 mb-0.5">Overall Risk</p>
                                        <p className={cn('text-sm font-bold', RISK_COLOR[riskData.risk_classification] ?? 'text-green-400')}>
                                            {riskData.risk_classification}
                                        </p>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-[9px] uppercase tracking-widest text-gray-500 mb-0.5">Vol Spike Prob</p>
                                        <p className="text-sm font-bold text-white">
                                            {(riskData.overall_vol_risk * 100).toFixed(1)}%
                                        </p>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-[9px] uppercase tracking-widest text-gray-500 mb-0.5">GTI Exposure</p>
                                        <p className="text-sm font-bold text-white">
                                            {(riskData.overall_gti_exposure * 100).toFixed(1)}%
                                        </p>
                                    </div>
                                </div>

                                {/* Per-asset rows (sorted by risk) */}
                                <div className="space-y-1.5">
                                    {riskData.holdings.map((h: any) => (
                                        <HoldingRiskRow key={h.symbol} holding={h} />
                                    ))}
                                </div>

                                <p className="text-[9px] text-gray-600 flex items-center gap-1">
                                    <Info className="h-3 w-3" /> Not financial advice. Live data only. Data unavailable assets are excluded from aggregates.
                                </p>
                            </>
                        ) : null}
                    </motion.section>
                )}
            </AnimatePresence>

            {/* ── Add Assets ── */}
            <section>
                <p className="text-[10px] uppercase tracking-widest text-gray-500 mb-2">Add Assets</p>
                <input
                    type="text"
                    placeholder="Search assets…"
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    className="w-full bg-[#07091a]/80 border border-gray-700/50 rounded-lg px-3 py-2 text-[11px] text-white placeholder-gray-600 focus:outline-none focus:border-white/30 mb-2"
                />
                <div className="space-y-1">
                    {filteredUniverse.map(asset => (
                        <button
                            key={asset.symbol}
                            onClick={() => addHolding(asset)}
                            className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-[#07091a]/60 border border-gray-700/30 hover:border-white/20 hover:bg-white/3 transition-all text-left group"
                        >
                            <div className="flex items-center gap-2">
                                <span className="text-white/70 font-bold text-[11px] group-hover:text-white transition-colors">{asset.symbol}</span>
                                <span className="text-gray-500 text-[11px]">{asset.label}</span>
                            </div>
                            <Plus className="h-3.5 w-3.5 text-gray-600 group-hover:text-white transition-colors" />
                        </button>
                    ))}
                    {filteredUniverse.length === 0 && searchQuery && (
                        <p className="text-[11px] text-gray-600 px-3 py-2">No matching assets</p>
                    )}
                </div>
            </section>
        </div>
    )
}

// ── Per-asset risk row ────────────────────────────────────────────────────────

function HoldingRiskRow({ holding }: { holding: any }) {
    if (holding.data_status === 'data_unavailable') {
        return (
            <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-800/30 border border-gray-700/30">
                <div className="flex items-center gap-2">
                    <span className="text-gray-500 font-bold text-[11px]">{holding.symbol}</span>
                    <span className="text-gray-600 text-[11px]">{holding.label}</span>
                </div>
                <span className="text-[10px] text-gray-600 border border-gray-700/40 rounded px-2 py-0.5">
                    DATA UNAVAILABLE
                </span>
            </div>
        )
    }

    const prob = holding.vol_spike_prob ?? 0
    const bias = holding.directional_bias ?? 0
    const rec = holding.recommendation ?? 'HOLD'
    const recColor = rec === 'Buy'
        ? 'text-green-400 border-green-500/30 bg-green-500/10'
        : rec === 'Sell'
            ? 'text-red-400 border-red-500/30 bg-red-500/10'
            : 'text-gray-400 border-gray-600/30 bg-gray-600/10'

    return (
        <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-[#07091a]/80 border border-white/10">
            <div className="flex items-center gap-2 min-w-0">
                <span className="text-white font-bold text-[11px] shrink-0">{holding.symbol}</span>
                <span className="text-gray-400 text-[11px] truncate hidden sm:inline">{holding.label}</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
                {/* Vol spike probability bar */}
                <div className="hidden sm:flex items-center gap-1">
                    <span className="text-[9px] text-gray-600">vol</span>
                    <div className="w-16 h-1.5 rounded-full bg-gray-800 overflow-hidden">
                        <div
                            className={cn(
                                'h-full rounded-full transition-all',
                                prob >= 0.7 ? 'bg-red-400' : prob >= 0.5 ? 'bg-amber-400' : 'bg-green-400'
                            )}
                            style={{ width: `${Math.round(prob * 100)}%` }}
                        />
                    </div>
                    <span className="text-[9px] text-gray-400 tabular-nums w-7 text-right">
                        {Math.round(prob * 100)}%
                    </span>
                </div>
                {/* Directional bias */}
                <span className={cn(
                    'text-[9px]',
                    bias > 0.15 ? 'text-green-400' : bias < -0.15 ? 'text-red-400' : 'text-gray-500'
                )}>
                    {bias > 0.15 ? <TrendingUp className="h-3 w-3 inline" />
                        : bias < -0.15 ? <TrendingDown className="h-3 w-3 inline" />
                            : <Minus className="h-3 w-3 inline" />}
                </span>
                {/* Recommendation badge */}
                <span className={cn('text-[9px] font-bold border rounded px-1.5 py-0.5', recColor)}>
                    {rec.toUpperCase()}
                </span>
            </div>
        </div>
    )
}

// ── Gate component — shown when user is not yet registered ───────────────────

export function PortfolioGate({ onRegisterClick }: { onRegisterClick: () => void }) {
    return (
        <div className="flex flex-col items-center justify-center h-full px-6 text-center gap-5 font-mono">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-400/20 to-pink-600/20 border border-purple-400/30 flex items-center justify-center shadow-[0_0_20px_rgba(168,85,247,0.15)]">
                <Briefcase className="w-7 h-7 text-purple-400" />
            </div>
            <div className="space-y-2">
                <h3 className="text-base font-bold text-white tracking-wide">Portfolio Feature</h3>
                <p className="text-sm text-gray-400 max-w-xs leading-relaxed">
                    Register your email to save and track your holdings and receive live geopolitical risk analysis on your portfolio.
                </p>
            </div>
            <button
                onClick={onRegisterClick}
                className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-purple-500/20 to-pink-500/20 border border-purple-400/40 text-purple-300 font-semibold text-[13px] hover:from-purple-500/30 hover:to-pink-500/30 hover:border-purple-400/60 transition-all shadow-[0_0_20px_rgba(168,85,247,0.1)]"
            >
                <Plus className="h-4 w-4" />
                Register Your Email
            </button>
            <p className="text-[10px] text-gray-600">
                No password. No signup. Just your email.
            </p>
        </div>
    )
}
