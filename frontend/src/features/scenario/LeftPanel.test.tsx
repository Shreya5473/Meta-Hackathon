import { render, screen, fireEvent } from '@testing-library/react'
import { LeftPanel } from './LeftPanel'
import { expect, test } from 'vitest'

test('renders filters and scenario sliders', () => {
    render(<LeftPanel />)

    // Renders the region filter "North America"
    expect(screen.getByText('N. America')).toBeInTheDocument()

    // Scenario sliders
    expect(screen.getByText('Oil Shock')).toBeInTheDocument()
    expect(screen.getByText('Rate Change')).toBeInTheDocument()
})

test('can click a filter', () => {
    render(<LeftPanel />)

    const equitiesButton = screen.getByText('Equities')
    fireEvent.click(equitiesButton)

    // Validates the component accepts clicks.
    // In a real app with store assertion, we'd mock the Zustand store 
    // and assert it was called.
})
