import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'

export const useGti = () => {
    return useQuery({
        queryKey: ['gti'],
        queryFn: api.getGti,
        refetchInterval: 15000,
        staleTime: 10000,
    })
}

export const useSignals = () => {
    return useQuery({
        queryKey: ['signals'],
        queryFn: api.getSignals,
        refetchInterval: 30000,
        staleTime: 20000,
    })
}

export const useEvents = () => {
    return useQuery({
        queryKey: ['events'],
        queryFn: api.getEvents,
        refetchInterval: 30000,
        staleTime: 25000,
    })
}

export const useGlobeCountries = () => {
    return useQuery({
        queryKey: ['globe-countries'],
        queryFn: api.getGlobeCountries,
        refetchInterval: 30000,
        staleTime: 20000,
    })
}

export const useEnhancedSignals = (region?: string) => {
    return useQuery({
        queryKey: ['enhanced-signals', region ?? 'all'],
        queryFn: () => api.getEnhancedSignals(region),
        refetchInterval: 60000,
        staleTime: 45000,
    })
}

export const useLivePrices = (symbols: string[]) => {
    const uniqueSymbols = Array.from(new Set(symbols.map(s => s.toUpperCase()))).sort()
    return useQuery({
        queryKey: ['live-prices', uniqueSymbols.join(',')],
        queryFn: () => api.getLivePrices(uniqueSymbols),
        enabled: uniqueSymbols.length > 0,
        refetchInterval: 5000,
        staleTime: 3000,
    })
}

export const useSimulateScenario = () => {
    return useMutation({
        mutationFn: api.simulateScenario
    })
}

export const useEvaluatePortfolio = () => {
    return useMutation({
        mutationFn: api.evaluatePortfolio
    })
}

// ── Cart / email-keyed portfolio hooks ────────────────────────────────────────

export const useCart = (email: string | null) => {
    return useQuery({
        queryKey: ['cart', email],
        queryFn: () => api.getCart(email!),
        enabled: !!email,
        staleTime: 30000,
    })
}

export const useSaveCart = (email: string | null) => {
    const qc = useQueryClient()
    return useMutation({
        mutationFn: ({ holdings, name }: { holdings: any[]; name?: string }) =>
            api.saveCart(email!, holdings, name),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['cart', email] })
        },
    })
}

export const usePortfolioRisk = () => {
    return useMutation({
        mutationFn: (email: string) => api.getPortfolioRisk(email),
    })
}
