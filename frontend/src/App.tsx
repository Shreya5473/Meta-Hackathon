import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2 } from 'lucide-react'
import { TopBar } from '@/features/visualization/TopBar'
import { LeftPanel } from '@/features/scenario/LeftPanel'
import { RightPanel } from '@/features/signals/RightPanel'
import { BottomTimeline } from '@/features/events/BottomTimeline'
import { EarthGlobe } from '@/features/visualization/EarthGlobe'
import { DeckGLMap } from '@/features/visualization/DeckGLMap'
import TradingCharts from '@/features/visualization/TradingCharts'
import { WaitlistForm } from '@/features/waitlist/WaitlistForm'
import { PortfolioPage, PortfolioGate } from '@/features/portfolio/PortfolioPage'
import { useGti, useLivePrices, useSignals } from '@/shared/api/hooks'
import { useStore } from '@/shared/state/store'
import { useAuth, setStoredEmail } from '@/shared/auth/useAuth'

const PAGE_TRANSITION = {
    initial: { opacity: 0, scale: 1.03 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.97 },
    transition: { duration: 0.35, ease: 'easeInOut' as const },
}

function App() {
    const { mode, selectedRegions, selectedAssetClasses } = useStore()
    const { data: gtiData } = useGti()
    const { data: signalsData } = useSignals()
    const { email, isRegistered } = useAuth()

    // Mobile drawer state for LeftPanel
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
    // Desktop left panel open/close
    const [leftPanelOpen, setLeftPanelOpen] = useState(false)
    // Desktop right (signals) panel open/close
    const [rightPanelOpen, setRightPanelOpen] = useState(true)
    // Mobile signals panel state for RightPanel
    const [mobileSignalsOpen, setMobileSignalsOpen] = useState(false)
    // Waitlist modal state
    const [waitlistOpen, setWaitlistOpen] = useState(false)

    const isChartsMode = mode === 'charts'
    const isGlobeMode = mode === 'globe'
    const isMapMode = mode === 'map'
    const isPortfolioMode = mode === 'portfolio'
    const showPanels = isGlobeMode || isMapMode

    // Filter signals based on active region + asset class filters
    const allSignals = signalsData?.signals ?? []
    const filteredSignals = allSignals.filter((s: any) => {
        const regionOk = selectedRegions.length === 0 ||
            selectedRegions.some(r => s.region?.toLowerCase().includes(r.toLowerCase()) || r.toLowerCase().includes(s.region?.toLowerCase()))
        const assetOk = selectedAssetClasses.length === 0 ||
            selectedAssetClasses.some(a => {
                const target = a.toLowerCase()
                const sector = String(s.sector ?? '').toLowerCase()
                const assetClass = String(s.asset_class ?? '').toLowerCase()
                const category = String(s.category ?? '').toLowerCase()
                return (
                    sector.includes(target) || target.includes(sector) ||
                    assetClass.includes(target) || target.includes(assetClass) ||
                    category.includes(target) || target.includes(category)
                )
            })
        return regionOk && assetOk
    })

    const liveSymbols = useMemo(
        () => filteredSignals.map((s: any) => String(s.symbol ?? '').toUpperCase()).filter(Boolean),
        [filteredSignals]
    )
    const { data: livePrices } = useLivePrices(liveSymbols)
    const enrichedSignals = useMemo(
        () => filteredSignals.map((signal: any) => {
            const live = livePrices?.[String(signal.symbol ?? '').toUpperCase()]
            if (!live) return signal
            return {
                ...signal,
                price: live.price,
                live_change_pct: live.change_pct,
                price_source: live.source,
            }
        }),
        [filteredSignals, livePrices]
    )


    return (
        <div className="relative w-screen h-[100dvh] overflow-hidden bg-[#03060f]">
            {/* Background grid lines */}
            <div
                className="absolute inset-0 pointer-events-none z-0"
                style={{
                    backgroundImage: `
                        linear-gradient(to right,  rgba(255,255,255,0.04) 1px, transparent 1px),
                        linear-gradient(to bottom, rgba(255,255,255,0.04) 1px, transparent 1px)
                    `,
                    backgroundSize: '48px 48px',
                }}
            />

            {/* ── Visualization canvas (full-screen) ── */}
            <div className="absolute inset-0 z-10">
                <AnimatePresence mode="wait">
                    {isGlobeMode && (
                        <motion.div key="globe" className="absolute inset-0" {...PAGE_TRANSITION}>
                            <EarthGlobe gti={gtiData} />
                        </motion.div>
                    )}
                    {isMapMode && (
                        <motion.div key="map" className="absolute inset-0" {...PAGE_TRANSITION}>
                            <DeckGLMap />
                        </motion.div>
                    )}
                    {isChartsMode && (
                        <motion.div key="charts" className="absolute inset-0" {...PAGE_TRANSITION}>
                            <TradingCharts />
                        </motion.div>
                    )}
                    {isPortfolioMode && (
                        <motion.div key="portfolio" className="absolute inset-0" {...PAGE_TRANSITION}>
                            {isRegistered && email ? (
                                <PortfolioPage email={email} onRegisterClick={() => setWaitlistOpen(true)} />
                            ) : (
                                <PortfolioGate onRegisterClick={() => setWaitlistOpen(true)} />
                            )}
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* ── Mobile backdrop overlay when drawer open ── */}
            <AnimatePresence>
                {(mobileMenuOpen || mobileSignalsOpen) && (
                    <motion.div
                        key="backdrop"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-40 bg-black/60 md:hidden"
                        onClick={() => { setMobileMenuOpen(false); setMobileSignalsOpen(false) }}
                    />
                )}
            </AnimatePresence>

            {/* ── Waitlist Modal Overlay ── */}
            <AnimatePresence>
                {waitlistOpen && (
                    <motion.div
                        key="waitlist-overlay"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
                        onClick={(e) => {
                            if (e.target === e.currentTarget) setWaitlistOpen(false)
                        }}
                    >
                        <motion.div
                            initial={{ scale: 0.95, opacity: 0, y: 20 }}
                            animate={{ scale: 1, opacity: 1, y: 0 }}
                            exit={{ scale: 0.95, opacity: 0, y: 20 }}
                            className="bg-[#0a0f1e]/95 border border-white/20 rounded-2xl shadow-2xl relative w-full max-w-md overflow-hidden"
                        >
                            <WaitlistForm
                                onClose={() => setWaitlistOpen(false)}
                                onSuccess={(registeredEmail: string) => {
                                    setStoredEmail(registeredEmail)
                                }}
                            />
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── UI overlay layer ── */}
            <div className="absolute inset-0 z-50 pointer-events-none flex flex-col">

                {/* TopBar — always visible */}
                <div className="pointer-events-auto shrink-0">
                    <TopBar
                        gti={gtiData}
                        onMenuToggle={showPanels ? () => setMobileMenuOpen(o => !o) : undefined}
                        menuOpen={mobileMenuOpen}
                    />
                </div>

                {/* Middle row: Left + Right panels (only on globe/map) — desktop layout */}
                {showPanels && (
                    <div className="flex-1 flex overflow-hidden relative">

                        {/* ── LEFT PANEL — Desktop: side panel | Mobile: slide-in drawer ── */}

                        {/* Desktop side panel */}
                        {leftPanelOpen && (
                            <motion.div
                                key={`left-${mode}`}
                                initial={{ x: -320, opacity: 0 }}
                                animate={{ x: 0, opacity: 1 }}
                                exit={{ x: -320, opacity: 0 }}
                                transition={{ type: 'spring', stiffness: 220, damping: 26, delay: 0.1 }}
                                className="hidden md:block w-72 pointer-events-auto m-3 mr-0"
                            >
                                <LeftPanel onClose={() => setLeftPanelOpen(false)} />
                            </motion.div>
                        )}

                        {/* Desktop re-open button when panel is closed */}
                        {!leftPanelOpen && (
                            <motion.button
                                initial={{ x: -40, opacity: 0 }}
                                animate={{ x: 0, opacity: 1 }}
                                onClick={() => setLeftPanelOpen(true)}
                                className="hidden md:flex pointer-events-auto m-3 mr-0 h-10 items-center gap-2 px-3 rounded-lg bg-[#07091a]/90 border border-white/20 text-white font-mono text-[10px] font-semibold backdrop-blur-md hover:bg-white/5 transition-all"
                            >
                                <span>⟩</span> FILTERS
                            </motion.button>
                        )}

                        {/* Mobile drawer */}
                        <AnimatePresence>
                            {mobileMenuOpen && (
                                <motion.div
                                    key="mobile-left-drawer"
                                    initial={{ x: '-100%' }}
                                    animate={{ x: 0 }}
                                    exit={{ x: '-100%' }}
                                    transition={{ type: 'spring', stiffness: 260, damping: 30 }}
                                    className="md:hidden fixed top-[56px] left-0 bottom-0 w-[85vw] max-w-[320px] z-50 pointer-events-auto"
                                    style={{ zIndex: 60 }}
                                >
                                    <LeftPanel onClose={() => setMobileMenuOpen(false)} />
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Spacer — leaves room for visualisation */}
                        <div className="flex-1" />

                        {/* ── RIGHT PANEL — Desktop: side panel | Mobile: slide-in drawer ── */}

                        {/* Desktop side panel (globe mode only) */}
                        {isGlobeMode && rightPanelOpen && (
                            <motion.div
                                key="right-globe"
                                initial={{ x: 320, opacity: 0 }}
                                animate={{ x: 0, opacity: 1 }}
                                exit={{ x: 320, opacity: 0 }}
                                transition={{ type: 'spring', stiffness: 220, damping: 26, delay: 0.15 }}
                                className="hidden md:block w-80 pointer-events-auto m-3 ml-0"
                            >
                                <RightPanel signals={enrichedSignals} onClose={() => setRightPanelOpen(false)} />
                            </motion.div>
                        )}

                        {/* Desktop re-open button for signals when closed */}
                        {isGlobeMode && !rightPanelOpen && (
                            <motion.button
                                initial={{ x: 40, opacity: 0 }}
                                animate={{ x: 0, opacity: 1 }}
                                onClick={() => setRightPanelOpen(true)}
                                className="hidden md:flex pointer-events-auto m-3 ml-0 h-10 items-center gap-2 px-3 rounded-lg bg-[#07091a]/90 border border-white/20 text-white font-mono text-[10px] font-semibold backdrop-blur-md hover:bg-white/5 transition-all"
                            >
                                SIGNALS <span>⟨</span>
                            </motion.button>
                        )}

                        {/* Mobile signals FAB button */}
                        {isGlobeMode && (
                            <button
                                onClick={() => setMobileSignalsOpen(o => !o)}
                                className="md:hidden fixed bottom-20 right-4 z-50 pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-full bg-white/10 border border-white/25 text-white font-mono text-[11px] font-semibold backdrop-blur-md shadow-lg shadow-white/5"
                                style={{ zIndex: 55 }}
                            >
                                <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                                SIGNALS
                            </button>
                        )}

                        {/* Mobile signals drawer */}
                        <AnimatePresence>
                            {mobileSignalsOpen && isGlobeMode && (
                                <motion.div
                                    key="mobile-right-drawer"
                                    initial={{ x: '100%' }}
                                    animate={{ x: 0 }}
                                    exit={{ x: '100%' }}
                                    transition={{ type: 'spring', stiffness: 260, damping: 30 }}
                                    className="md:hidden fixed top-[56px] right-0 bottom-0 w-[90vw] max-w-[360px] pointer-events-auto"
                                    style={{ zIndex: 60 }}
                                >
                                    <RightPanel
                                        signals={enrichedSignals}
                                        onClose={() => setMobileSignalsOpen(false)}
                                    />
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                )}

                {/* Charts mode: fill space */}
                {isChartsMode && <div className="flex-1" />}

                {/* Bottom timeline — globe & map only */}
                {showPanels && (
                    <motion.div
                        initial={{ y: 80, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        transition={{ type: 'spring', stiffness: 200, damping: 26, delay: 0.2 }}
                        className="pointer-events-auto shrink-0 mx-2 sm:mx-3 mb-2 sm:mb-3"
                    >
                        <BottomTimeline gti={gtiData} />
                    </motion.div>
                )}

                {/* ── Early Access / Waitlist FAB (visible everywhere) ── */}
                <motion.button
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    whileHover={{ scale: isRegistered ? 1 : 1.05 }}
                    whileTap={{ scale: isRegistered ? 1 : 0.95 }}
                    onClick={() => { if (!isRegistered) setWaitlistOpen(true) }}
                    className={`fixed bottom-[88px] right-4 sm:bottom-6 sm:right-6 z-50 flex items-center justify-center rounded-full font-mono text-xs font-bold pointer-events-auto transition-all duration-300 overflow-hidden backdrop-blur-md ${isRegistered
                        ? 'bg-emerald-500/20 border border-emerald-400/50 shadow-[0_0_20px_rgba(16,185,129,0.2)] cursor-default text-emerald-300'
                        : 'bg-pink-500/10 border border-pink-400/30 hover:bg-pink-500/20 hover:border-pink-400/60 shadow-[0_0_15px_rgba(236,72,153,0.15)] hover:shadow-[0_0_25px_rgba(236,72,153,0.3)] text-white'
                        }`}
                >
                    <AnimatePresence mode="wait">
                        {isRegistered ? (
                            <motion.div
                                key="registered"
                                initial={{ opacity: 0, y: 15 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -15 }}
                                transition={{ duration: 0.3 }}
                                className="flex items-center gap-2 px-4 py-3"
                            >
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-200" />
                                <span>REGISTERED</span>
                            </motion.div>
                        ) : (
                            <motion.div
                                key="join"
                                initial={{ opacity: 0, y: 15 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -15 }}
                                transition={{ duration: 0.3 }}
                                className="flex items-center gap-2 px-4 py-3"
                            >
                                <span className="w-2 h-2 rounded-full bg-pink-200 animate-pulse" />
                                <span>JOIN WAITLIST</span>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </motion.button>

                <div className="fixed left-3 bottom-3 sm:left-4 sm:bottom-4 z-50 pointer-events-none font-mono text-[10px] sm:text-xs tracking-wide text-white/60">
                    made by shreeya gupta and rushit palesha
                </div>
            </div>
        </div>
    )
}

export default App
