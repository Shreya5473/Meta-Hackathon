/**
 * TradingCharts — AI Trading Signals Screen
 *
 * Three-column layout:
 *   LEFT   — Asset universe browser (grouped by category)
 *   CENTER — Signal card feed (filtered by selected category/action)
 *   RIGHT  — Expanded signal detail (trade setup, reliability, timeline, reasoning)
 */
import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    TrendingUp, TrendingDown, Minus, ChevronLeft,
    AlertTriangle, BarChart2, Clock, Target, Shield, Zap,
    RefreshCw, Filter, X, Info, Activity
} from 'lucide-react'
import { api } from '../../shared/api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface TradeSetup {
    current_price: number
    entry_price: number
    stop_loss: number
    target_price: number
    risk_reward: number
    atr_pct: number
    max_position_pct: number
}

interface Reliability {
    historical_accuracy: number
    win_rate: number
    sharpe_ratio: number
    max_drawdown: number
}

interface ReasoningStep {
    step: number
    label: string
    description: string
    evidence: string
    phase: string
    confidence_contribution: number
}

interface TimelineEntry {
    ts: string
    label: string
    detail: string
    phase: string
}

interface Signal {
    symbol: string
    label: string
    asset_class: string
    category: string
    sector: string
    region: string
    description: string
    geo_sensitivity: string[]
    action: 'BUY' | 'SELL' | 'HOLD'
    confidence_pct: number
    uncertainty_pct: number
    time_horizon: string
    bullish_strength: number
    bearish_strength: number
    volatility_label: string
    vol_spike_prob: number
    trade_setup: TradeSetup
    reliability: Reliability
    triggering_event: { id: string; title: string; category: string; severity: number; ts: string }
    reasoning_summary: string
    reasoning_chain: ReasoningStep[]
    event_timeline: TimelineEntry[]
    related_assets: string[]
    generated_at: string
}

// ── Fallback data (used when backend is offline) ──────────────────────────────

const FALLBACK_SIGNALS: Signal[] = [
    {
        symbol: 'XAUUSD', label: 'Gold', asset_class: 'commodity', category: 'Commodities',
        sector: 'metals', region: 'global', description: 'Safe-haven precious metal',
        geo_sensitivity: ['military_escalation', 'sanctions'],
        action: 'BUY', confidence_pct: 88, uncertainty_pct: 12, time_horizon: 'short-term',
        bullish_strength: 0.74, bearish_strength: 0.08, volatility_label: 'MEDIUM',
        vol_spike_prob: 0.81,
        trade_setup: { current_price: 2341, entry_price: 2341, stop_loss: 2298, target_price: 2427, risk_reward: 2.0, atr_pct: 1.84, max_position_pct: 3.2 },
        reliability: { historical_accuracy: 0.68, win_rate: 0.62, sharpe_ratio: 1.42, max_drawdown: 0.12 },
        triggering_event: { id: 'e1', title: 'Iran-Israel Escalation — Missile Exchanges', category: 'military_escalation', severity: 0.92, ts: new Date(Date.now() - 7200000).toISOString() },
        reasoning_summary: 'BUY Gold — safe-haven demand surge driven by military escalation in Middle East. Confidence 88%.',
        reasoning_chain: [
            { step: 1, label: 'Event Detected', description: 'Military escalation detected in Middle East', evidence: 'Severity 92% · Iran-Israel Missile Exchanges', phase: 'event', confidence_contribution: 0.35 },
            { step: 2, label: 'Economic Impact', description: 'Safe-haven demand surge triggered', evidence: 'Historical: GTI >75 → Gold rallies avg 4.6% in 24h', phase: 'economic_impact', confidence_contribution: 0.28 },
            { step: 3, label: 'Market Mechanism', description: 'Institutional flight to safety driving bid', evidence: 'Options IV elevated; CDS spreads widening', phase: 'mechanism', confidence_contribution: 0.22 },
            { step: 4, label: 'Asset Movement', description: 'BUY Gold — documented safe-haven correlation', evidence: 'Geo-sensitivity confirmed for military events', phase: 'movement', confidence_contribution: 0.15 },
        ],
        event_timeline: [
            { ts: new Date(Date.now() - 7200000).toISOString(), label: 'Event Detected', detail: 'Iran-Israel Escalation — Missile Exchanges', phase: 'event' },
            { ts: new Date(Date.now() - 7080000).toISOString(), label: 'NLP Classification', detail: 'Category: military escalation · Severity: 92%', phase: 'nlp' },
            { ts: new Date(Date.now() - 6840000).toISOString(), label: 'BUY Signal Generated', detail: 'Gold BUY · Confidence: 88%', phase: 'signal' },
            { ts: new Date(Date.now() - 5400000).toISOString(), label: 'Market Reaction', detail: 'Gold +2.4% (est.)', phase: 'reaction' },
        ],
        related_assets: ['XAGUSD', 'GLD', 'TLT'],
        generated_at: new Date().toISOString(),
    },
    {
        symbol: 'WTI', label: 'WTI Crude Oil', asset_class: 'commodity', category: 'Commodities',
        sector: 'energy', region: 'middle_east', description: 'West Texas Intermediate crude',
        geo_sensitivity: ['energy_supply_disruption', 'military_escalation'],
        action: 'BUY', confidence_pct: 82, uncertainty_pct: 18, time_horizon: 'short-term',
        bullish_strength: 0.70, bearish_strength: 0.10, volatility_label: 'HIGH',
        vol_spike_prob: 0.75,
        trade_setup: { current_price: 83.4, entry_price: 83.4, stop_loss: 80.1, target_price: 90.3, risk_reward: 2.1, atr_pct: 3.96, max_position_pct: 2.8 },
        reliability: { historical_accuracy: 0.71, win_rate: 0.65, sharpe_ratio: 1.55, max_drawdown: 0.14 },
        triggering_event: { id: 'e1', title: 'Iran-Israel Escalation — Strait of Hormuz Risk', category: 'military_escalation', severity: 0.92, ts: new Date(Date.now() - 7200000).toISOString() },
        reasoning_summary: 'BUY WTI Oil — Hormuz strait disruption risk from Middle East escalation. Confidence 82%.',
        reasoning_chain: [
            { step: 1, label: 'Event Detected', description: 'Military conflict detected near Strait of Hormuz', evidence: 'Severity 92% · Iran-Israel exchange', phase: 'event', confidence_contribution: 0.38 },
            { step: 2, label: 'Economic Impact', description: 'Supply reduction threatens 20% of global oil flow', evidence: 'Hormuz route carries ~18M bbl/day', phase: 'economic_impact', confidence_contribution: 0.30 },
            { step: 3, label: 'Market Mechanism', description: 'Spot market premium expansion; futures backwardation', evidence: 'Backwardation detected in front-month contracts', phase: 'mechanism', confidence_contribution: 0.20 },
            { step: 4, label: 'Asset Movement', description: 'BUY WTI — energy sector outperforms in supply crises', evidence: 'WTI+BRENT confirmed sensitivity to ME conflicts', phase: 'movement', confidence_contribution: 0.12 },
        ],
        event_timeline: [
            { ts: new Date(Date.now() - 7200000).toISOString(), label: 'Event Detected', detail: 'Missile exchanges near Hormuz Strait', phase: 'event' },
            { ts: new Date(Date.now() - 7080000).toISOString(), label: 'NLP Classification', detail: 'Energy supply disruption · Severity 92%', phase: 'nlp' },
            { ts: new Date(Date.now() - 6720000).toISOString(), label: 'BUY Signal Generated', detail: 'WTI BUY · Confidence 82%', phase: 'signal' },
            { ts: new Date(Date.now() - 4800000).toISOString(), label: 'Market Reaction', detail: 'WTI +3.8% (est.)', phase: 'reaction' },
        ],
        related_assets: ['BRENT', 'XLE', 'XOM', 'CVX'],
        generated_at: new Date().toISOString(),
    },
    {
        symbol: 'LMT', label: 'Lockheed Martin', asset_class: 'stock', category: 'Stocks',
        sector: 'defense', region: 'americas', description: 'Defense prime contractor',
        geo_sensitivity: ['military_escalation', 'nuclear_threat'],
        action: 'BUY', confidence_pct: 85, uncertainty_pct: 15, time_horizon: 'medium-term',
        bullish_strength: 0.72, bearish_strength: 0.05, volatility_label: 'MEDIUM',
        vol_spike_prob: 0.78,
        trade_setup: { current_price: 472.5, entry_price: 472.5, stop_loss: 454.2, target_price: 509.1, risk_reward: 2.0, atr_pct: 1.94, max_position_pct: 2.5 },
        reliability: { historical_accuracy: 0.65, win_rate: 0.60, sharpe_ratio: 1.28, max_drawdown: 0.13 },
        triggering_event: { id: 'e1', title: 'Iran-Israel Escalation — NATO Defense Posture', category: 'military_escalation', severity: 0.92, ts: new Date(Date.now() - 7200000).toISOString() },
        reasoning_summary: 'BUY LMT — defense spending surge expected from Middle East escalation. Confidence 85%.',
        reasoning_chain: [
            { step: 1, label: 'Event Detected', description: 'Regional military conflict escalation detected', evidence: 'Severity 92% · Missile exchange reported', phase: 'event', confidence_contribution: 0.35 },
            { step: 2, label: 'Economic Impact', description: 'Defense procurement acceleration expected', evidence: 'Historical: conflicts → 12-18% defense budget uplift', phase: 'economic_impact', confidence_contribution: 0.30 },
            { step: 3, label: 'Market Mechanism', description: 'Government contracts + emergency appropriations', evidence: 'F-35 contract pipeline + THAAD demand', phase: 'mechanism', confidence_contribution: 0.22 },
            { step: 4, label: 'Asset Movement', description: 'BUY LMT — primary missile defense contractor', evidence: 'ITA ETF basket confirmed sensitivity', phase: 'movement', confidence_contribution: 0.13 },
        ],
        event_timeline: [
            { ts: new Date(Date.now() - 7200000).toISOString(), label: 'Event Detected', detail: 'Military escalation — NATO posture shift', phase: 'event' },
            { ts: new Date(Date.now() - 7020000).toISOString(), label: 'NLP Classification', detail: 'Military escalation · Severity 92%', phase: 'nlp' },
            { ts: new Date(Date.now() - 6600000).toISOString(), label: 'BUY Signal Generated', detail: 'LMT BUY · Confidence 85%', phase: 'signal' },
            { ts: new Date(Date.now() - 4200000).toISOString(), label: 'Market Reaction', detail: 'LMT +2.1% (est.)', phase: 'reaction' },
        ],
        related_assets: ['RTX', 'NOC', 'GD', 'ITA'],
        generated_at: new Date().toISOString(),
    },
    {
        symbol: 'SPX', label: 'S&P 500', asset_class: 'equity_index', category: 'Equity Indices',
        sector: 'broad_equity', region: 'americas', description: 'US large-cap benchmark',
        geo_sensitivity: ['military_escalation', 'political_instability'],
        action: 'SELL', confidence_pct: 68, uncertainty_pct: 32, time_horizon: 'short-term',
        bullish_strength: 0.05, bearish_strength: 0.55, volatility_label: 'HIGH',
        vol_spike_prob: 0.62,
        trade_setup: { current_price: 5198, entry_price: 5198, stop_loss: 5291, target_price: 5012, risk_reward: 2.0, atr_pct: 1.79, max_position_pct: 1.8 },
        reliability: { historical_accuracy: 0.61, win_rate: 0.57, sharpe_ratio: 1.10, max_drawdown: 0.18 },
        triggering_event: { id: 'e1', title: 'Iran-Israel Escalation — Risk-Off Sentiment', category: 'military_escalation', severity: 0.92, ts: new Date(Date.now() - 7200000).toISOString() },
        reasoning_summary: 'SELL S&P 500 — geopolitical risk-off rotation from equities to safe havens. Confidence 68%.',
        reasoning_chain: [
            { step: 1, label: 'Event Detected', description: 'Major geopolitical conflict escalation', evidence: 'Severity 92% · Middle East missile exchanges', phase: 'event', confidence_contribution: 0.32 },
            { step: 2, label: 'Economic Impact', description: 'Global risk appetite deterioration', evidence: 'VIX historically spikes 30-50% on ME conflicts', phase: 'economic_impact', confidence_contribution: 0.28 },
            { step: 3, label: 'Market Mechanism', description: 'Portfolio de-risking; margin calls on leveraged positions', evidence: 'Institutional put buying elevated; vol surface steepening', phase: 'mechanism', confidence_contribution: 0.25 },
            { step: 4, label: 'Asset Movement', description: 'SELL SPX — equity risk premium repricing', evidence: 'Inverse correlation with GTI confirmed', phase: 'movement', confidence_contribution: 0.15 },
        ],
        event_timeline: [
            { ts: new Date(Date.now() - 7200000).toISOString(), label: 'Event Detected', detail: 'Risk-off trigger — military escalation', phase: 'event' },
            { ts: new Date(Date.now() - 7140000).toISOString(), label: 'NLP Classification', detail: 'Military escalation · Severity 92%', phase: 'nlp' },
            { ts: new Date(Date.now() - 6960000).toISOString(), label: 'SELL Signal Generated', detail: 'S&P 500 SELL · Confidence 68%', phase: 'signal' },
            { ts: new Date(Date.now() - 5100000).toISOString(), label: 'Market Reaction', detail: 'SPX -1.8% (est.)', phase: 'reaction' },
        ],
        related_assets: ['NDX', 'DJI', 'DAX'],
        generated_at: new Date().toISOString(),
    },
    {
        symbol: 'EURUSD', label: 'EUR/USD', asset_class: 'forex', category: 'Forex',
        sector: 'currencies', region: 'europe', description: 'Major pair; Russia/ECB sensitive',
        geo_sensitivity: ['sanctions', 'energy_supply_disruption'],
        action: 'SELL', confidence_pct: 72, uncertainty_pct: 28, time_horizon: 'medium-term',
        bullish_strength: 0.08, bearish_strength: 0.61, volatility_label: 'MEDIUM',
        vol_spike_prob: 0.65,
        trade_setup: { current_price: 1.0852, entry_price: 1.0852, stop_loss: 1.0938, target_price: 1.0680, risk_reward: 2.0, atr_pct: 0.79, max_position_pct: 2.2 },
        reliability: { historical_accuracy: 0.64, win_rate: 0.59, sharpe_ratio: 1.25, max_drawdown: 0.09 },
        triggering_event: { id: 'e5', title: 'Russia Natgas Flow to EU Drops 40%', category: 'energy_supply_disruption', severity: 0.80, ts: new Date(Date.now() - 36000000).toISOString() },
        reasoning_summary: 'SELL EUR/USD — energy supply disruption weakens European growth outlook. Confidence 72%.',
        reasoning_chain: [
            { step: 1, label: 'Event Detected', description: 'Russian gas flow to Europe reduced 40%', evidence: 'Severity 80% · Pipeline data confirmed', phase: 'event', confidence_contribution: 0.35 },
            { step: 2, label: 'Economic Impact', description: 'European industrial output and growth outlook deteriorate', evidence: 'Germany manufacturing PMI leading indicator negative', phase: 'economic_impact', confidence_contribution: 0.30 },
            { step: 3, label: 'Market Mechanism', description: 'ECB dovish pivot speculation; EUR risk premium rises', evidence: 'Eurozone growth downgrade priced into rate futures', phase: 'mechanism', confidence_contribution: 0.22 },
            { step: 4, label: 'Asset Movement', description: 'SELL EUR/USD — energy shock → growth drag → currency weakness', evidence: 'Historical: gas supply cut → EUR -2.5% avg in 30 days', phase: 'movement', confidence_contribution: 0.13 },
        ],
        event_timeline: [
            { ts: new Date(Date.now() - 36000000).toISOString(), label: 'Event Detected', detail: 'Russia Natgas Flow to EU -40%', phase: 'event' },
            { ts: new Date(Date.now() - 35880000).toISOString(), label: 'NLP Classification', detail: 'Energy supply disruption · Severity 80%', phase: 'nlp' },
            { ts: new Date(Date.now() - 35280000).toISOString(), label: 'SELL Signal Generated', detail: 'EUR/USD SELL · Confidence 72%', phase: 'signal' },
            { ts: new Date(Date.now() - 28800000).toISOString(), label: 'Market Reaction', detail: 'EUR/USD -0.8% (est.)', phase: 'reaction' },
        ],
        related_assets: ['GBPUSD', 'USDCHF', 'DAX', 'NATGAS'],
        generated_at: new Date().toISOString(),
    },
    {
        symbol: 'BTCUSD', label: 'Bitcoin', asset_class: 'crypto', category: 'Crypto',
        sector: 'digital_assets', region: 'global', description: 'Sanctions/capital flight alternative',
        geo_sensitivity: ['sanctions', 'political_instability'],
        action: 'BUY', confidence_pct: 58, uncertainty_pct: 42, time_horizon: 'medium-term',
        bullish_strength: 0.40, bearish_strength: 0.18, volatility_label: 'EXTREME',
        vol_spike_prob: 0.52,
        trade_setup: { current_price: 68200, entry_price: 68200, stop_loss: 62800, target_price: 79400, risk_reward: 2.07, atr_pct: 7.92, max_position_pct: 1.2 },
        reliability: { historical_accuracy: 0.55, win_rate: 0.51, sharpe_ratio: 0.88, max_drawdown: 0.28 },
        triggering_event: { id: 'e1', title: 'Iran Sanctions — Capital Flight to Alternatives', category: 'sanctions', severity: 0.75, ts: new Date(Date.now() - 14400000).toISOString() },
        reasoning_summary: 'BUY Bitcoin — sanction-driven capital flight to uncensorable assets. Confidence 58% (high uncertainty).',
        reasoning_chain: [
            { step: 1, label: 'Event Detected', description: 'New international sanctions announced', evidence: 'Capital controls risk in affected regions', phase: 'event', confidence_contribution: 0.30 },
            { step: 2, label: 'Economic Impact', description: 'Demand for sanction-resistant assets rises', evidence: 'Historical: SWIFT exclusion → BTC +15% in 30 days', phase: 'economic_impact', confidence_contribution: 0.28 },
            { step: 3, label: 'Market Mechanism', description: 'On-chain volumes in target region spike', evidence: 'P2P premium elevated; stablecoin demand rising', phase: 'mechanism', confidence_contribution: 0.25 },
            { step: 4, label: 'Asset Movement', description: 'BUY BTC — alternative store of value demand', evidence: 'High uncertainty applies — use small position size', phase: 'movement', confidence_contribution: 0.17 },
        ],
        event_timeline: [
            { ts: new Date(Date.now() - 14400000).toISOString(), label: 'Event Detected', detail: 'Iran sanctions — capital flight signals', phase: 'event' },
            { ts: new Date(Date.now() - 14280000).toISOString(), label: 'NLP Classification', detail: 'Sanctions · Severity 75%', phase: 'nlp' },
            { ts: new Date(Date.now() - 13680000).toISOString(), label: 'BUY Signal Generated', detail: 'Bitcoin BUY · Confidence 58%', phase: 'signal' },
            { ts: new Date(Date.now() - 9000000).toISOString(), label: 'Market Reaction', detail: 'BTC +4.2% (est.)', phase: 'reaction' },
        ],
        related_assets: ['ETHUSD', 'XAUUSD'],
        generated_at: new Date().toISOString(),
    },
]

const CATEGORIES = ['All', 'Commodities', 'Equity Indices', 'Forex', 'Crypto', 'Stocks', 'ETFs', 'Bonds']
const ACTIONS = ['All', 'BUY', 'SELL', 'HOLD']

// ── Utility helpers ───────────────────────────────────────────────────────────

function formatPrice(p: number): string {
    if (p >= 10000) return p.toLocaleString('en-US', { maximumFractionDigits: 0 })
    if (p >= 100) return p.toFixed(2)
    if (p >= 1) return p.toFixed(4)
    return p.toFixed(6)
}

function formatPct(v: number): string { return `${(v * 100).toFixed(1)}%` }
function formatTs(iso: string): string {
    const d = new Date(iso)
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function actionColor(action: string) {
    if (action === 'BUY') return 'text-emerald-400 bg-emerald-500/15 border-emerald-500/30'
    if (action === 'SELL') return 'text-red-400 bg-red-500/15 border-red-500/30'
    return 'text-yellow-400 bg-yellow-500/15 border-yellow-500/30'
}

function volColor(label: string) {
    if (label === 'LOW') return 'text-emerald-400'
    if (label === 'MEDIUM') return 'text-yellow-400'
    if (label === 'HIGH') return 'text-orange-400'
    return 'text-red-400'
}

function phaseColor(phase: string) {
    const m: Record<string, string> = {
        event: 'border-red-500 bg-red-500/20 text-red-300',
        nlp: 'border-purple-500 bg-purple-500/20 text-purple-300',
        signal: 'border-white/30 bg-white/10 text-white',
        reaction: 'border-emerald-500 bg-emerald-500/20 text-emerald-300',
        economic_impact: 'border-orange-500 bg-orange-500/20 text-orange-300',
        mechanism: 'border-white/30 bg-white/10 text-white/70',
        movement: 'border-teal-500 bg-teal-500/20 text-teal-300',
    }
    return m[phase] ?? 'border-gray-600 bg-gray-500/20 text-gray-300'
}

// ── Signal Card ───────────────────────────────────────────────────────────────

function SignalCard({
    signal, selected, onClick
}: { signal: Signal; selected: boolean; onClick: () => void }) {
    const isBuy = signal.action === 'BUY'
    const isSell = signal.action === 'SELL'

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            onClick={onClick}
            className={`relative rounded-xl border cursor-pointer transition-all duration-200 p-3.5 ${selected
                ? 'border-white/30 bg-white/8 shadow-[0_0_18px_rgba(255,255,255,0.12)]'
                : 'border-white/8 bg-white/3 hover:border-white/15 hover:bg-white/5'
                }`}
        >
            {/* Action glow strip */}
            <div className={`absolute left-0 top-0 bottom-0 w-0.5 rounded-l-xl ${isBuy ? 'bg-emerald-500' : isSell ? 'bg-red-500' : 'bg-yellow-500'
                }`} />

            <div className="pl-2">
                {/* Header row */}
                <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="min-w-0">
                        <div className="flex items-center gap-2">
                            <span className="text-white font-mono font-bold text-sm">{signal.symbol}</span>
                            <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${actionColor(signal.action)}`}>
                                {signal.action}
                            </span>
                        </div>
                        <div className="text-gray-400 text-[10px] truncate mt-0.5">{signal.label}</div>
                    </div>
                    <div className="text-right shrink-0">
                        <div className="text-white font-mono text-sm font-semibold">
                            {signal.confidence_pct.toFixed(0)}%
                        </div>
                        <div className="text-gray-500 text-[9px]">confidence</div>
                    </div>
                </div>

                {/* Strength bars */}
                <div className="space-y-1 mb-2">
                    <div className="flex items-center gap-2">
                        <span className="text-[9px] text-emerald-400 w-10 shrink-0">Bull</span>
                        <div className="flex-1 h-1 bg-white/8 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-emerald-500 rounded-full transition-all"
                                style={{ width: `${signal.bullish_strength * 100}%` }}
                            />
                        </div>
                        <span className="text-[9px] text-emerald-400 w-7 text-right">{(signal.bullish_strength * 100).toFixed(0)}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-[9px] text-red-400 w-10 shrink-0">Bear</span>
                        <div className="flex-1 h-1 bg-white/8 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-red-500 rounded-full transition-all"
                                style={{ width: `${signal.bearish_strength * 100}%` }}
                            />
                        </div>
                        <span className="text-[9px] text-red-400 w-7 text-right">{(signal.bearish_strength * 100).toFixed(0)}%</span>
                    </div>
                </div>

                {/* Meta chips */}
                <div className="flex items-center gap-1.5 flex-wrap">
                    <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded ${volColor(signal.volatility_label)} bg-white/5`}>
                        VOL: {signal.volatility_label}
                    </span>
                    <span className="text-[8px] text-gray-500 font-mono px-1.5 py-0.5 rounded bg-white/5">
                        {signal.time_horizon}
                    </span>
                    <span className="text-[8px] text-gray-500 font-mono px-1.5 py-0.5 rounded bg-white/5">
                        RR {signal.trade_setup.risk_reward.toFixed(1)}
                    </span>
                </div>

                {/* Triggering event */}
                <div className="mt-2 text-[9px] text-gray-500 truncate">
                    ⚡ {signal.triggering_event.title}
                </div>
            </div>
        </motion.div>
    )
}

// ── Signal Detail Panel ───────────────────────────────────────────────────────

function SignalDetail({ signal }: { signal: Signal }) {
    const [tab, setTab] = useState<'setup' | 'reasoning' | 'timeline' | 'reliability'>('setup')

    const TABS = [
        { id: 'setup', label: 'Trade Setup', icon: Target },
        { id: 'reasoning', label: 'AI Reasoning', icon: Zap },
        { id: 'timeline', label: 'Timeline', icon: Clock },
        { id: 'reliability', label: 'Reliability', icon: Shield },
    ] as const

    const ts = signal.trade_setup
    const rel = signal.reliability
    const risk = Math.abs(ts.entry_price - ts.stop_loss)
    const rewrd = Math.abs(ts.target_price - ts.entry_price)

    return (
        <div className="h-full flex flex-col bg-[#07091a]/80 border-l border-white/30/12 overflow-hidden">
            {/* Header */}
            <div className="shrink-0 p-4 border-b border-white/8">
                <div className="flex items-start justify-between gap-3">
                    <div>
                        <div className="flex items-center gap-3">
                            <span className="text-white font-mono font-bold text-xl">{signal.symbol}</span>
                            <span className={`text-sm font-mono font-bold px-2.5 py-1 rounded-lg border ${actionColor(signal.action)}`}>
                                {signal.action}
                            </span>
                        </div>
                        <div className="text-gray-400 text-xs mt-0.5">{signal.label} · {signal.category}</div>
                        <div className="text-gray-500 text-[10px] mt-1 max-w-xs leading-relaxed">{signal.description}</div>
                    </div>
                    <div className="text-right">
                        <div className="text-white font-mono text-2xl font-bold">{signal.confidence_pct.toFixed(0)}%</div>
                        <div className="text-gray-500 text-[10px]">confidence</div>
                        <div className="text-orange-400 font-mono text-sm mt-1">{signal.uncertainty_pct.toFixed(0)}%</div>
                        <div className="text-gray-500 text-[10px]">uncertainty</div>
                    </div>
                </div>

                {/* Strength meters */}
                <div className="mt-3 grid grid-cols-2 gap-3">
                    <div>
                        <div className="flex items-center justify-between mb-1">
                            <span className="text-[10px] text-emerald-400 font-mono">Bullish Strength</span>
                            <span className="text-[10px] text-emerald-400 font-mono">{(signal.bullish_strength * 100).toFixed(0)}%</span>
                        </div>
                        <div className="h-1.5 bg-white/8 rounded-full overflow-hidden">
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${signal.bullish_strength * 100}%` }}
                                transition={{ duration: 0.6 }}
                                className="h-full bg-gradient-to-r from-emerald-600 to-emerald-400 rounded-full"
                            />
                        </div>
                    </div>
                    <div>
                        <div className="flex items-center justify-between mb-1">
                            <span className="text-[10px] text-red-400 font-mono">Bearish Strength</span>
                            <span className="text-[10px] text-red-400 font-mono">{(signal.bearish_strength * 100).toFixed(0)}%</span>
                        </div>
                        <div className="h-1.5 bg-white/8 rounded-full overflow-hidden">
                            <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${signal.bearish_strength * 100}%` }}
                                transition={{ duration: 0.6 }}
                                className="h-full bg-gradient-to-r from-red-600 to-red-400 rounded-full"
                            />
                        </div>
                    </div>
                </div>

                {/* Meta chips */}
                <div className="mt-3 flex items-center gap-2 flex-wrap">
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${volColor(signal.volatility_label)} bg-white/5 border-current/20`}>
                        {signal.volatility_label} VOLATILITY
                    </span>
                    <span className="text-[10px] text-gray-400 font-mono px-2 py-0.5 rounded bg-white/5">
                        {signal.time_horizon}
                    </span>
                    <span className="text-[10px] text-purple-400 font-mono px-2 py-0.5 rounded bg-white/5">
                        {signal.sector.replace('_', ' ')}
                    </span>
                    <span className="text-[10px] text-gray-500 font-mono px-2 py-0.5 rounded bg-white/5">
                        {signal.region.replace('_', ' ')}
                    </span>
                </div>

                {/* Triggering event */}
                <div className="mt-2 p-2 rounded-lg bg-red-500/8 border border-red-500/20">
                    <div className="text-[9px] text-red-400 font-mono uppercase tracking-wider mb-0.5">Triggering Event</div>
                    <div className="text-[10px] text-gray-200 leading-relaxed">{signal.triggering_event.title}</div>
                    <div className="text-[9px] text-gray-500 mt-0.5">
                        {signal.triggering_event.category.replace(/_/g, ' ')} ·
                        Severity {formatPct(signal.triggering_event.severity)} ·
                        {formatTs(signal.triggering_event.ts)}
                    </div>
                </div>
            </div>

            {/* Tab bar */}
            <div className="shrink-0 flex border-b border-white/8 bg-black/20">
                {TABS.map(({ id, label, icon: Icon }) => (
                    <button
                        key={id}
                        onClick={() => setTab(id as any)}
                        className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[10px] font-mono font-semibold uppercase tracking-wide transition-colors ${tab === id
                            ? 'text-white border-b-2 border-white/30 bg-white/3'
                            : 'text-gray-500 hover:text-gray-300'
                            }`}
                    >
                        <Icon className="h-3 w-3" />
                        <span className="hidden sm:inline">{label}</span>
                    </button>
                ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/10">
                <AnimatePresence mode="wait">
                    {tab === 'setup' && (
                        <motion.div key="setup" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                            <div className="text-[10px] text-gray-500 font-mono uppercase tracking-widest mb-3">Trade Structure</div>

                            {/* Price table */}
                            <div className="grid grid-cols-2 gap-2 mb-4">
                                {[
                                    { label: 'Current Price', value: formatPrice(ts.current_price), color: 'text-gray-200' },
                                    { label: 'Entry', value: formatPrice(ts.entry_price), color: 'text-white' },
                                    { label: 'Stop Loss', value: formatPrice(ts.stop_loss), color: 'text-red-400' },
                                    { label: 'Target', value: formatPrice(ts.target_price), color: 'text-emerald-400' },
                                ].map(({ label, value, color }) => (
                                    <div key={label} className="p-2.5 rounded-lg bg-white/3 border border-white/8">
                                        <div className="text-[9px] text-gray-500 font-mono uppercase mb-1">{label}</div>
                                        <div className={`font-mono font-bold text-sm ${color}`}>{value}</div>
                                    </div>
                                ))}
                            </div>

                            {/* R:R + metrics */}
                            <div className="grid grid-cols-3 gap-2 mb-4">
                                <div className="p-2.5 rounded-lg bg-white/3 border border-white/8 col-span-1">
                                    <div className="text-[9px] text-gray-500 font-mono uppercase mb-1">Risk/Reward</div>
                                    <div className="text-white font-mono font-bold text-lg">{ts.risk_reward.toFixed(2)}×</div>
                                </div>
                                <div className="p-2.5 rounded-lg bg-white/3 border border-white/8">
                                    <div className="text-[9px] text-gray-500 font-mono uppercase mb-1">ATR (daily)</div>
                                    <div className="text-orange-400 font-mono font-bold text-sm">{ts.atr_pct.toFixed(2)}%</div>
                                </div>
                                <div className="p-2.5 rounded-lg bg-white/3 border border-white/8">
                                    <div className="text-[9px] text-gray-500 font-mono uppercase mb-1">Max Pos.</div>
                                    <div className="text-purple-400 font-mono font-bold text-sm">{ts.max_position_pct.toFixed(1)}%</div>
                                </div>
                            </div>

                            {/* Risk visualization */}
                            <div className="p-3 rounded-lg bg-white/3 border border-white/8">
                                <div className="text-[9px] text-gray-500 font-mono uppercase mb-2">Risk vs Reward</div>
                                <div className="flex items-center gap-2 text-[10px]">
                                    <span className="text-red-400 font-mono">Risk: {formatPrice(risk)}</span>
                                    <div className="flex-1 flex h-3 rounded overflow-hidden">
                                        <div className="bg-red-500/50" style={{ width: `${100 / (ts.risk_reward + 1)}%` }} />
                                        <div className="bg-emerald-500/50 flex-1" />
                                    </div>
                                    <span className="text-emerald-400 font-mono">+{formatPrice(rewrd)}</span>
                                </div>
                            </div>

                            {/* Warning */}
                            <div className="mt-3 p-2.5 rounded-lg bg-amber-500/8 border border-amber-500/20 flex gap-2">
                                <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
                                <p className="text-[9px] text-amber-200/70 leading-relaxed">
                                    Educational purposes only. Not financial advice. Always perform your own due diligence.
                                    Model v1.0 · Data as of {new Date(signal.generated_at).toLocaleTimeString()}
                                </p>
                            </div>
                        </motion.div>
                    )}

                    {tab === 'reasoning' && (
                        <motion.div key="reasoning" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                            <div className="text-[10px] text-gray-500 font-mono uppercase tracking-widest mb-3">Causal Reasoning Chain</div>
                            <p className="text-[10px] text-gray-400 leading-relaxed mb-4 p-2.5 rounded-lg bg-white/3 border border-white/8">
                                {signal.reasoning_summary}
                            </p>

                            <div className="space-y-3">
                                {signal.reasoning_chain.map((step, i) => (
                                    <div key={i} className="flex gap-3">
                                        <div className="flex flex-col items-center">
                                            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-mono font-bold border shrink-0 ${phaseColor(step.phase)}`}>
                                                {step.step}
                                            </div>
                                            {i < signal.reasoning_chain.length - 1 && (
                                                <div className="w-px flex-1 bg-white/10 my-1" />
                                            )}
                                        </div>
                                        <div className="flex-1 pb-3">
                                            <div className="text-[10px] text-gray-200 font-semibold mb-0.5">{step.label}</div>
                                            <div className="text-[10px] text-gray-300 leading-relaxed mb-1">{step.description}</div>
                                            <div className="text-[9px] text-gray-500 italic">{step.evidence}</div>
                                            <div className="mt-1.5 flex items-center gap-1">
                                                <span className="text-[8px] text-gray-600 font-mono">contribution:</span>
                                                <div className="flex-1 h-0.5 bg-white/8 rounded-full max-w-[60px]">
                                                    <div className="h-full bg-white/60 rounded-full" style={{ width: `${step.confidence_contribution * 100 * 2.5}%` }} />
                                                </div>
                                                <span className="text-[8px] text-white/70 font-mono">{(step.confidence_contribution * 100).toFixed(0)}%</span>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {signal.related_assets.length > 0 && (
                                <div className="mt-4">
                                    <div className="text-[9px] text-gray-500 font-mono uppercase mb-2">Related Assets</div>
                                    <div className="flex gap-1.5 flex-wrap">
                                        {signal.related_assets.map(sym => (
                                            <span key={sym} className="text-[9px] font-mono text-gray-400 px-2 py-0.5 rounded bg-white/5 border border-white/10">
                                                {sym}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </motion.div>
                    )}

                    {tab === 'timeline' && (
                        <motion.div key="timeline" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                            <div className="text-[10px] text-gray-500 font-mono uppercase tracking-widest mb-3">Event → Market Reaction</div>
                            <div className="space-y-0">
                                {signal.event_timeline.map((entry, i) => (
                                    <div key={i} className="flex gap-3">
                                        <div className="flex flex-col items-center">
                                            <div className={`w-2.5 h-2.5 rounded-full shrink-0 mt-0.5 border ${phaseColor(entry.phase).replace('text-', 'border-').replace('bg-', '').split(' ')[0]}`}
                                                style={{ background: 'currentColor' }} />
                                            {i < signal.event_timeline.length - 1 && (
                                                <div className="w-px flex-1 bg-white/10 my-1 min-h-[20px]" />
                                            )}
                                        </div>
                                        <div className="pb-4 flex-1">
                                            <div className="flex items-center gap-2 mb-0.5">
                                                <span className="text-[9px] text-gray-500 font-mono">{formatTs(entry.ts)}</span>
                                                <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded-full border ${phaseColor(entry.phase)}`}>
                                                    {entry.phase.replace('_', ' ').toUpperCase()}
                                                </span>
                                            </div>
                                            <div className="text-[10px] text-gray-200 font-semibold">{entry.label}</div>
                                            <div className="text-[9px] text-gray-400 mt-0.5">{entry.detail}</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </motion.div>
                    )}

                    {tab === 'reliability' && (
                        <motion.div key="reliability" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                            <div className="text-[10px] text-gray-500 font-mono uppercase tracking-widest mb-3">Historical Performance</div>

                            <div className="grid grid-cols-2 gap-3 mb-4">
                                {[
                                    { label: 'Signal Accuracy', value: formatPct(rel.historical_accuracy), sub: 'directional calls', color: 'text-emerald-400' },
                                    { label: 'Win Rate', value: formatPct(rel.win_rate), sub: 'profitable trades', color: 'text-white' },
                                    { label: 'Sharpe Ratio', value: rel.sharpe_ratio.toFixed(2), sub: 'risk-adjusted return', color: 'text-white/70' },
                                    { label: 'Max Drawdown', value: formatPct(rel.max_drawdown), sub: 'peak-to-trough', color: 'text-red-400' },
                                ].map(({ label, value, sub, color }) => (
                                    <div key={label} className="p-3 rounded-lg bg-white/3 border border-white/8">
                                        <div className="text-[9px] text-gray-500 font-mono uppercase mb-1">{label}</div>
                                        <div className={`font-mono font-bold text-lg ${color}`}>{value}</div>
                                        <div className="text-[8px] text-gray-600 mt-0.5">{sub}</div>
                                    </div>
                                ))}
                            </div>

                            {/* Visual accuracy bar */}
                            <div className="p-3 rounded-lg bg-white/3 border border-white/8">
                                <div className="text-[9px] text-gray-500 font-mono uppercase mb-2">Signal Reliability Score</div>
                                <div className="flex items-center gap-2">
                                    <div className="flex-1 h-2 bg-white/8 rounded-full overflow-hidden">
                                        <motion.div
                                            initial={{ width: 0 }}
                                            animate={{ width: `${rel.historical_accuracy * 100}%` }}
                                            transition={{ duration: 0.8 }}
                                            className="h-full bg-gradient-to-r from-white to-emerald-500 rounded-full"
                                        />
                                    </div>
                                    <span className="text-[10px] text-emerald-400 font-mono">{formatPct(rel.historical_accuracy)}</span>
                                </div>
                            </div>

                            <div className="mt-3 p-2.5 rounded-lg bg-white/5 border border-white/15">
                                <div className="text-[9px] text-white/50 leading-relaxed">
                                    Performance metrics derived from backtesting engine using historical geopolitical events.
                                    Past performance does not guarantee future results.
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    )
}

// ── Main Component ────────────────────────────────────────────────────────────

// ── Filter Sidebar (shared between desktop and mobile drawer) ─────────────────

function FilterSidebar({
    selectedCategory, setSelectedCategory,
    selectedAction, setSelectedAction,
    onClose,
}: {
    selectedCategory: string
    setSelectedCategory: (c: string) => void
    selectedAction: string
    setSelectedAction: (a: string) => void
    onClose?: () => void
}) {
    return (
        <div className="flex flex-col h-full overflow-y-auto bg-[#07091a]/95 border-r border-white/8">
            {/* Mobile drawer header */}
            {onClose && (
                <div className="flex items-center justify-between px-4 py-3 border-b border-white/8 shrink-0">
                    <span className="text-[10px] text-gray-500 font-mono uppercase tracking-widest">Filters</span>
                    <button
                        onClick={onClose}
                        className="flex items-center justify-center w-9 h-9 rounded-lg border border-white/10 text-gray-500 hover:text-gray-200 transition-colors"
                        style={{ minHeight: 'unset' }}
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
            )}

            <div className="p-3 border-b border-white/8">
                <div className="text-[9px] text-gray-600 font-mono uppercase tracking-widest mb-2">Asset Class</div>
                <div className="space-y-0.5">
                    {CATEGORIES.map(cat => (
                        <button
                            key={cat}
                            onClick={() => { setSelectedCategory(cat); onClose?.() }}
                            className={`w-full text-left px-2.5 py-2 rounded-lg text-[10px] font-mono transition-colors ${selectedCategory === cat
                                ? 'bg-white/8 text-white border border-white/15'
                                : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                                }`}
                            style={{ minHeight: '40px' }}
                        >
                            {cat}
                        </button>
                    ))}
                </div>
            </div>

            <div className="p-3 border-b border-white/8">
                <div className="text-[9px] text-gray-600 font-mono uppercase tracking-widest mb-2">Direction</div>
                <div className="space-y-0.5">
                    {ACTIONS.map(act => (
                        <button
                            key={act}
                            onClick={() => { setSelectedAction(act); onClose?.() }}
                            className={`w-full text-left px-2.5 py-2 rounded-lg text-[10px] font-mono transition-colors flex items-center gap-2 ${selectedAction === act
                                ? 'bg-white/8 text-white border border-white/15'
                                : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                                }`}
                            style={{ minHeight: '40px' }}
                        >
                            {act === 'BUY' && <TrendingUp className="h-3 w-3 text-emerald-400" />}
                            {act === 'SELL' && <TrendingDown className="h-3 w-3 text-red-400" />}
                            {act === 'HOLD' && <Minus className="h-3 w-3 text-yellow-400" />}
                            {act === 'All' && <BarChart2 className="h-3 w-3 text-gray-500" />}
                            {act}
                        </button>
                    ))}
                </div>
            </div>

            <div className="p-3">
                <div className="text-[9px] text-gray-600 font-mono uppercase tracking-widest mb-2">Geo Sensitivity</div>
                <div className="space-y-0.5">
                    {['military_escalation', 'energy_supply_disruption', 'trade_restrictions', 'sanctions', 'political_instability'].map(tag => (
                        <div key={tag} className="text-[8px] text-gray-600 font-mono px-2 py-1 rounded bg-white/3 leading-tight">
                            {tag.replace(/_/g, ' ')}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function TradingCharts() {
    const [signals, setSignals] = useState<Signal[]>(FALLBACK_SIGNALS)
    const [loading, setLoading] = useState(false)
    const [selectedCategory, setSelectedCategory] = useState('All')
    const [selectedAction, setSelectedAction] = useState('All')
    const [selectedSignal, setSelectedSignal] = useState<Signal | null>(FALLBACK_SIGNALS[0])
    const [searchQuery, setSearchQuery] = useState('')
    const [lastRefresh, setLastRefresh] = useState(new Date())

    // Mobile-specific state
    // 'list' = signal cards view, 'detail' = signal detail view, 'filters' = filter drawer
    const [mobileView, setMobileView] = useState<'list' | 'detail'>('list')
    const [mobileFilterOpen, setMobileFilterOpen] = useState(false)

    const fetchSignals = useCallback(async () => {
        setLoading(true)
        try {
            const data = await api.getSignalsV2({ limit: 100 })
            if (data?.signals?.length) {
                setSignals(data.signals as Signal[])
                if (!selectedSignal) setSelectedSignal(data.signals[0])
            }
        } catch {
            // keep fallback data
        } finally {
            setLoading(false)
            setLastRefresh(new Date())
        }
    }, [])

    useEffect(() => {
        fetchSignals()
        const interval = setInterval(fetchSignals, 60_000)
        return () => clearInterval(interval)
    }, [fetchSignals])

    // Filtered signals
    const filtered = signals.filter(s => {
        const catMatch = selectedCategory === 'All' || s.category === selectedCategory || s.asset_class === selectedCategory.toLowerCase()
        const actMatch = selectedAction === 'All' || s.action === selectedAction
        const q = searchQuery.toLowerCase()
        const qMatch = !q || s.symbol.toLowerCase().includes(q) || s.label.toLowerCase().includes(q) || s.sector.toLowerCase().includes(q)
        return catMatch && actMatch && qMatch
    })

    const buyCount = filtered.filter(s => s.action === 'BUY').length
    const sellCount = filtered.filter(s => s.action === 'SELL').length
    const holdCount = filtered.filter(s => s.action === 'HOLD').length

    function handleSignalSelect(sig: Signal) {
        setSelectedSignal(sig)
        setMobileView('detail')
    }

    return (
        <div className="absolute inset-0 flex flex-col bg-[#030610] overflow-hidden">
            {/* Top status bar */}
            <div className="shrink-0 flex items-center justify-between px-3 sm:px-4 py-2 bg-[#07091a]/90 border-b border-white/30/12 min-h-[48px]">
                <div className="flex items-center gap-2 sm:gap-4">
                    <div className="flex items-center gap-1.5">
                        <Activity className="h-3.5 w-3.5 text-white" />
                        <span className="text-white font-mono text-xs font-semibold uppercase tracking-wider">
                            <span className="hidden sm:inline">AI Trading </span>Signals
                        </span>
                    </div>
                    <div className="flex items-center gap-2 sm:gap-3 text-[10px] font-mono">
                        <span className="text-emerald-400">{buyCount} BUY</span>
                        <span className="text-red-400">{sellCount} SELL</span>
                        <span className="hidden sm:inline text-yellow-400">{holdCount} HOLD</span>
                        <span className="hidden sm:inline text-gray-600">of {filtered.length}</span>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <span className="hidden sm:inline text-[9px] text-gray-600 font-mono">
                        Updated {lastRefresh.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
                    </span>
                    <button
                        onClick={fetchSignals}
                        disabled={loading}
                        className="flex items-center justify-center w-9 h-9 rounded-lg bg-white/4 border border-white/8 hover:border-white/20 transition-colors"
                        title="Refresh signals"
                        style={{ minHeight: 'unset' }}
                    >
                        <RefreshCw className={`h-3 w-3 text-gray-400 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            {/* ── MOBILE: Filter backdrop ── */}
            <AnimatePresence>
                {mobileFilterOpen && (
                    <motion.div
                        key="filter-backdrop"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="lg:hidden fixed inset-0 z-40 bg-black/60"
                        onClick={() => setMobileFilterOpen(false)}
                    />
                )}
            </AnimatePresence>

            {/* ── MOBILE: Filter drawer ── */}
            <AnimatePresence>
                {mobileFilterOpen && (
                    <motion.div
                        key="filter-drawer"
                        initial={{ x: '-100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '-100%' }}
                        transition={{ type: 'spring', stiffness: 280, damping: 30 }}
                        className="lg:hidden fixed top-0 left-0 bottom-0 w-[75vw] max-w-[280px] z-50"
                    >
                        <FilterSidebar
                            selectedCategory={selectedCategory}
                            setSelectedCategory={setSelectedCategory}
                            selectedAction={selectedAction}
                            setSelectedAction={setSelectedAction}
                            onClose={() => setMobileFilterOpen(false)}
                        />
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── DESKTOP / TABLET: 3-column layout ── */}
            <div className="hidden lg:flex flex-1 overflow-hidden">
                {/* LEFT: Category + Action filters */}
                <div className="w-44 shrink-0 flex flex-col border-r border-white/8 bg-[#07091a]/50 overflow-y-auto">
                    <FilterSidebar
                        selectedCategory={selectedCategory}
                        setSelectedCategory={setSelectedCategory}
                        selectedAction={selectedAction}
                        setSelectedAction={setSelectedAction}
                    />
                </div>

                {/* CENTER: Signal card list */}
                <div className="w-72 shrink-0 flex flex-col border-r border-white/8 overflow-hidden">
                    {/* Search */}
                    <div className="shrink-0 p-2.5 border-b border-white/8">
                        <div className="flex items-center gap-2 bg-white/5 rounded-lg px-2.5 py-1.5 border border-white/8" style={{ minHeight: '40px' }}>
                            <Filter className="h-3 w-3 text-gray-500 shrink-0" />
                            <input
                                type="text"
                                placeholder="Search asset..."
                                value={searchQuery}
                                onChange={e => setSearchQuery(e.target.value)}
                                className="flex-1 bg-transparent text-[10px] font-mono text-gray-300 placeholder-gray-600 outline-none min-w-0"
                                style={{ minHeight: 'unset' }}
                            />
                            {searchQuery && (
                                <button onClick={() => setSearchQuery('')} style={{ minHeight: 'unset' }}>
                                    <X className="h-3 w-3 text-gray-500 hover:text-gray-300" />
                                </button>
                            )}
                        </div>
                    </div>
                    {/* Cards */}
                    <div className="flex-1 overflow-y-auto p-2.5 space-y-2">
                        {loading && signals.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full gap-3">
                                <RefreshCw className="h-5 w-5 text-white/50 animate-spin" />
                                <span className="text-[10px] text-gray-600 font-mono">Loading signals...</span>
                            </div>
                        ) : filtered.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-full gap-2">
                                <Info className="h-5 w-5 text-gray-600" />
                                <span className="text-[10px] text-gray-600 font-mono">No signals match filter</span>
                            </div>
                        ) : (
                            <AnimatePresence>
                                {filtered.map(sig => (
                                    <SignalCard
                                        key={sig.symbol}
                                        signal={sig}
                                        selected={selectedSignal?.symbol === sig.symbol}
                                        onClick={() => setSelectedSignal(sig)}
                                    />
                                ))}
                            </AnimatePresence>
                        )}
                    </div>
                </div>

                {/* RIGHT: Signal detail */}
                <div className="flex-1 overflow-hidden">
                    <AnimatePresence mode="wait">
                        {selectedSignal ? (
                            <motion.div
                                key={selectedSignal.symbol}
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -10 }}
                                transition={{ duration: 0.2 }}
                                className="h-full"
                            >
                                <SignalDetail signal={selectedSignal} />
                            </motion.div>
                        ) : (
                            <motion.div
                                key="empty"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="h-full flex flex-col items-center justify-center gap-3"
                            >
                                <BarChart2 className="h-8 w-8 text-gray-700" />
                                <span className="text-[11px] text-gray-600 font-mono">Select a signal to view details</span>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            {/* ── MOBILE / TABLET: Single-panel navigation ── */}
            <div className="flex lg:hidden flex-1 flex-col overflow-hidden">

                {/* Mobile toolbar: filter button + search (list view) or back button (detail view) */}
                <div className="shrink-0 flex items-center gap-2 px-3 py-2 border-b border-white/8 bg-[#07091a]/60">
                    {mobileView === 'list' ? (
                        <>
                            {/* Filter button */}
                            <button
                                onClick={() => setMobileFilterOpen(true)}
                                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-white/12 bg-white/5 text-gray-400 text-[10px] font-mono hover:text-gray-200 transition-colors shrink-0"
                                style={{ minHeight: '44px' }}
                            >
                                <Filter className="h-3.5 w-3.5" />
                                <span>Filter</span>
                                {(selectedCategory !== 'All' || selectedAction !== 'All') && (
                                    <span className="w-1.5 h-1.5 rounded-full bg-white" />
                                )}
                            </button>

                            {/* Search */}
                            <div className="flex-1 flex items-center gap-2 bg-white/5 rounded-lg px-3 border border-white/8" style={{ minHeight: '44px' }}>
                                <Filter className="h-3.5 w-3.5 text-gray-500 shrink-0" />
                                <input
                                    type="text"
                                    placeholder="Search asset..."
                                    value={searchQuery}
                                    onChange={e => setSearchQuery(e.target.value)}
                                    className="flex-1 bg-transparent text-[11px] font-mono text-gray-300 placeholder-gray-600 outline-none min-w-0"
                                    style={{ minHeight: 'unset' }}
                                />
                                {searchQuery && (
                                    <button onClick={() => setSearchQuery('')} style={{ minHeight: 'unset' }}>
                                        <X className="h-3.5 w-3.5 text-gray-500" />
                                    </button>
                                )}
                            </div>

                            {/* Active filter chips */}
                            {selectedCategory !== 'All' && (
                                <button
                                    onClick={() => setSelectedCategory('All')}
                                    className="flex items-center gap-1 px-2 py-1.5 rounded-lg bg-white/8 border border-white/15 text-white text-[9px] font-mono shrink-0"
                                    style={{ minHeight: 'unset' }}
                                >
                                    {selectedCategory} <X className="h-3 w-3" />
                                </button>
                            )}
                        </>
                    ) : (
                        /* Back button in detail view */
                        <button
                            onClick={() => setMobileView('list')}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-white/12 bg-white/5 text-gray-300 text-[11px] font-mono hover:text-white transition-colors"
                            style={{ minHeight: '44px' }}
                        >
                            <ChevronLeft className="h-4 w-4" />
                            <span>All Signals</span>
                        </button>
                    )}
                </div>

                {/* Panel content */}
                <div className="flex-1 overflow-hidden">
                    <AnimatePresence mode="wait">
                        {mobileView === 'list' ? (
                            <motion.div
                                key="mobile-list"
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                transition={{ duration: 0.2 }}
                                className="h-full overflow-y-auto p-3 space-y-2.5"
                            >
                                {loading && signals.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-full gap-3">
                                        <RefreshCw className="h-6 w-6 text-white/50 animate-spin" />
                                        <span className="text-[11px] text-gray-600 font-mono">Loading signals...</span>
                                    </div>
                                ) : filtered.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-full gap-2">
                                        <Info className="h-6 w-6 text-gray-600" />
                                        <span className="text-[11px] text-gray-600 font-mono">No signals match filter</span>
                                    </div>
                                ) : (
                                    <AnimatePresence>
                                        {filtered.map(sig => (
                                            <SignalCard
                                                key={sig.symbol}
                                                signal={sig}
                                                selected={selectedSignal?.symbol === sig.symbol}
                                                onClick={() => handleSignalSelect(sig)}
                                            />
                                        ))}
                                    </AnimatePresence>
                                )}
                            </motion.div>
                        ) : (
                            <motion.div
                                key={`mobile-detail-${selectedSignal?.symbol}`}
                                initial={{ opacity: 0, x: 30 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 20 }}
                                transition={{ duration: 0.22 }}
                                className="h-full overflow-hidden"
                            >
                                {selectedSignal
                                    ? <SignalDetail signal={selectedSignal} />
                                    : (
                                        <div className="h-full flex flex-col items-center justify-center gap-3">
                                            <BarChart2 className="h-8 w-8 text-gray-700" />
                                            <span className="text-[11px] text-gray-600 font-mono">Select a signal to view details</span>
                                        </div>
                                    )
                                }
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            {/* Bottom disclaimer */}
            <div className="shrink-0 flex items-center justify-center px-3 py-1.5 bg-[#07091a]/80 border-t border-white/5">
                <span className="text-[9px] text-gray-600 font-mono text-center">
                    ⚠️ Educational purposes only · Not financial advice · Model v1.0 · Auto-refresh 60s
                </span>
            </div>
        </div>
    )
}
