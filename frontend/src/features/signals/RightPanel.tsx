import { useStore } from '@/shared/state/store'
import { Panel, Badge, cn } from '@/shared/ui/Panel'
import { Target, Eye, AlertTriangle, ArrowUpRight, ArrowDownRight, BarChart3, ChevronDown, ChevronRight, X } from 'lucide-react'
import { useState } from 'react'

interface RightPanelProps {
    signals: any[]
    onClose?: () => void
}

export function RightPanel({ signals, onClose }: RightPanelProps) {
    const { selectedAssetId, setSelectedAssetId } = useStore()
    const [signalsExpanded, setSignalsExpanded] = useState(true)

    const selectedAsset = signals.find(s => s.symbol === selectedAssetId) || signals[0]

    return (
        <Panel className="flex flex-col h-full overflow-hidden">
            {/* Panel header with SIGNALS title + close button */}
            <div className="flex items-center border-b border-border/50 shrink-0">
                <div className="flex-1 flex items-center gap-2 py-3 px-4 text-[10px] font-mono uppercase tracking-wider text-[var(--color-primary)] border-b border-[var(--color-primary)] bg-[var(--color-primary)]/5 min-h-[44px]">
                    <Target className="h-3.5 w-3.5" /> SIGNALS
                </div>
                {onClose && (
                    <button
                        onClick={onClose}
                        className="px-4 self-stretch flex items-center text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-all shrink-0 border-l border-border/30"
                        title="Close panel"
                    >
                        <X className="w-4 h-4" />
                    </button>
                )}
            </div>

            <div className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-4">
                {selectedAsset && <AssetDetail asset={selectedAsset} />}
                <div>
                    <button
                        onClick={() => setSignalsExpanded(!signalsExpanded)}
                        className="flex items-center justify-between w-full py-2 text-[10px] font-mono uppercase tracking-[0.1em] text-muted-foreground hover:text-foreground transition-colors"
                        style={{ minHeight: '44px' }}
                    >
                        <span className="flex items-center gap-2">
                            <BarChart3 className="h-3.5 w-3.5" /> All Signals ({signals.length})
                        </span>
                        {signalsExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    </button>

                    {signalsExpanded && (
                        <div className="space-y-2 mt-2">
                            {signals.map(signal => (
                                <AssetCard
                                    key={signal.symbol}
                                    asset={signal}
                                    isSelected={selectedAssetId === signal.symbol}
                                    onClick={() => setSelectedAssetId(signal.symbol)}
                                />
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </Panel>
    )
}

function AssetCard({ asset, isSelected, onClick }: { asset: any, isSelected: boolean, onClick: () => void }) {
    const isUp = asset.directional_bias >= 0
    const color = asset.recommendation === 'BUY' ? '#22c55e' : asset.recommendation === 'SELL' ? '#ef4444' : '#f59e0b'
    return (
        <div
            onClick={onClick}
            className={cn(
                "p-3 rounded-md border text-left transition-all cursor-pointer",
                isSelected
                    ? "border-[var(--color-primary)]/30 bg-[var(--color-primary)]/10 shadow-[0_0_15px_rgba(0,242,255,0.1)]"
                    : "border-border/50 bg-secondary/30 hover:bg-secondary/50 hover:border-border"
            )}
            style={{ minHeight: '60px' }}
        >
            <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-mono font-bold">{asset.symbol}</span>
                    <Badge variant={asset.recommendation === 'BUY' ? 'success' : asset.recommendation === 'SELL' ? 'critical' : 'warn'}>
                        {asset.recommendation}
                    </Badge>
                </div>
                <span className={cn("text-xs font-mono tabular-nums flex items-center", isUp ? "text-[#22c55e]" : "text-[#ef4444]")}>
                    {isUp ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                    {Math.abs(asset.directional_bias)}%
                </span>
            </div>
            <div className="flex items-center justify-between text-[11px] font-mono mb-2">
                <span className="text-muted-foreground">{asset.sector}</span>
                <span className="tabular-nums opacity-80">${asset.price?.toFixed(2) || '---'}</span>
            </div>
            <div className="h-1 rounded-full bg-secondary overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${asset.confidence_score}%`, backgroundColor: color, opacity: 0.8 }} />
            </div>
        </div>
    )
}

function AssetDetail({ asset }: { asset: any }) {
    return (
        <div className="space-y-4 p-3 sm:p-4 rounded-md border border-[var(--color-primary)]/20 bg-[var(--color-primary)]/5">
            <div className="flex items-start justify-between">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-xl font-mono font-bold">{asset.symbol}</h3>
                        <Badge variant={asset.recommendation === 'BUY' ? 'success' : asset.recommendation === 'SELL' ? 'critical' : 'warn'}>
                            {asset.recommendation}
                        </Badge>
                    </div>
                    <span className="text-xs font-mono text-muted-foreground">{asset.sector} / {asset.region}</span>
                </div>
                <div className="text-right">
                    <div className="text-lg font-mono font-bold tabular-nums">${asset.price?.toFixed(2) || '--'}</div>
                    <span className={cn("text-xs font-mono tabular-nums", asset.directional_bias >= 0 ? "text-[#22c55e]" : "text-[#ef4444]")}>
                        {asset.directional_bias >= 0 ? '+' : ''}{asset.directional_bias}%
                    </span>
                </div>
            </div>

            <div className="space-y-1.5">
                <div className="flex items-center justify-between flex-wrap gap-2 text-[10px] font-mono">
                    <span className="text-muted-foreground">Confidence: {asset.confidence_score}%</span>
                    <span className="text-muted-foreground">Uncertainty: {asset.uncertainty}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-secondary overflow-hidden flex relative">
                    <div className="h-full bg-[var(--color-primary)]/80" style={{ width: `${asset.confidence_score}%` }} />
                    <div className="absolute inset-y-0 bg-[#f59e0b]/40 rounded-full" style={{ left: `${asset.confidence_score - asset.uncertainty}%`, width: `${asset.uncertainty * 2}%` }} />
                </div>
            </div>

            <div>
                <h4 className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-[var(--color-primary)] mb-2">
                    <Eye className="w-3.5 h-3.5" /> AI Analysis
                </h4>
                <p className="text-xs font-mono text-muted-foreground leading-relaxed">
                    {asset.reasoning}
                </p>
            </div>

            {asset.risk_factors?.length > 0 && (
                <div>
                    <h4 className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-[#f59e0b] mb-2">
                        <AlertTriangle className="w-3.5 h-3.5" /> Risk Factors
                    </h4>
                    <ul className="space-y-1.5">
                        {asset.risk_factors.map((risk: string, i: number) => (
                            <li key={i} className="flex gap-2 text-[10px] font-mono text-muted-foreground">
                                <span className="text-[#f59e0b]/50">{'>>'}</span> {risk}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    )
}
