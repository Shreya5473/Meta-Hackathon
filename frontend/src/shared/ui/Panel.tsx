import React from 'react'
import { motion, type HTMLMotionProps } from 'framer-motion'
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

export const Panel = React.forwardRef<HTMLDivElement, HTMLMotionProps<"div">>(
    ({ className, children, ...props }, ref) => {
        return (
            <motion.div
                ref={ref}
                className={cn("cyber-panel relative overflow-hidden", className)}
                {...props}
            >
                <div className="absolute inset-0 bg-gradient-to-b from-transparent to-white/5 pointer-events-none mix-blend-overlay" />
                {children as React.ReactNode}
            </motion.div>
        )
    }
)
Panel.displayName = "Panel"

export function Badge({ children, variant = 'default', className }: { children: React.ReactNode, variant?: 'default' | 'critical' | 'warn' | 'success', className?: string }) {
    const variants = {
        default: "bg-[var(--color-primary)]/10 text-[var(--color-primary)] border-[var(--color-primary)]/30",
        critical: "bg-[#ef4444]/10 text-[#ef4444] border-[#ef4444]/30",
        warn: "bg-[#f59e0b]/10 text-[#f59e0b] border-[#f59e0b]/30",
        success: "bg-[#22c55e]/10 text-[#22c55e] border-[#22c55e]/30"
    }
    return (
        <span className={cn("inline-flex items-center rounded-sm border px-2 py-0.5 text-[10px] uppercase font-mono tracking-wider font-semibold", variants[variant], className)}>
            {children}
        </span>
    )
}
