import { useStore } from '@/shared/state/store'
import { Panel } from '@/shared/ui/Panel'
import { Flame, BarChart3, Crosshair, ShieldAlert, Truck, Filter, Thermometer, X } from 'lucide-react'

interface LeftPanelProps {
    onClose?: () => void
}

export function LeftPanel({ onClose }: LeftPanelProps) {
    const { scenario, updateScenario, selectedRegions, toggleRegion, selectedAssetClasses, toggleAssetClass } = useStore()

    const regions = ["North America", "Europe", "Asia Pacific", "Middle East", "Latin America", "Africa"] as const
    const assets = ["Equities", "Bonds", "Commodities", "Forex", "Crypto"] as const

    const activeFilterCount = selectedRegions.length + selectedAssetClasses.length

    return (
        <Panel className="flex flex-col h-full overflow-y-auto">
            {/* Panel header with title + close button (always shown when onClose provided) */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border/50 shrink-0">
                <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                    <Filter className="w-3 h-3" /> Filters &amp; Scenarios
                </span>
                {onClose && (
                    <button
                        onClick={onClose}
                        className="flex items-center justify-center w-8 h-8 rounded-lg border border-white/10 bg-white/5 text-gray-400 hover:text-red-300 hover:bg-red-500/20 hover:border-red-400/40 transition-all"
                        title="Close panel"
                    >
                        <X className="w-4 h-4" />
                    </button>
                )}
            </div>

            {/* Filters */}
            <div className="p-4 border-b border-border/50">
                <div className="flex items-center justify-between mb-3">
                    <h2 className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
                        <Filter className="w-3 h-3" /> Filters
                    </h2>
                    {activeFilterCount > 0 && (
                        <span className="text-[9px] font-mono bg-[var(--color-primary)]/20 text-[var(--color-primary)] px-2 py-0.5 rounded border border-[var(--color-primary)]/30">
                            {activeFilterCount} Active
                        </span>
                    )}
                </div>

                {activeFilterCount === 0 && (
                    <p className="text-[10px] font-mono text-gray-500 bg-secondary/30 p-2 rounded border border-border/50 mb-4">
                        💡 No regions selected = showing global data
                    </p>
                )}

                <div className="space-y-4">
                    <div>
                        <span className="text-[9px] uppercase tracking-widest text-muted-foreground/50 block mb-2">Regions</span>
                        <div className="flex flex-wrap gap-1.5">
                            {regions.map(r => (
                                <button
                                    key={r}
                                    onClick={() => toggleRegion(r)}
                                    className={`px-2.5 py-1.5 rounded-[2px] border text-[9px] font-mono tracking-wider transition-colors ${selectedRegions.includes(r)
                                        ? 'bg-[var(--color-primary)]/10 text-[var(--color-primary)] border-[var(--color-primary)]/30'
                                        : 'bg-transparent text-muted-foreground border-border hover:border-border/80'
                                        }`}
                                    style={{ minHeight: '36px' }}
                                >
                                    {r.replace("North", "N.").replace("Latin", "L.").replace("Pacific", "Pac.")}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div>
                        <span className="text-[9px] uppercase tracking-widest text-muted-foreground/50 block mb-2">Assets</span>
                        <div className="flex flex-wrap gap-1.5">
                            {assets.map(a => (
                                <button
                                    key={a}
                                    onClick={() => toggleAssetClass(a)}
                                    className={`px-2.5 py-1.5 rounded-[2px] border text-[9px] font-mono tracking-wider transition-colors ${selectedAssetClasses.includes(a)
                                        ? 'bg-[var(--color-primary)]/10 text-[var(--color-primary)] border-[var(--color-primary)]/30'
                                        : 'bg-transparent text-muted-foreground border-border hover:border-border/80'
                                        }`}
                                    style={{ minHeight: '36px' }}
                                >
                                    {a}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* Scenario Simulation */}
            <div className="p-4 flex-1">
                <h2 className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-muted-foreground mb-4">
                    <Thermometer className="w-3 h-3" /> What-If Scenarios
                </h2>

                <div className="space-y-6">
                    <ScenarioSlider
                        label="Oil Shock"
                        value={scenario.oilPriceShock}
                        onChange={(v) => updateScenario({ oilPriceShock: v })}
                        icon={<Flame className="h-3 w-3 text-[#f59e0b]" />}
                        color="#f59e0b"
                    />
                    <ScenarioSlider
                        label="Rate Change"
                        value={scenario.interestRateChange}
                        onChange={(v) => updateScenario({ interestRateChange: v })}
                        icon={<BarChart3 className="h-3 w-3 text-[#0ea5e9]" />}
                        color="#0ea5e9"
                    />
                    <ScenarioSlider
                        label="Escalation"
                        value={scenario.geopoliticalEscalation}
                        onChange={(v) => updateScenario({ geopoliticalEscalation: v })}
                        icon={<Crosshair className="h-3 w-3 text-[#ef4444]" />}
                        color="#ef4444"
                    />
                    <ScenarioSlider
                        label="Supply Chain"
                        value={scenario.supplyChainDisruption}
                        onChange={(v) => updateScenario({ supplyChainDisruption: v })}
                        icon={<Truck className="h-3 w-3 text-[#f59e0b]" />}
                        color="#f59e0b"
                    />
                    <ScenarioSlider
                        label="Cyber Threat"
                        value={scenario.cyberThreatLevel}
                        onChange={(v) => updateScenario({ cyberThreatLevel: v })}
                        icon={<ShieldAlert className="h-3 w-3 text-[#ffffff]" />}
                        color="#ffffff"
                    />
                </div>
            </div>
        </Panel>
    )
}

function ScenarioSlider({ label, value, onChange, icon, color }: {
    label: string
    value: number
    onChange: (v: number) => void
    icon: React.ReactNode
    color: string
}) {
    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                    {icon}
                    <span className="text-[10px] font-mono text-foreground/80 uppercase tracking-wider">
                        {label}
                    </span>
                </div>
                <span className="text-[11px] font-mono font-semibold tabular-nums" style={{ color }}>
                    {value}%
                </span>
            </div>
            {/* Slider track — tall enough for touch (44px via wrapper) */}
            <div className="relative flex items-center" style={{ height: '28px' }}>
                <div className="absolute inset-x-0 h-1.5 rounded-full bg-secondary/80 overflow-hidden" style={{ top: '50%', transform: 'translateY(-50%)' }}>
                    <div
                        className="absolute inset-y-0 left-0 rounded-full transition-all duration-300"
                        style={{ width: `${value}%`, background: `linear-gradient(90deg, ${color}40, ${color})`, boxShadow: `0 0 8px ${color}40` }}
                    />
                </div>
                <input
                    type="range"
                    min={0}
                    max={100}
                    value={value}
                    onChange={(e) => onChange(Number(e.target.value))}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    style={{ minHeight: 'unset' }}
                />
            </div>
        </div>
    )
}
