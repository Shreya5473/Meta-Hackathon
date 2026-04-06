import { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import Globe from 'react-globe.gl'
import { motion, AnimatePresence } from 'framer-motion'
import { MapPin, ChevronRight, Globe2 } from 'lucide-react'
import { useStore } from '@/shared/state/store'
import { api } from '@/shared/api/client'

// ── Colour helpers ────────────────────────────────────────────────────────
function gtiToCapColor(score: number): string {
    if (score >= 80) return 'rgba(239,68,68,0.70)'
    if (score >= 60) return 'rgba(245,158,11,0.60)'
    if (score >= 35) return 'rgba(14,165,233,0.50)'
    return 'rgba(34,197,94,0.35)'
}

function gtiToLabel(score: number) {
    if (score >= 80) return { text: 'CRITICAL', cls: 'text-red-400 border-red-400/40 bg-red-400/10' }
    if (score >= 60) return { text: 'HIGH', cls: 'text-amber-400 border-amber-400/40 bg-amber-400/10' }
    if (score >= 35) return { text: 'MEDIUM', cls: 'text-white border-white/20 bg-white/5' }
    return { text: 'LOW', cls: 'text-green-400 border-green-400/40 bg-green-400/10' }
}

// ── Transition flash overlay ──────────────────────────────────────────────
function TransitionFlash({ active }: { active: boolean }) {
    return (
        <AnimatePresence>
            {active && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: [0, 0.6, 0] }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.55, times: [0, 0.3, 1] }}
                    className="absolute inset-0 z-50 pointer-events-none"
                    style={{ background: 'radial-gradient(circle, rgba(255,255,255,0.3) 0%, rgba(0,8,32,0.95) 100%)' }}
                />
            )}
        </AnimatePresence>
    )
}

// ── Hover tooltip ─────────────────────────────────────────────────────────
function CountryTooltip({ country, pos }: { country: any; pos: { x: number; y: number } | null }) {
    if (!country || !pos) return null
    const { text, cls } = gtiToLabel(country.gti_score)
    return (
        <div
            className="absolute z-30 pointer-events-none"
            style={{ left: pos.x + 14, top: pos.y - 40 }}
        >
            <div className="bg-[#070c1a]/95 border border-white/15 rounded-lg px-3 py-2 shadow-xl backdrop-blur-lg min-w-[160px]">
                <div className="flex items-center justify-between gap-3">
                    <span className="text-white text-xs font-bold font-mono">{country.name}</span>
                    <span className={`text-[9px] font-mono border px-1.5 py-0.5 rounded ${cls}`}>{text}</span>
                </div>
                <div className="text-[10px] font-mono text-gray-400 mt-0.5">
                    GTI: <span className="text-white font-bold">{country.gti_score?.toFixed(1)}</span>
                    <span className="text-gray-600 ml-2">· Click to view market impact</span>
                </div>
            </div>
        </div>
    )
}

// ── Main Globe component ──────────────────────────────────────────────────
export function EarthGlobe({ gti }: { gti: any }) {
    const globeEl = useRef<any>(null)
    const { setMode, setSelectedCountryIso } = useStore()

    const [w, setW] = useState(window.innerWidth)
    const [h, setH] = useState(window.innerHeight)
    const [geojson, setGeojson] = useState<{ features: any[] }>({ features: [] })
    const [countryData, setCountryData] = useState<any>(null)
    const [hoveredCountry, setHoveredCountry] = useState<any>(null)
    const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null)
    const [transitioning, setTransitioning] = useState(false)

    // resize
    useEffect(() => {
        const fn = () => { setW(window.innerWidth); setH(window.innerHeight) }
        window.addEventListener('resize', fn)
        return () => window.removeEventListener('resize', fn)
    }, [])

    // GeoJSON
    useEffect(() => {
        fetch('https://raw.githubusercontent.com/vasturiano/react-globe.gl/master/example/datasets/ne_110m_admin_0_countries.geojson')
            .then(r => r.json()).then(setGeojson).catch(() => { })
    }, [])

    // Backend data
    useEffect(() => {
        api.getGlobeCountries().then(setCountryData)
        const t = setInterval(() => api.getGlobeCountries().then(setCountryData), 30000)
        return () => clearInterval(t)
    }, [])

    // ISO → GTI score lookup
    const riskLookup = useMemo<Record<string, number>>(() => {
        if (!countryData?.countries) return {}
        return Object.fromEntries(countryData.countries.map((c: any) => [c.iso, c.gti_score]))
    }, [countryData])

    // ISO → country name lookup
    const nameLookup = useMemo<Record<string, string>>(() => {
        if (!countryData?.countries) return {}
        return Object.fromEntries(countryData.countries.map((c: any) => [c.iso, c.name]))
    }, [countryData])

    // Globe setup
    useEffect(() => {
        if (!globeEl.current) return
        const g = globeEl.current
        g.controls().autoRotate = true
        g.controls().autoRotateSpeed = 0.3
        g.controls().enableZoom = true
        g.pointOfView({ lat: 25, lng: 20, altitude: 2.2 }, 0)
    }, [])

    // Duplicate arcs to create a faint base line + a bright animated pulse
    const displayArcs = useMemo(() => {
        const rawArcs = countryData?.arcs ?? []
        return [
            ...rawArcs.map((a: any) => ({ ...a, isPulse: false })),
            ...rawArcs.map((a: any) => ({ ...a, isPulse: true }))
        ]
    }, [countryData])
    const rings = useMemo(() => (countryData?.event_markers ?? []).map((e: any) => ({
        lat: e.lat, lng: e.lng,
        maxR: (e.severity ?? 0.5) * 3.5,
        propagationSpeed: 1.5,
        repeatPeriod: 1000,
        color: e.classification?.includes('military') ? '#ef4444' : '#f59e0b',
    })), [countryData])

    // Country click → flash → transition to map
    const handlePolygonClick = useCallback((polygon: any) => {
        if (!polygon?.properties) return
        const iso = polygon.properties.ISO_A2 ?? ''
        if (!iso) return

        setTransitioning(true)
        if (globeEl.current) {
            globeEl.current.controls().autoRotate = false
        }

        // Brief pause for flash animation, then switch mode
        setTimeout(() => {
            setSelectedCountryIso(iso)
            setMode('map')
        }, 450)
    }, [setSelectedCountryIso, setMode])

    const handlePolygonHover = useCallback((polygon: any) => {
        const iso = polygon?.properties?.ISO_A2 ?? ''
        if (iso) {
            const score = riskLookup[iso] ?? 30
            const name = nameLookup[iso] ?? polygon.properties?.NAME ?? iso
            setHoveredCountry({ iso, name, gti_score: score })
        } else {
            setHoveredCountry(null)
            setTooltipPos(null)
        }
    }, [riskLookup, nameLookup])

    const globalGti = countryData?.global_gti ?? gti?.gti_value ?? 67

    return (
        <div
            className="w-full h-full absolute inset-0 bg-[#010816]"
            onMouseMove={e => tooltipPos && setTooltipPos({ x: e.clientX, y: e.clientY })}
            onMouseLeave={() => { setHoveredCountry(null); setTooltipPos(null) }}
        >
            <Globe
                ref={globeEl}
                width={w}
                height={h}
                globeImageUrl="//cdn.jsdelivr.net/npm/three-globe/example/img/earth-night.jpg"
                bumpImageUrl="//cdn.jsdelivr.net/npm/three-globe/example/img/earth-topology.png"
                backgroundImageUrl="//cdn.jsdelivr.net/npm/three-globe/example/img/night-sky.png"
                atmosphereColor="#00d4ff"
                atmosphereAltitude={0.10}
                showAtmosphere
                waitForGlobeReady={false}

                polygonsData={geojson.features}
                polygonCapColor={(d: any) => {
                    const score = riskLookup[d.properties?.ISO_A2 ?? ''] ?? 20
                    return gtiToCapColor(score)
                }}
                polygonSideColor={() => 'rgba(0,0,0,0.05)'}
                polygonStrokeColor={(d: any) => {
                    const iso = d.properties?.ISO_A2 ?? ''
                    return iso === hoveredCountry?.iso ? 'rgba(255,255,255,0.9)' : 'rgba(0,200,255,0.3)'
                }}
                polygonAltitude={(d: any) => {
                    const score = riskLookup[d.properties?.ISO_A2 ?? ''] ?? 0
                    const hovered = (d.properties?.ISO_A2 ?? '') === hoveredCountry?.iso
                    return (hovered ? 0.02 : 0) + 0.002 + score * 0.0005
                }}
                onPolygonClick={handlePolygonClick}
                onPolygonHover={handlePolygonHover}
                polygonLabel={() => ''}

                // Tension arcs
                arcsData={displayArcs}
                arcColor={(d: any) => {
                    const isMilitary = d.type?.includes('military')
                    if (!d.isPulse) {
                        return ['rgba(255, 255, 255, 0.15)', isMilitary ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)']
                    }
                    return ['rgba(255, 255, 255, 0.0)', isMilitary ? 'rgba(239, 68, 68, 1)' : 'rgba(245, 158, 11, 1)']
                }}
                arcDashLength={(d: any) => d.isPulse ? 0.5 : 1}
                arcDashGap={(d: any) => d.isPulse ? 2.5 : 0}
                arcDashInitialGap={(d: any) => d.isPulse ? Math.random() * 5 : 0}
                arcDashAnimateTime={(d: any) => d.isPulse ? 2000 : 0}
                arcStroke={(d: any) => (d.isPulse ? 0.3 : 0.1) + (d.severity ?? 0.5) * 0.2}
                arcAltitude={(d: any) => 0.15 + (d.severity ?? 0.5) * 0.25}
                arcLabel={(d: any) => {
                    if (!d.isPulse) return ''
                    return `<div style="background:#070c1a;border:1px solid rgba(255,255,255,0.25);padding:5px 9px;border-radius:6px;font-family:monospace;font-size:11px;color:#e2e8f0">${d.fromName ?? ''} → ${d.toName ?? ''}<br/><span style="color:#f59e0b">${(d.type ?? '').replace(/_/g, ' ').toUpperCase()}</span></div>`
                }}

                // Event rings
                ringsData={rings}
                ringLat="lat"
                ringLng="lng"
                ringMaxRadius="maxR"
                ringPropagationSpeed="propagationSpeed"
                ringRepeatPeriod="repeatPeriod"
                ringColor={(d: any) => (t: number) =>
                    `${d.color}${Math.round((1 - t) * 200).toString(16).padStart(2, '0')}`
                }
                ringAltitude={0.005}
            />

            {/* Transition flash */}
            <TransitionFlash active={transitioning} />

            {/* HUD corners */}
            <div className="absolute inset-0 pointer-events-none z-20 overflow-hidden">
                <div className="absolute top-[60px] left-6 border-l-2 border-t-2 border-white/25 w-12 h-12" />
                <div className="absolute top-[60px] right-6 border-r-2 border-t-2 border-white/25 w-12 h-12" />
                <div className="absolute bottom-[90px] left-6 border-l-2 border-b-2 border-white/25 w-12 h-12" />
                <div className="absolute bottom-[90px] right-6 border-r-2 border-b-2 border-white/25 w-12 h-12" />

                {/* Global GTI badge — top centre */}
                <div className="absolute top-[60px] left-1/2 -translate-x-1/2 flex items-center gap-4 text-[10px] font-mono">
                    <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                        <span className="text-green-400 tracking-widest">LIVE</span>
                    </div>
                    <div className="bg-[#070c1a]/80 border border-white/15 rounded-lg px-3 py-1.5 flex items-center gap-2">
                        <Globe2 className="h-3 w-3 text-white" />
                        <span className="text-gray-400">Global GTI</span>
                        <span className="text-white font-bold">{globalGti.toFixed(1)}</span>
                    </div>
                </div>

                {/* Legend — bottom left */}
                <div className="absolute bottom-[90px] left-6 text-[9px] font-mono bg-[#070c1a]/75 border border-white/10 rounded-lg p-2.5 space-y-1.5">
                    <p className="text-gray-500 uppercase tracking-widest text-[8px] mb-1.5">Risk Level</p>
                    {[
                        { label: 'CRITICAL ≥80', color: '#ef4444' },
                        { label: 'HIGH ≥60', color: '#f59e0b' },
                        { label: 'MEDIUM ≥35', color: '#0ea5e9' },
                        { label: 'LOW <35', color: '#22c55e' },
                    ].map(({ label, color }) => (
                        <div key={label} className="flex items-center gap-2">
                            <span className="w-3 h-1 rounded-full" style={{ background: color }} />
                            <span className="text-gray-400">{label}</span>
                        </div>
                    ))}
                </div>

                {/* Arc types — bottom right */}
                <div className="absolute bottom-[90px] right-6 text-[9px] font-mono bg-[#070c1a]/75 border border-white/10 rounded-lg p-2.5 space-y-1.5">
                    <p className="text-gray-500 uppercase tracking-widest text-[8px] mb-1.5">Arc Types</p>
                    {[
                        { label: 'Military', color: '#ef4444' },
                        { label: 'Sanctions', color: '#f97316' },
                        { label: 'Trade', color: '#f59e0b' },
                        { label: 'Diplomatic', color: '#0ea5e9' },
                    ].map(({ label, color }) => (
                        <div key={label} className="flex items-center gap-2">
                            <span className="w-5 h-px" style={{ background: color }} />
                            <span className="text-gray-400">{label}</span>
                        </div>
                    ))}
                </div>

                {/* Click instruction — bottom centre */}
                <div className="absolute bottom-[90px] left-1/2 -translate-x-1/2">
                    <div className="flex items-center gap-2 bg-[#070c1a]/70 border border-white/10 rounded-lg px-3 py-1.5 text-[10px] font-mono text-gray-400">
                        <MapPin className="h-3 w-3 text-white" />
                        Click any country to view market impact
                        <ChevronRight className="h-3 w-3 text-white" />
                    </div>
                </div>
            </div>

            {/* Mouse-tracking tooltip */}
            <CountryTooltip country={hoveredCountry} pos={tooltipPos} />

            {/* Invisible overlay to track mouse */}
            <div
                className="absolute inset-0 z-[25] pointer-events-none"
                onMouseMove={e => setTooltipPos({ x: e.clientX, y: e.clientY })}
            />
        </div>
    )
}
