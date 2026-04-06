import { Globe, Map, BarChart2, Briefcase, Activity, Shield, Wifi, TrendingUp, TrendingDown, Minus, Clock, Menu, X } from 'lucide-react'
import { cn } from '@/shared/ui/Panel'
import { useStore, type VisualizationMode } from '@/shared/state/store'
import { useEffect, useState } from 'react'

const MODES: { id: VisualizationMode; label: string; sub: string; icon: typeof Globe }[] = [
    { id: 'globe', label: 'EARTH PULSE', sub: 'Global Intelligence Globe', icon: Globe },
    { id: 'map', label: 'GEO MAP', sub: 'Market Impact Map', icon: Map },
    { id: 'charts', label: 'AI SIGNALS', sub: 'Trading Recommendations', icon: BarChart2 },
    { id: 'portfolio', label: 'PORTFOLIO', sub: 'My Holdings & Risk', icon: Briefcase },
]

function LiveClock() {
    const [t, setT] = useState(() => new Date().toISOString().substring(11, 19))
    useEffect(() => {
        const id = setInterval(() => setT(new Date().toISOString().substring(11, 19)), 1000)
        return () => clearInterval(id)
    }, [])
    return <span className="font-mono text-[11px] tabular-nums text-gray-400">{t} UTC</span>
}

interface TopBarProps {
    gti: any
    onMenuToggle?: () => void
    menuOpen?: boolean
}

export function TopBar({ gti, onMenuToggle, menuOpen }: TopBarProps) {
    const { mode, setMode } = useStore()

    const gtiVal = gti?.gti_value ?? null
    const gtiDelta = gti?.gti_delta_1h ?? 0
    const severity = gtiVal === null ? 'OFFLINE' : gtiVal >= 80 ? 'CRITICAL' : gtiVal >= 60 ? 'ELEVATED' : 'NOMINAL'
    const sevColor = gtiVal === null ? 'text-gray-500' : gtiVal >= 80 ? 'text-red-400' : gtiVal >= 60 ? 'text-amber-400' : 'text-green-400'
    const sevBg = gtiVal === null ? '' : gtiVal >= 80 ? 'bg-red-500/10 border-red-500/20'
        : gtiVal >= 60 ? 'bg-amber-500/10 border-amber-500/20'
            : 'bg-green-500/10 border-green-500/20'

    return (
        <div className="w-full flex items-center justify-between px-3 sm:px-5 py-2 sm:py-2.5 bg-[#07091a]/95 backdrop-blur-xl border-b border-white/10 shadow-lg min-h-[56px]">

            {/* ── Left: Brand + GTI ── */}
            <div className="flex items-center gap-2 sm:gap-5 min-w-0">
                {/* Hamburger button — mobile only (globe/map modes) */}
                {onMenuToggle && (
                    <button
                        onClick={onMenuToggle}
                        aria-label={menuOpen ? 'Close menu' : 'Open menu'}
                        className="md:hidden flex items-center justify-center w-10 h-10 rounded-lg border border-white/15 bg-white/3 text-white hover:bg-white/5 transition-colors shrink-0"
                    >
                        {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
                    </button>
                )}

                {/* Logo */}
                <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
                    <div className="h-8 w-8 rounded-lg bg-white/5 border border-white/15 flex items-center justify-center">
                        <Activity className="h-4 w-4 sm:h-4.5 sm:w-4.5 text-white" />
                    </div>
                    <div>
                        <p className="text-[12px] sm:text-[13px] font-bold font-mono tracking-[0.18em] text-white leading-none">GEOTRADE</p>
                        <p className="text-[8px] sm:text-[9px] font-mono text-white/60 tracking-widest leading-none mt-0.5">TRADER v2.0</p>
                    </div>
                </div>

                {/* Divider — hidden on mobile */}
                <div className="hidden sm:block w-px h-8 bg-white/8 shrink-0" />

                {/* GTI Score — hidden on mobile, abbreviated on tablet */}
                <div className="hidden sm:flex items-center gap-3">
                    <Shield className="h-4 w-4 text-gray-500 shrink-0" />
                    <div>
                        <p className="text-[9px] font-mono uppercase tracking-widest text-gray-500 leading-none mb-1 hidden lg:block">
                            Global Tension Index (GTI)
                        </p>
                        <p className="text-[9px] font-mono uppercase tracking-widest text-gray-500 leading-none mb-1 lg:hidden">
                            GTI
                        </p>
                        <div className="flex items-center gap-2">
                            <span className={cn('text-xl font-mono font-bold tabular-nums leading-none', sevColor)}>
                                {gtiVal !== null ? gtiVal.toFixed(1) : '--.-'}
                            </span>
                            <div className="hidden lg:flex items-center gap-0.5 text-[10px] font-mono">
                                {gtiDelta > 0 ? <TrendingUp className="h-3 w-3 text-red-400" /> :
                                    gtiDelta < 0 ? <TrendingDown className="h-3 w-3 text-green-400" /> :
                                        <Minus className="h-3 w-3 text-gray-500" />}
                                <span className={gtiDelta >= 0 ? 'text-red-400' : 'text-green-400'}>
                                    {gtiDelta !== 0 ? `${gtiDelta > 0 ? '+' : ''}${gtiDelta.toFixed(1)}` : ''}
                                </span>
                            </div>
                            <span className={cn('text-[9px] font-mono border px-1.5 py-0.5 rounded', sevBg, sevColor)}>
                                {severity}
                            </span>
                        </div>
                    </div>
                </div>

                {/* GTI compact badge — mobile only */}
                <div className="flex sm:hidden items-center gap-1.5">
                    <Shield className="h-3.5 w-3.5 text-gray-500 shrink-0" />
                    <span className={cn('text-sm font-mono font-bold tabular-nums', sevColor)}>
                        {gtiVal !== null ? gtiVal.toFixed(0) : '--'}
                    </span>
                    <span className={cn('text-[8px] font-mono border px-1 py-0.5 rounded', sevBg, sevColor)}>
                        {severity}
                    </span>
                </div>
            </div>

            {/* ── Center: Mode toggle ── */}
            <div className="flex items-center gap-0.5 sm:gap-1 bg-[#03060f]/60 border border-white/10 rounded-xl p-0.5 sm:p-1">
                {MODES.map(({ id, label, sub, icon: Icon }) => {
                    const active = mode === id
                    return (
                        <button
                            key={id}
                            onClick={() => setMode(id)}
                            title={sub}
                            className={cn(
                                'flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-4 py-2 rounded-lg text-[10px] font-mono font-semibold uppercase tracking-widest transition-all duration-200 min-h-[36px]',
                                active
                                    ? 'bg-white/8 text-white border border-white/20 shadow-[0_0_12px_rgba(255,255,255,0.15)]'
                                    : 'text-gray-500 hover:text-gray-200 hover:bg-white/5 border border-transparent'
                            )}
                        >
                            <Icon className={cn('h-3.5 w-3.5 shrink-0', active && 'text-white')} />
                            <span className="hidden sm:inline">{label}</span>
                        </button>
                    )
                })}
            </div>

            {/* ── Right: Status — hidden on mobile ── */}
            <div className="hidden md:flex items-center gap-3 shrink-0">
                <div className="flex items-center gap-1.5 text-[10px] font-mono bg-green-500/8 border border-green-500/20 rounded-lg px-2.5 py-1.5">
                    <Wifi className="h-3 w-3 text-green-400 animate-pulse" />
                    <span className="text-green-400 font-semibold">LIVE</span>
                    <span className="text-gray-500">·</span>
                    <span className="text-gray-400 hidden lg:inline">{gti?.top_drivers?.length ?? 12} feeds</span>
                </div>

                <div className="hidden lg:flex items-center gap-1.5 text-[10px] bg-[#0a0f1e] border border-gray-700/50 rounded-lg px-2.5 py-1.5">
                    <Clock className="h-3 w-3 text-gray-500" />
                    <LiveClock />
                </div>
            </div>

            {/* Live dot — mobile only */}
            <div className="flex md:hidden items-center gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                <span className="text-[9px] text-green-400 font-mono">LIVE</span>
            </div>
        </div>
    )
}
