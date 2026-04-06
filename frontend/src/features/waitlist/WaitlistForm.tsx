import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, AlertCircle, Loader2, Sparkles, Send } from 'lucide-react'
import { API_BASE } from '@/shared/api/client'
import { setStoredEmail } from '@/shared/auth/useAuth'

const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL as string) || 'https://qvpcktrfbtzhivoksqzp.supabase.co'
const SUPABASE_ANON = (import.meta.env.VITE_SUPABASE_ANON_KEY as string) || ''

interface WaitlistFormProps {
    onClose: () => void
    onSuccess?: (email: string) => void
}

/** Insert directly to Supabase — no backend, no CORS, no cold start */
async function addToWaitlistDirect(email: string): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/waitlist`, {
        method: 'POST',
        headers: {
            apikey: SUPABASE_ANON,
            Authorization: `Bearer ${SUPABASE_ANON}`,
            'Content-Type': 'application/json',
            Prefer: 'return=minimal',
        },
        body: JSON.stringify({ email }),
        signal: AbortSignal.timeout(15000),
    })
    if (res.ok) return { success: true, message: 'Added to waitlist' }
    const err = await res.text().catch(() => '')
    if (/duplicate|unique|23505/i.test(err)) return { success: false, message: 'Email already registered' }
    return { success: false, message: 'Could not add. Please try again.' }
}

/** Insert via backend API (fallback) */
async function addToWaitlistApi(email: string): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/waitlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
        signal: AbortSignal.timeout(30000),
    })
    const data = await res.json().catch(() => ({}))
    return { success: !!(res.ok && data.success), message: data.message || 'Could not add. Please try again.' }
}

export function WaitlistForm({ onClose, onSuccess }: WaitlistFormProps) {
    const [email, setEmail] = useState('')
    const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
    const [message, setMessage] = useState('')
    const [count, setCount] = useState<number | null>(null)

    useEffect(() => {
        fetch(`${API_BASE}/waitlist/count`)
            .then(res => res.json())
            .then(data => { if (data?.count !== undefined) setCount(data.count) })
            .catch(() => {})
    }, [])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!email || !email.includes('@')) return
        setStatus('loading')
        setMessage('')

        const addFn = SUPABASE_ANON ? addToWaitlistDirect : addToWaitlistApi
        try {
            const result = await addFn(email.trim())
            if (result.success) {
                setStatus('success')
                setMessage("You're on the waitlist 🚀")
                setStoredEmail(email.trim())
                onSuccess?.(email.trim())
            } else {
                setStatus('error')
                setMessage(result.message)
            }
        } catch {
            setStatus('error')
            setMessage('Connection failed. Please try again.')
        }
    }

    return (
        <div className="flex flex-col items-center p-6 sm:p-8 max-w-md w-full relative">
            {/* Header */}
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-white/10 to-white/5 border border-white/20 flex items-center justify-center mb-5 shadow-[0_0_15px_rgba(255,255,255,0.15)] relative">
                <Sparkles className="w-6 h-6 text-white" />
            </div>

            <h2 className="text-2xl font-bold text-white mb-2 text-center">
                Get Early Access
            </h2>

            <p className="text-sm font-mono text-gray-400 text-center mb-6 leading-relaxed">
                Join {count ? <span className="text-white font-bold">{count}</span> : 'other'} professionals leveraging AI-driven geopolitical market intelligence.
            </p>

            {/* Form Area */}
            <AnimatePresence mode="wait">
                {status === 'success' ? (
                    <motion.div
                        key="success"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="w-full flex flex-col items-center p-6 bg-green-500/10 border border-green-500/30 rounded-xl"
                    >
                        <CheckCircle2 className="w-10 h-10 text-green-400 mb-3" />
                        <p className="text-green-400 font-bold font-mono text-center">{message}</p>
                        <p className="text-xs text-gray-400 text-center mt-2">We'll email you when your account is ready.</p>
                        <button
                            onClick={onClose}
                            className="mt-6 px-6 py-2 rounded-lg bg-white/5 border border-white/10 text-white font-mono text-xs hover:bg-white/10 transition-colors"
                            style={{ minHeight: '44px' }}
                        >
                            Close
                        </button>
                    </motion.div>
                ) : (
                    <motion.form
                        key="form"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onSubmit={handleSubmit}
                        className="w-full space-y-4"
                    >
                        <div className="relative">
                            <input
                                type="email"
                                value={email}
                                onChange={e => {
                                    setEmail(e.target.value)
                                    if (status === 'error') setStatus('idle')
                                }}
                                placeholder="Enter your email"
                                required
                                disabled={status === 'loading'}
                                className={`w-full bg-[#0a0f1e]/80 border ${status === 'error' ? 'border-red-500/50 focus:border-red-500' : 'border-white/15 focus:border-white/30/60'} rounded-xl px-4 py-3 text-white font-mono text-sm outline-none transition-colors disabled:opacity-50`}
                                style={{ minHeight: '44px' }}
                            />
                            {status === 'error' && (
                                <AlertCircle className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-red-500" />
                            )}
                        </div>

                        {status === 'error' && (
                            <p className="text-red-400 text-xs font-mono px-1 flex items-center gap-1.5">
                                <span className="w-1 h-1 rounded-full bg-red-400" /> {message}
                            </p>
                        )}

                        <button
                            type="submit"
                            disabled={status === 'loading' || !email}
                            className="w-full relative group overflow-hidden rounded-xl bg-white disabled:opacity-50 disabled:cursor-not-allowed border border-white/30 shadow-[0_0_20px_rgba(255,255,255,0.1)] hover:shadow-[0_0_25px_rgba(255,255,255,0.1)] transition-all"
                            style={{ minHeight: '44px' }}
                        >
                            <div className="absolute inset-0 bg-gradient-to-r from-white to-gray-300 opacity-0 group-hover:opacity-100 transition-opacity disabled:hidden" />
                            <div className="relative flex items-center justify-center gap-2 py-3 px-4">
                                {status === 'loading' ? (
                                    <>
                                        <Loader2 className="w-4 h-4 text-white animate-spin" />
                                        <span className="font-bold text-white text-sm uppercase tracking-wider">Joining...</span>
                                    </>
                                ) : (
                                    <>
                                        <span className="font-bold text-white text-sm uppercase tracking-wider">
                                            {status === 'error' ? 'Try again' : 'Join Waitlist'}
                                        </span>
                                        <Send className="w-3.5 h-3.5 text-white group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                                    </>
                                )}
                            </div>
                        </button>

                        <p className="text-[10px] text-gray-500 font-mono text-center pt-2">
                            No spam. Unsubscribe at any time.
                        </p>
                    </motion.form>
                )}
            </AnimatePresence>
        </div>
    )
}
