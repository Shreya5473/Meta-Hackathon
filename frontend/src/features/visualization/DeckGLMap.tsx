import { useState, useEffect, useRef, useMemo } from 'react'
import DeckGL from '@deck.gl/react'
import { GeoJsonLayer } from '@deck.gl/layers'
import Map from 'react-map-gl/maplibre'
import { motion, AnimatePresence } from 'framer-motion'
import { createChart, ColorType } from 'lightweight-charts'
import {
    X, TrendingUp, TrendingDown,
    Globe2, Activity, Layers
} from 'lucide-react'
import { useStore } from '@/shared/state/store'
import { api } from '@/shared/api/client'
import 'maplibre-gl/dist/maplibre-gl.css'

// ── Dark map style ─────────────────────────────────────────────────────────
const MAP_STYLE = {
    version: 8,
    sources: {
        tiles: { type: 'raster', tiles: ['https://basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png'], tileSize: 256 }
    },
    layers: [
        { id: 'bg', type: 'background', paint: { 'background-color': '#03070f' } },
        { id: 'tiles', type: 'raster', source: 'tiles', paint: { 'raster-opacity': 0.45 } }
    ]
}
const INITIAL_VIEW = { longitude: 18, latitude: 28, zoom: 1.5, pitch: 0, bearing: 0 }

function gtiToFill(score: number, selected = false): [number, number, number, number] {
    const a = selected ? 200 : 110
    if (score >= 80) return [239, 68, 68, a]
    if (score >= 60) return [245, 158, 11, a]
    if (score >= 35) return [14, 165, 233, a]
    return [34, 197, 94, Math.round(a * 0.6)]
}

// ── Asset selector tabs ────────────────────────────────────────────────────
const ASSET_META: Record<string, { label: string; category: string; base: number }> = {
    XAUUSD: { label: 'GOLD', category: 'Commodity', base: 2340 },
    USOIL: { label: 'OIL', category: 'Commodity', base: 82 },
    NATGAS: { label: 'GAS', category: 'Commodity', base: 3.2 },
    WHEAT: { label: 'WHEAT', category: 'Commodity', base: 580 },
    CORN: { label: 'CORN', category: 'Commodity', base: 430 },
    SPX: { label: 'S&P500', category: 'Equity', base: 5200 },
    NDX: { label: 'NASDAQ', category: 'Equity', base: 18000 },
    DXY: { label: 'DXY', category: 'Forex', base: 104 },
    COPPER: { label: 'COPPER', category: 'Commodity', base: 4.5 },
    SILVER: { label: 'SILVER', category: 'Commodity', base: 29 },
}

// ── Candlestick chart pane ─────────────────────────────────────────────────
function CandleChart({ data, symbol, changeP }: { data: any[]; symbol: string; changeP: number }) {
    const divRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (!divRef.current || !data.length) return
        const el = divRef.current
        const chart = createChart(el, {
            width: el.clientWidth,
            height: el.clientHeight,
            layout: {
                background: { type: ColorType.Solid, color: 'transparent' },
                textColor: '#64748b',
                fontSize: 10,
                fontFamily: 'monospace',
            },
            grid: {
                vertLines: { color: 'rgba(255,255,255,0.05)' },
                horzLines: { color: 'rgba(255,255,255,0.05)' },
            },
            crosshair: { vertLine: { color: '#00d4ff30' }, horzLine: { color: '#00d4ff30' } },
            rightPriceScale: { borderColor: 'rgba(255,255,255,0.1)', textColor: '#475569' },
            timeScale: { borderColor: 'rgba(255,255,255,0.1)', timeVisible: true },
        })

        const series = chart.addCandlestickSeries({
            upColor: '#22c55e',
            downColor: '#ef4444',
            borderUpColor: '#22c55e',
            borderDownColor: '#ef4444',
            wickUpColor: '#22c55e',
            wickDownColor: '#ef4444',
        })

        const rows = data
            .map((d: any) => ({
                time: Math.floor(new Date(d.ts).getTime() / 1000) as any,
                open: d.open, high: d.high, low: d.low, close: d.close,
            }))
            .sort((a: any, b: any) => a.time - b.time)

        series.setData(rows)
        chart.timeScale().fitContent()

        const obs = new ResizeObserver(() => {
            chart.applyOptions({ width: el.clientWidth, height: el.clientHeight })
        })
        obs.observe(el)

        return () => { obs.disconnect(); chart.remove() }
    }, [data])

    return (
        <div className="flex flex-col h-full">
            {/* Chart header */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/10 shrink-0">
                <div>
                    <span className="text-white font-bold font-mono text-sm">
                        {ASSET_META[symbol]?.label ?? symbol}
                    </span>
                    <span className="text-gray-500 font-mono text-[10px] ml-2">/ {symbol}</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className={`text-lg font-mono font-bold ${changeP >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {changeP >= 0 ? '▲' : '▼'} {Math.abs(changeP).toFixed(2)}%
                    </span>
                    {changeP >= 0
                        ? <TrendingUp className="h-4 w-4 text-green-400" />
                        : <TrendingDown className="h-4 w-4 text-red-400" />
                    }
                </div>
            </div>
            {/* Chart canvas */}
            <div ref={divRef} className="flex-1 min-h-0" />
        </div>
    )
}

// ── Right panel: asset select + chart ─────────────────────────────────────
function AssetChartPanel({ iso, impactData, loading, onClose }: {
    iso: string
    impactData: any
    loading: boolean
    onClose: () => void
}) {
    const availableAssets: string[] = impactData?.quotes?.map((q: any) => q.symbol) ?? []
    const [selected, setSelected] = useState<string | null>(null)

    // auto-select first asset when data loads
    useEffect(() => {
        if (availableAssets.length && !selected) setSelected(availableAssets[0])
    }, [availableAssets.join(',')])

    const quote = impactData?.quotes?.find((q: any) => q.symbol === selected)
    const chart = impactData?.charts?.[selected ?? ''] ?? []
    const sectors = impactData?.sector_exposure ?? {}

    return (
        <div className="flex flex-col h-full bg-[#07091a]/98 border-l border-white/10">
            {/* Country header */}
            <div className="shrink-0 px-4 py-3 border-b border-white/10 flex items-center gap-3">
                <Globe2 className="h-4 w-4 text-white shrink-0" />
                <div className="flex-1 min-w-0">
                    <p className="text-white font-bold font-mono text-sm truncate">
                        {impactData?.name ?? iso} — Market Impact
                    </p>
                    <p className="text-[10px] font-mono text-gray-500">
                        GTI Score: <span className={`font-bold ${(impactData?.gti_score ?? 0) >= 80 ? 'text-red-400' :
                            (impactData?.gti_score ?? 0) >= 60 ? 'text-amber-400' : 'text-white'
                            }`}>{(impactData?.gti_score ?? 0).toFixed(1)}</span>
                        <span className="text-gray-600 ml-2">· Click asset to analyse</span>
                    </p>
                </div>
            </div>

            {loading ? (
                <div className="flex-1 flex items-center justify-center gap-3 flex-col">
                    <div className="w-8 h-8 border-2 border-white/30 border-t-transparent rounded-full animate-spin" />
                    <p className="text-[11px] font-mono text-gray-500">Fetching market data…</p>
                </div>
            ) : (
                <>
                    {/* Asset tabs header — with close button on right */}
                    <div className="shrink-0 px-3 py-2 border-b border-white/10">
                        <div className="flex items-center justify-between mb-2">
                            <p className="text-[9px] font-mono text-gray-600 uppercase tracking-widest flex items-center gap-1">
                                <Layers className="h-3 w-3" /> Select Asset to Analyse
                            </p>
                            <button
                                onClick={onClose}
                                className="flex items-center gap-1 px-2 py-1 rounded-md bg-white/5 border border-white/10 hover:bg-red-500/20 hover:border-red-400/40 transition-all text-gray-500 hover:text-red-300 font-mono text-[9px]"
                                title="Close panel"
                            >
                                <X className="h-3.5 w-3.5" />
                            </button>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                            {availableAssets.map(sym => {
                                const q = impactData?.quotes?.find((x: any) => x.symbol === sym)
                                const isUp = (q?.change_pct ?? 0) >= 0
                                return (
                                    <button
                                        key={sym}
                                        onClick={() => setSelected(sym)}
                                        className={`flex flex-col items-start px-2.5 py-1.5 rounded-lg border text-left transition-all ${selected === sym
                                            ? 'border-white/30 bg-white/5 shadow-[0_0_8px_rgba(255,255,255,0.15)]'
                                            : 'border-white/10 hover:border-white/20 bg-[#0a1020]/60'
                                            }`}
                                    >
                                        <span className="text-[9px] font-mono text-gray-400 uppercase tracking-wider">
                                            {ASSET_META[sym]?.label ?? sym}
                                        </span>
                                        <div className="flex items-center gap-1">
                                            <span className="text-xs font-mono font-bold text-white">
                                                {q?.price?.toFixed(sym === 'NATGAS' || sym === 'COPPER' ? 3 : 1)}
                                            </span>
                                            <span className={`text-[9px] font-mono ${isUp ? 'text-green-400' : 'text-red-400'}`}>
                                                {isUp ? '+' : ''}{q?.change_pct?.toFixed(2)}%
                                            </span>
                                        </div>
                                    </button>
                                )
                            })}
                        </div>
                    </div>

                    {/* Chart — takes remaining height */}
                    <div className="flex-1 min-h-0">
                        {selected && chart.length > 0 ? (
                            <CandleChart data={chart} symbol={selected} changeP={quote?.change_pct ?? 0} />
                        ) : (
                            <div className="h-full flex items-center justify-center">
                                <p className="text-sm font-mono text-gray-600">Select an asset above</p>
                            </div>
                        )}
                    </div>

                    {/* OHLC strip */}
                    {quote && (
                        <div className="shrink-0 grid grid-cols-4 border-t border-white/10">
                            {[
                                { l: 'OPEN', v: quote.open },
                                { l: 'HIGH', v: quote.high },
                                { l: 'LOW', v: quote.low },
                                { l: 'CLOSE', v: quote.price },
                            ].map(({ l, v }) => (
                                <div key={l} className="py-2 text-center border-r border-white/10 last:border-r-0">
                                    <p className="text-[9px] font-mono text-gray-600 uppercase">{l}</p>
                                    <p className="text-xs font-mono text-gray-200 font-bold mt-0.5">
                                        {(v ?? 0).toFixed(2)}
                                    </p>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Sector exposure */}
                    {Object.keys(sectors).length > 0 && (
                        <div className="shrink-0 px-4 py-3 border-t border-white/10">
                            <p className="text-[9px] font-mono text-gray-500 uppercase tracking-widest mb-2 flex items-center gap-1">
                                <Activity className="h-3 w-3" /> Sector Exposure
                            </p>
                            <div className="space-y-1.5">
                                {Object.entries(sectors).slice(0, 4).map(([sector, val]) => (
                                    <div key={sector}>
                                        <div className="flex justify-between text-[9px] font-mono mb-0.5">
                                            <span className="text-gray-400">{sector}</span>
                                            <span className="text-white">{((val as number) * 100).toFixed(0)}%</span>
                                        </div>
                                        <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                                            <motion.div
                                                initial={{ width: 0 }}
                                                animate={{ width: `${(val as number) * 100}%` }}
                                                transition={{ duration: 0.6, ease: 'easeOut' }}
                                                className="h-full rounded-full bg-gradient-to-r from-white to-gray-200"
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Disclaimer */}
                    <div className="shrink-0 px-4 py-2 border-t border-white/10 text-center">
                        <p className="text-[9px] font-mono text-gray-700">
                            Educational only · Not financial advice
                        </p>
                    </div>
                </>
            )}
        </div>
    )
}

// ── Main DeckGLMap ─────────────────────────────────────────────────────────
export function DeckGLMap() {
    const { selectedCountryIso, setSelectedCountryIso, selectedRegions } = useStore()
    const [geojson, setGeojson] = useState<any>(null)
    const [countryData, setCountryData] = useState<any>(null)
    const [selectedIso, setSelectedIso] = useState<string | null>(selectedCountryIso)
    const [impactData, setImpactData] = useState<any>(null)
    const [impactLoading, setImpactLoading] = useState(false)

    // Inherit from globe click
    useEffect(() => {
        if (selectedCountryIso) setSelectedIso(selectedCountryIso)
    }, [selectedCountryIso])

    // Load impact when country changes
    useEffect(() => {
        if (!selectedIso) return
        setImpactLoading(true)
        setImpactData(null)
        api.getCountryMarketImpact(selectedIso).then(d => {
            setImpactData(d)
            setImpactLoading(false)
        })
    }, [selectedIso])

    // GeoJSON
    useEffect(() => {
        fetch('https://raw.githubusercontent.com/vasturiano/react-globe.gl/master/example/datasets/ne_110m_admin_0_countries.geojson')
            .then(r => r.json()).then(setGeojson).catch(() => { })
    }, [])

    // Backend risk
    useEffect(() => {
        api.getGlobeCountries().then(setCountryData)
        const t = setInterval(() => api.getGlobeCountries().then(setCountryData), 30000)
        return () => clearInterval(t)
    }, [])

    const riskLookup = useMemo<Record<string, number>>(() => {
        if (!countryData?.countries) return {}
        return Object.fromEntries(countryData.countries.map((c: any) => [c.iso, c.gti_score]))
    }, [countryData])

    const layers = useMemo(() => {
        if (!geojson) return []

        // Helper: Region matching mapping
        const isCountryInRegion = (iso: string, regions: string[]) => {
            if (regions.length === 0) return true // no filter = show all
            if (!countryData?.countries) return true
            const countryDef = countryData.countries.find((c: any) => c.iso === iso && c.region)
            if (!countryDef) return true // skip filter if we don't have region mapping
            // Note: backend regions might differ slightly from frontend strings, but exact matching works for most
            return regions.some(r => countryDef.region.includes(r) || r.includes(countryDef.region))
        }

        return [new GeoJsonLayer({
            id: 'countries',
            data: geojson,
            pickable: true,
            stroked: true,
            filled: true,
            getFillColor: (d: any) => {
                const iso = d.properties?.ISO_A2 ?? ''
                const score = riskLookup[iso] ?? 20

                // Dim if filtered out
                const inRegion = isCountryInRegion(iso, selectedRegions)
                const [r, g, b, a] = gtiToFill(score, iso === selectedIso)
                return inRegion ? [r, g, b, a] : [r, g, b, Math.max(0, a - 90)] // Dimmer alpha if not in region
            },
            getLineColor: (d: any) => {
                const iso = d.properties?.ISO_A2 ?? ''
                const inRegion = isCountryInRegion(iso, selectedRegions)
                if (iso === selectedIso) return [0, 212, 255, 255]
                return inRegion ? [0, 180, 220, 55] : [0, 180, 220, 15] // Dimmer border
            },
            getLineWidth: (d: any) =>
                (d.properties?.ISO_A2 ?? '') === selectedIso ? 3000 : 800,
            lineWidthMinPixels: 1,
            onClick: (info: any) => {
                const iso = info.object?.properties?.ISO_A2
                if (iso) {
                    setSelectedIso(iso)
                    setSelectedCountryIso(iso)
                }
            },
            updateTriggers: {
                getFillColor: [riskLookup, selectedIso, selectedRegions.join(',')],
                getLineColor: [selectedIso, selectedRegions.join(',')],
                getLineWidth: selectedIso,
            }
        })]
    }, [geojson, riskLookup, selectedIso, setSelectedCountryIso, selectedRegions, countryData])

    // Split widths: 55% map, 45% chart panel
    const showPanel = !!selectedIso

    return (
        <div className="w-full h-full absolute inset-0 flex bg-[#03070f] overflow-hidden">
            {/* ── Map ── */}
            <div className={`relative transition-all duration-500 w-full ${showPanel ? 'md:w-[55%]' : 'md:w-full'}`}>
                <DeckGL
                    initialViewState={INITIAL_VIEW}
                    controller={{ dragRotate: false }}
                    layers={layers}
                    getCursor={() => 'crosshair'}
                >
                    <Map mapStyle={MAP_STYLE as any} />
                </DeckGL>

                {/* Map HUD */}
                <div className="absolute top-[60px] left-3 pointer-events-none z-10 hidden sm:block">
                    <div className="bg-[#07091a]/80 border border-white/15 rounded-lg px-3 py-2 text-[9px] font-mono backdrop-blur-md">
                        <p className="text-gray-500 uppercase tracking-widest mb-1.5">Market Impact Map</p>
                        <div className="flex flex-col gap-1">
                            {[
                                { color: '#ef4444', label: 'Critical ≥80' },
                                { color: '#f59e0b', label: 'High ≥60' },
                                { color: '#0ea5e9', label: 'Medium ≥35' },
                                { color: '#22c55e', label: 'Low <35' },
                            ].map(({ color, label }) => (
                                <div key={label} className="flex items-center gap-2">
                                    <span className="w-2.5 h-2.5 rounded-sm opacity-80 border" style={{ background: color + '60', borderColor: color }} />
                                    <span className="text-gray-400">{label}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {!showPanel && (
                    <div className="absolute bottom-[90px] left-1/2 -translate-x-1/2 pointer-events-none z-10 w-full px-4 text-center">
                        <p className="text-[10px] font-mono text-white/40 tracking-widest uppercase bg-black/40 backdrop-blur-sm inline-block px-3 py-1.5 rounded-full border border-white/5">
                            Click any country to view financial analysis
                        </p>
                    </div>
                )}
            </div>

            {/* ── Chart panel ── */}
            <AnimatePresence>
                {showPanel && (
                    <motion.div
                        initial={{ opacity: 0, x: 50 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 100 }}
                        transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
                        className="absolute inset-0 md:relative md:inset-auto md:w-[45%] h-full shrink-0 z-[60] md:z-auto bg-[#0a0f1e]/95 md:bg-transparent backdrop-blur-xl md:backdrop-blur-none border-l border-white/15 overflow-hidden"
                    >
                        <AssetChartPanel
                            iso={selectedIso}
                            impactData={impactData}
                            loading={impactLoading}
                            onClose={() => { setSelectedIso(null); setSelectedCountryIso(null) }}
                        />
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
