import { create } from 'zustand'

export type VisualizationMode = 'globe' | 'map' | 'charts' | 'portfolio'
export type SignalType = 'BUY' | 'SELL' | 'HOLD'
export type AssetClass = 'Equities' | 'Bonds' | 'Commodities' | 'Forex' | 'Crypto'
export type Region = 'North America' | 'Europe' | 'Asia Pacific' | 'Middle East' | 'Latin America' | 'Africa'

export interface ScenarioParams {
    oilPriceShock: number
    interestRateChange: number
    geopoliticalEscalation: number
    supplyChainDisruption: number
    cyberThreatLevel: number
}

export interface CartHolding {
    symbol: string
    label: string
    weight: number
    sector?: string
    region?: string
}

interface GeoTradeState {
    // Mode selection
    mode: VisualizationMode
    setMode: (mode: VisualizationMode) => void

    // Country selection (shared between Globe and Map)
    selectedCountryIso: string | null
    setSelectedCountryIso: (iso: string | null) => void

    // Selection
    selectedAssetId: string | null
    setSelectedAssetId: (id: string | null) => void
    hoveredAssetId: string | null
    setHoveredAssetId: (id: string | null) => void

    // Filters
    selectedRegions: Region[]
    toggleRegion: (region: Region) => void
    selectedAssetClasses: AssetClass[]
    toggleAssetClass: (ac: AssetClass) => void

    // Scenario
    scenario: ScenarioParams
    updateScenario: (params: Partial<ScenarioParams>) => void
    runSimulation: () => void // placeholder for triggering re-calc
}

const defaultScenario: ScenarioParams = {
    oilPriceShock: 0,
    interestRateChange: 0,
    geopoliticalEscalation: 50,
    supplyChainDisruption: 30,
    cyberThreatLevel: 40,
}

export const useStore = create<GeoTradeState>((set) => ({
    mode: 'globe',
    setMode: (mode) => set({ mode }),

    selectedCountryIso: null,
    setSelectedCountryIso: (iso) => set({ selectedCountryIso: iso }),

    selectedAssetId: null,
    setSelectedAssetId: (id) => set({ selectedAssetId: id }),
    hoveredAssetId: null,
    setHoveredAssetId: (id) => set({ hoveredAssetId: id }),

    selectedRegions: [],
    toggleRegion: (region) => set((state) => ({
        selectedRegions: state.selectedRegions.includes(region)
            ? state.selectedRegions.filter((r) => r !== region)
            : [...state.selectedRegions, region]
    })),

    selectedAssetClasses: [],
    toggleAssetClass: (ac) => set((state) => ({
        selectedAssetClasses: state.selectedAssetClasses.includes(ac)
            ? state.selectedAssetClasses.filter((a) => a !== ac)
            : [...state.selectedAssetClasses, ac]
    })),

    scenario: defaultScenario,
    updateScenario: (params) => set((state) => ({
        scenario: { ...state.scenario, ...params }
    })),

    runSimulation: () => {
        // Triggers global simulation recalculations in the actual UI.
        console.log("Simulation triggered with params.")
    }
}))
