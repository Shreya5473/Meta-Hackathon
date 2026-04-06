import { Panel } from '@/shared/ui/Panel'
import { AlertCircle, AlertOctagon, Info } from 'lucide-react'
import { useEvents } from '@/shared/api/hooks'
import { fallbackEvents } from '@/shared/api/mockData'

function EventMarker({ event }: { event: any }) {
    const severity = event.severity_score ?? event.magnitude ?? 0
    const isCritical = severity >= 0.8
    const isHigh = severity >= 0.6
    const color = isCritical ? '#ef4444' : isHigh ? '#f59e0b' : '#e2e8f0'
    const Icon = isCritical ? AlertOctagon : isHigh ? AlertCircle : Info
    const ts = event.occurred_at ?? event.ts
    const time = ts ? new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--:--'
    const label = isCritical ? 'CRITICAL' : isHigh ? 'HIGH' : 'MEDIUM'

    return (
        <div
            className="flex items-start gap-2 p-2 border border-border/50 rounded-md bg-secondary/30 min-w-[180px] sm:min-w-[200px] shrink-0 cursor-pointer hover:border-gray-500 transition-colors"
            style={{ borderLeftColor: color, borderLeftWidth: '2px' }}
        >
            <Icon className="w-3.5 h-3.5 mt-0.5 shrink-0" style={{ color }} />
            <div className="flex flex-col">
                <span className="text-[10px] font-mono leading-tight whitespace-nowrap overflow-hidden text-ellipsis w-[130px] sm:w-[155px]">
                    {event.title}
                </span>
                <span className="text-[9px] font-mono text-muted-foreground mt-0.5 tracking-wider">
                    {time} · {event.region ?? 'Global'} · {label}
                </span>
            </div>
        </div>
    )
}

export function BottomTimeline({ gti }: { gti: any }) {
    const { data: eventsData } = useEvents()
    const events = eventsData?.events ?? fallbackEvents

    const gtiValues = [40, 45, 42, 50, 65, 78, 80, 75, 72, 70, 75, gti?.gti_value ?? 71]

    return (
        <Panel className="border-x-0 !rounded-none bg-[#161c28]/90 overflow-hidden">
            {/* ── Desktop layout (md+): sparkline + scrolling events + count ── */}
            <div className="hidden md:flex items-center h-[72px]">
                {/* GTI sparkline */}
                <div className="w-56 px-4 py-2 border-r border-border/50 h-full flex flex-col justify-center shrink-0">
                    <div className="flex justify-between items-center text-[10px] font-mono tracking-wider mb-2">
                        <span className="text-muted-foreground uppercase">GTI Trend</span>
                        <span className="text-[var(--color-primary)] font-bold">
                            {gti ? gti.gti_value.toFixed(1) : '--.-'}
                        </span>
                    </div>
                    <div className="h-4 w-full flex items-end overflow-hidden gap-0.5">
                        {gtiValues.map((v, i) => (
                            <div
                                key={i}
                                className="flex-1 bg-[var(--color-primary)]/40 hover:bg-[var(--color-primary)] transition-colors rounded-sm"
                                style={{ height: `${(v / 100) * 100}%` }}
                            />
                        ))}
                    </div>
                </div>

                {/* Events list */}
                <div className="flex-1 overflow-x-auto overflow-y-hidden flex items-center px-4 gap-3 scrollbar-hide">
                    {events.slice(0, 8).map((e: any) => (
                        <EventMarker key={e.id} event={e} />
                    ))}
                </div>

                {/* Count */}
                <div className="px-6 flex flex-col items-center justify-center border-l border-border/50 h-full shrink-0">
                    <span className="text-2xl font-mono font-bold">{events.length}</span>
                    <span className="text-[9px] uppercase tracking-wider text-muted-foreground">Events</span>
                </div>
            </div>

            {/* ── Mobile layout (< md): compact single-row bar ── */}
            <div className="flex md:hidden items-center h-[48px] px-3 gap-3">
                {/* GTI badge */}
                <div className="flex items-center gap-1.5 shrink-0">
                    <div className="h-3 w-8 flex items-end gap-px overflow-hidden">
                        {gtiValues.slice(-5).map((v, i) => (
                            <div
                                key={i}
                                className="flex-1 bg-[var(--color-primary)]/50 rounded-sm"
                                style={{ height: `${(v / 100) * 100}%` }}
                            />
                        ))}
                    </div>
                    <span className="text-[var(--color-primary)] font-mono text-xs font-bold">
                        GTI {gti ? gti.gti_value.toFixed(0) : '--'}
                    </span>
                </div>

                <div className="w-px h-5 bg-border/50 shrink-0" />

                {/* Scrollable event chips */}
                <div className="flex-1 overflow-x-auto scrollbar-hide flex items-center gap-2">
                    {events.slice(0, 5).map((e: any) => {
                        const severity = e.severity_score ?? e.magnitude ?? 0
                        const isCritical = severity >= 0.8
                        const isHigh = severity >= 0.6
                        const color = isCritical ? '#ef4444' : isHigh ? '#f59e0b' : '#e2e8f0'
                        return (
                            <div
                                key={e.id}
                                className="shrink-0 flex items-center gap-1.5 px-2 py-1 rounded border border-border/40 bg-secondary/30"
                                style={{ borderLeftColor: color, borderLeftWidth: '2px' }}
                            >
                                <span className="text-[9px] font-mono whitespace-nowrap max-w-[120px] overflow-hidden text-ellipsis">
                                    {e.title}
                                </span>
                            </div>
                        )
                    })}
                </div>

                {/* Event count */}
                <div className="shrink-0 flex items-center gap-1">
                    <span className="text-sm font-mono font-bold">{events.length}</span>
                    <span className="text-[8px] uppercase tracking-wider text-muted-foreground">events</span>
                </div>
            </div>
        </Panel>
    )
}
