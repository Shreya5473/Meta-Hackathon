import { z } from 'zod'

export const RegionSchema = z.enum([
    'North America', 'Europe', 'Asia Pacific', 'Middle East', 'Latin America', 'Africa'
])
export const AssetClassSchema = z.enum(['Equities', 'Bonds', 'Commodities', 'Forex', 'Crypto'])
export const SignalTypeSchema = z.enum(['BUY', 'SELL', 'HOLD'])

export const GTIDriverSchema = z.object({
    region: z.string().optional(),
    driver: z.string().optional(),
    contribution_weight: z.number().optional()
})

export const GTIResponseSchema = z.object({
    gti_value: z.number(),
    gti_delta_1h: z.number(),
    ts: z.string(),
    top_drivers: z.array(GTIDriverSchema).optional()
})
export type GTIResponse = z.infer<typeof GTIResponseSchema>

export const SignalSchema = z.object({
    symbol: z.string(),
    sector: z.string().optional(),
    region: z.string().optional(),
    recommendation: z.string().optional(),
    confidence_score: z.number().optional(),
    uncertainty: z.number().optional(),
    price: z.number().optional(),
    directional_bias: z.number().optional(),
    reasoning: z.string().optional(),
    risk_factors: z.array(z.string()).optional(),
    correlated_assets: z.array(z.string()).optional()
})

export const SignalsResponseSchema = z.object({
    signals: z.array(SignalSchema)
})
export type SignalsResponse = z.infer<typeof SignalsResponseSchema>

export const TimelineEventSchema = z.object({
    id: z.union([z.string(), z.number()]),
    title: z.string(),
    ts: z.string().optional(),
    occurred_at: z.string().optional(),
    severity_score: z.number(),
    region: z.string().optional(),
    magnitude: z.number().optional(),
    summary: z.string().optional()
})

export const EventsResponseSchema = z.object({
    events: z.array(TimelineEventSchema)
})
export type EventsResponse = z.infer<typeof EventsResponseSchema>
